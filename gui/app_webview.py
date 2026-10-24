import os
import sys
import time
import threading
import subprocess
from dataclasses import replace
from ctypes import wintypes
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

try:
    import psutil
except ImportError:
    psutil = None

import webview

from core.proxy_model import ProxyItem, parse_bulk_proxies
from core.singbox_manager import SingBoxManager
from core.paths import sys_exe
from core.version import APP_VERSION
from core.admin_utils import is_admin
from core.ip_service import (
    get_current_system_ip,
    quick_ping_proxy,
    test_proxy,
    resolve_host_geo,
    probe_proxy_protocol
)
from core.storage import save_proxies, load_proxies, load_settings, save_setting, get_secure_storage_path, StorageError, get_migration_error
from core.connection_log import ConnectionJournal, ConnectionSource
from core.protection_session import ProtectionSession
from core.win_job import bind_self_to_job


class TunState:
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


def get_html_content() -> str:
    """Загружает разметку index.html из бандла PyInstaller или с диска."""
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "gui", "web", "index.html"))
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(cur_dir, "web", "index.html"))
    candidates.append(os.path.join(os.path.dirname(cur_dir), "gui", "web", "index.html"))

    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    raise FileNotFoundError("Не удалось найти файл index.html для WebView2.")


class ProxyTunBridgeApi:
    """
    Потокобезопасный мост между JavaScript-интерфейсом в WebView2 и сетевым ядром Python.
    Реализует раздельные блокировки, конечный автомат состояний (TunState), порядковые номера
    ошибок (error_seq), защиту от затирания хранилища при сбоях и безопасное завершение.
    """

    def __init__(self):
        self._lock = threading.RLock()       # Для мгновенных чтений/записей состояния
        self._op_lock = threading.Lock()     # Сериализует тяжелые операции start/stop
        self._sb = SingBoxManager()
        self._journal = ConnectionJournal()
        self._source = ConnectionSource(self._journal)
        self._protection = ProtectionSession(self._sb, self._journal)
        self._state = TunState.IDLE
        self._last_error: Optional[str] = None
        self._error_seq: int = 0
        self._storage_error: Optional[str] = None
        self._closing: bool = False
        self._ip_gen = 0

        try:
            self.proxies: List[ProxyItem] = load_proxies()
        except StorageError as e:
            self.proxies = []
            self._storage_error = str(e)
            self._last_error = f"Ошибка хранилища: {e}"
            self._error_seq += 1

        mig_err = get_migration_error()
        if mig_err and not self._last_error:
            self._last_error = mig_err
            self._error_seq += 1

        self.selected_proxy_id: Optional[str] = self.proxies[0].id if self.proxies else None
        self.settings: Dict[str, Any] = load_settings()
        self.settings["bypass_telegram"] = False
        self._session_candidates = ()
        self._session_cursor = 0

        self.is_admin = is_admin()
        self.connected_since: Optional[float] = None
        self.current_system_ip: Dict[str, Any] = {"ip": "IP появится после подключения", "country_code": "", "status": "unavailable"}

        # Телеметрия скорости
        self.last_net_bytes: Optional[Tuple[int, int]] = None
        self.last_net_time: Optional[float] = None
        self.current_upload_mbps: float = 0.0
        self.current_download_mbps: float = 0.0
        self._probe_fail_count: int = 0

        self._window = None

        # Запуск фонового обновления IP и сторожевого таймера
        self._geo_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="geo_worker")
        threading.Thread(target=self._watchdog_loop, daemon=True).start()

        # Фоновое доопределение гео для серверов без страны при старте в пуле воркеров
        unresolved_ids = [p.id for p in self.proxies if not p.country or p.get_country_code() == "PX"]

    def get_connections(self, after=0, query=""):
        return self._journal.read(after, query=query)

    def clear_connections(self):
        self._journal.clear()
        return {"success": True}

    def release_protection(self):
        with self._lock:
            if getattr(self,'_release_pending',False):
                return {"success":False,"busy":True,"error":"Снятие защиты уже выполняется"}
            self._release_pending=True
            self._op_generation=getattr(self,'_op_generation',0)+1
            self._state=TunState.STOPPING
            self._protection.cancel.set()
            self._ip_gen += 1
            self.current_system_ip={"ip":"IP не проверен: защита снимается", "country_code":"", "status":"unavailable"}
        with self._op_lock:
            try:
                self._protection.release()
                with self._lock:
                    self._state = TunState.IDLE
                    self.connected_since=None
                    self._ip_gen += 1
                    self.current_system_ip={"ip":"Защита снята: IP не проверен", "country_code":"", "status":"unavailable"}
                return {"success": True}
            except Exception:
                with self._lock:
                    self._state=TunState.ERROR
                    self._protection.state='unknown'
                return {"success": False, "error": "Не удалось снять защиту Windows; используйте локальное восстановление"}
            finally:
                with self._lock: self._release_pending=False

    def set_window(self, window):
        self._window = window

    def _notify_ui_refresh(self):
        """Оповещает интерфейс WebView о фоновом обновлении данных прокси."""
        if self._window and not self._closing:
            try:
                self._window.evaluate_js("if (typeof refreshState === 'function') refreshState();")
            except Exception:
                pass

    def _resolve_single_proxy_async(self, proxy_id: str):
        if self._closing or self._protection.state != "unarmed":
            return
        with self._lock:
            p = next((x for x in self.proxies if x.id == proxy_id), None)
            if not p:
                return
            host = p.host
            original = p

        c, cc, city = resolve_host_geo(host, timeout=3.0)
        if self._closing:
            return

        with self._lock:
            if self._closing:
                return
            p = next((x for x in self.proxies if x.id == proxy_id), None)
            if p is original and p.host == host and self._protection.state == 'unarmed' and (c or (cc and cc != "PX")):
                p.country = c
                p.country_code = cc if cc != "PX" else ""
                p.city = city
                try:
                    self._save()
                except Exception as e:
                    import logging
                    logging.getLogger("ProxyTUN").warning("Ошибка сохранения гео в фоне: %s", e)
        if not self._closing:
            self._notify_ui_refresh()

    def _resolve_proxies_batch_async(self, proxy_ids: List[str]):
        if self._protection.state != "unarmed": return

        updated = False

        def _worker(pid):
            nonlocal updated
            if self._closing:
                return
            with self._lock:
                p = next((x for x in self.proxies if x.id == pid), None)
                if not p:
                    return
                host = p.host
                original = p
            c, cc, city = resolve_host_geo(host, timeout=3.0)
            if self._closing:
                return
            with self._lock:
                if self._closing:
                    return
                p = next((x for x in self.proxies if x.id == pid), None)
                if p is original and p.host == host and self._protection.state == 'unarmed' and (c or (cc and cc != "PX")):
                    p.country = c
                    p.country_code = cc if cc != "PX" else ""
                    p.city = city
                    updated = True

        for pid in proxy_ids:
            if self._closing:
                break
            _worker(pid)

        if not self._closing and updated:
            with self._lock:
                if self._closing:
                    return
                try:
                    self._save()
                except Exception as e:
                    import logging
                    logging.getLogger("ProxyTUN").warning("Ошибка сохранения батча гео: %s", e)
        if not self._closing:
            self._notify_ui_refresh()

    def _save(self) -> None:
        """Сохраняет список прокси с блокировкой при ошибках расшифровки (B4) и при закрытии."""
        if self._closing:
            return
        if self._storage_error:
            raise StorageError(f"Хранилище заблокировано для защиты данных: {self._storage_error}")
        save_proxies(self.proxies)

    def reset_storage(self) -> Dict[str, Any]:
        """Явный сброс хранилища пользователем при повреждении с гарантированной резервной копией (R4)."""
        with self._lock:
            path = get_secure_storage_path()
            if os.path.exists(path):
                try:
                    os.replace(path, f"{path}.reset-{int(time.time())}.bak")
                except Exception as e:
                    return {"success": False, "error": f"Не удалось создать резервную копию: {e}"}
            self._storage_error = None
            self.proxies = []
            self.selected_proxy_id = None
            try:
                save_proxies(self.proxies)
            except Exception as e:
                return {"success": False, "error": str(e)}
            return {"success": True}

    def _ip_context(self):
        if self._closing:
            return None
        protection = self._protection
        if protection.state == "protected":
            if (self._state != TunState.RUNNING or protection.cancel.is_set()
                    or not self._sb.is_running() or not self._sb.proxy_reachable):
                return None
            return (protection.generation, self._sb.process, "protected")
        if protection.state == "unarmed" and self._state == TunState.IDLE:
            return (protection.generation, None, "unarmed")
        return None

    def _refresh_ip_async(self):
        """Coalesced refresh, with lifecycle checks before request and publication."""
        with self._lock:
            context = self._ip_context()
            if context is None:
                self._ip_gen += 1
                self.current_system_ip = {"ip": "IP недоступен: туннель не подключён", "country_code": "", "status": "blocked"}
                return
            if getattr(self, "_ip_pending", False):
                self._ip_retry = getattr(self, "_ip_pending_context", None) != context
                if self._ip_retry:
                    self.current_system_ip = {"ip": "IP недоступен: предыдущая проверка не завершена", "country_code": "", "status": "unavailable"}
                return
            self._ip_gen += 1
            generation = self._ip_gen
            self._ip_pending = True
            self._ip_pending_context = context
            self._ip_retry = False
            self.current_system_ip = {"ip": "Проверка IP…", "country_code": "", "status": "checking"}

        def expire():
            with self._lock:
                if self._ip_pending and generation == self._ip_gen:
                    self._ip_gen += 1  # Late query cannot publish after deadline.
                    self.current_system_ip = {"ip": "IP недоступен: время проверки истекло", "country_code": "", "status": "unavailable"}
        timer = threading.Timer(4.0, expire)
        timer.daemon = True
        timer.start()

        def worker():
            try:
                with self._lock:
                    if generation != self._ip_gen or context != self._ip_context():
                        return
                try:
                    data = get_current_system_ip(timeout=3.0)
                except Exception:
                    data = {"ip": "IP недоступен", "country_code": "", "status": "unavailable"}
                with self._lock:
                    if generation == self._ip_gen and context == self._ip_context():
                        self.current_system_ip = data
            finally:
                timer.cancel()
                with self._lock:
                    self._ip_pending = False
                    retry = self._ip_retry and not self._closing
                    if generation == self._ip_gen and context != self._ip_context():
                        self.current_system_ip = {"ip": "IP не проверен: состояние изменилось", "country_code": "", "status": "unavailable"}
                if retry:
                    self._refresh_ip_async()
        threading.Thread(target=worker, daemon=True).start()

    def _watchdog_loop(self):
        next_probe = time.monotonic() + 30
        failures = 0
        while not self._closing:
            time.sleep(1.5)
            if not self._op_lock.acquire(blocking=False):
                continue
            retry = False
            try:
                if self._state != TunState.RUNNING:
                    continue
                generation = self._protection.generation
                process = self._sb.process
                if not self._sb.is_running():
                    retry = True
                else:
                    self._source.poll(self._sb, generation)
                    if time.monotonic() >= next_probe:
                        reachable = self._sb._probe_tunnel(process, deadline=time.monotonic()+2.5)
                        next_probe = time.monotonic()+min(300,30*2**min(failures,4))
                        if generation == self._protection.generation and process is self._sb.process:
                            failures = 0 if reachable else failures+1
                            retry = not reachable
                if retry and not self._closing and self._state == TunState.RUNNING:
                    with self._lock:
                        if self._closing or self._state != TunState.RUNNING or getattr(self,'_release_pending',False) or self._protection.cancel.is_set():
                            continue
                        candidates = self._remaining_session_candidates()
                        self._state = TunState.STARTING
                        self._ip_gen += 1
                        self.current_system_ip = {"ip": "Переключение сервера…", "country_code": "", "status": "unavailable"}
                    success = self._protection.connect(candidates)
                    with self._lock:
                        self._finish_session_attempt(success)
                        if getattr(self,'_release_pending',False) or self._closing:
                            continue
                        self._state = TunState.RUNNING if success else TunState.ERROR
                        self._last_error = None if success else "Интернет заблокирован: резервные серверы недоступны"
                        self.connected_since = time.time() if success else None
                        if not success: self._error_seq += 1
                    self._refresh_ip_async()
            except Exception:
                with self._lock:
                    if getattr(self,'_release_pending',False):
                        continue
                    self._state = TunState.ERROR
                    self._last_error = "Ошибка защиты Windows; подключение остановлено"
                    self._error_seq += 1
                try:
                    self._sb.stop()
                except Exception:
                    self._protection.state = "unknown"
                self._refresh_ip_async()
            finally:
                self._op_lock.release()

    def _proxy_to_dict(self, p: Optional[ProxyItem]) -> Optional[Dict[str, Any]]:
        if not p:
            return None
        # raw_line и пароль НЕ передаются в DOM интерфейса для защиты от утечек
        return {
            "id": p.id,
            "host": p.host,
            "port": p.port,
            "protocol": p.protocol,
            "username": p.username,
            "tag": p.tag,
            "latency_ms": p.latency_ms,
            "country": p.country,
            "city": p.city,
            "country_code": p.get_country_code(),
            "location_name": p.get_location_name()
        }

    def _get_selected_proxy(self) -> Optional[ProxyItem]:
        for p in self.proxies:
            if p.id == self.selected_proxy_id:
                return p
        return self.proxies[0] if self.proxies else None

    # ================= JS API METHODS =================

    def _fallback_ids(self):
        """Missing key preserves legacy order; an explicitly empty list stays empty."""
        available = {p.id for p in self.proxies}
        stored = self.settings.get('fallback_proxy_ids', [p.id for p in self.proxies])
        result = []
        for proxy_id in stored if isinstance(stored, list) else []:
            if isinstance(proxy_id, str) and proxy_id in available and proxy_id not in result:
                result.append(proxy_id)
        return result

    def _snapshot_session(self, primary, generation):
        """Called under _lock once per manual start; never reads saved data on retry."""
        by_id = {p.id: p for p in self.proxies}
        ids = [primary.id] + [item for item in self._fallback_ids() if item != primary.id]
        self._session_candidates = tuple(replace(by_id[item]) for item in ids)
        self._session_cursor = 0
        self._session_generation = generation

    def _remaining_session_candidates(self):
        queue = getattr(self, '_session_candidates', ())
        cursor = getattr(self, '_session_cursor', 0)
        return tuple(replace(item) for item in queue[cursor:])

    def _finish_session_attempt(self, success):
        queue = getattr(self, '_session_candidates', ())
        cursor = getattr(self, '_session_cursor', 0)
        if success:
            # ProtectionSession resolves the whole initial queue before arming.
            # Keep those numeric endpoints in the session: editing saved hostnames
            # correctly invalidates its cache, but must not disable this session.
            import ipaddress
            cache = getattr(self._protection, 'cache', {})
            hosts = getattr(self._protection, 'cache_hosts', {})
            frozen = []
            for item in queue:
                address = cache.get(item.id) if isinstance(cache, dict) else None
                bound_host = hosts.get(item.id) if isinstance(hosts, dict) else None
                if bound_host == item.host.rstrip('.').casefold() and isinstance(address, str):
                    try:
                        item = replace(item, host=str(ipaddress.ip_address(address)))
                    except ValueError:
                        pass
                frozen.append(item)
            queue = self._session_candidates = tuple(frozen)
        active_id = self._sb.active_proxy.id if success and self._sb.active_proxy else None
        # Every candidate preceding the successful one has already failed.
        self._session_cursor = next((i + 1 for i in range(cursor, len(queue))
                                     if queue[i].id == active_id), len(queue))

    def get_fallbacks(self) -> Dict[str, Any]:
        with self._lock:
            return {'success': True, 'fallback_proxy_ids': self._fallback_ids(),
                    'proxies': [self._proxy_to_dict(p) for p in self.proxies],
                    'applies_next_connection': self._state in (TunState.RUNNING, TunState.STARTING)}

    def set_fallbacks(self, proxy_ids) -> Dict[str, Any]:
        with self._lock:
            if self._closing or getattr(self, '_release_pending', False):
                return {'success': False, 'busy': True, 'error': 'Операция завершения уже выполняется.'}
            available = {p.id for p in self.proxies}
            if (not isinstance(proxy_ids, list) or
                    any(not isinstance(item, str) or item not in available for item in proxy_ids) or
                    len(set(proxy_ids)) != len(proxy_ids)):
                return {'success': False, 'error': 'Некорректный список резервов. Откройте его заново.'}
            ordered = list(proxy_ids)
            try:
                save_setting('fallback_proxy_ids', ordered)
            except Exception:
                return {'success': False, 'error': 'Не удалось сохранить резервы. Повторите попытку.'}
            self.settings['fallback_proxy_ids'] = ordered
            return {'success': True, 'fallback_proxy_ids': list(ordered)}

    def get_state(self) -> Dict[str, Any]:
        """Возвращает полное состояние системы в JS (мгновенно, без ожидания сетевых операций)."""
        with self._lock:
            sel = self._get_selected_proxy()
            act = self._sb.active_proxy
            is_run = (self._state == TunState.RUNNING and self._sb.is_running())

            return {
                "is_running": is_run,
                "state": self._state,
                "proxy_reachable": self._sb.proxy_reachable,
                "last_error": self._last_error,
                "error_seq": self._error_seq,
                "storage_error": self._storage_error,
                "connected_since": self.connected_since,
                "is_admin": self.is_admin,
                "system_ip": self.current_system_ip,
                "network_warning": self._network_warning(),
                "speed_upload": f"{self.current_upload_mbps:.1f} Mb/s",
                "speed_download": f"{self.current_download_mbps:.1f} Mb/s",
                "active_proxy": self._proxy_to_dict(act),
                "selected_proxy": self._proxy_to_dict(sel),
                "proxies": [self._proxy_to_dict(p) for p in self.proxies],
                "protection": self._protection.state,
                "settings": dict(self.settings)
            }

    def get_telemetry(self) -> Dict[str, Any]:
        """Быстрый ежесекундный поллинг телеметрии (скорость адаптера, статус, номер ошибки и IP)."""
        with self._lock:
            is_run = (self._state == TunState.RUNNING and self._sb.is_running())
            state = self._state
            last_err = self._last_error
            err_seq = self._error_seq
            proxy_reach = self._sb.proxy_reachable

        # Точный подсчет скорости текущего интерфейса ядра
        if psutil is not None:
            try:
                pernic = psutil.net_io_counters(pernic=True)
                tun_stat = pernic.get(self._sb.interface_name)
                now_net = tun_stat if (tun_stat and is_run) else psutil.net_io_counters()
                now_time = time.time()
                
                with self._lock:
                    if self.last_net_bytes and self.last_net_time:
                        dt = now_time - self.last_net_time
                        if dt > 0.4:
                            sent_bytes = now_net.bytes_sent - self.last_net_bytes[0]
                            recv_bytes = now_net.bytes_recv - self.last_net_bytes[1]
                            if is_run and sent_bytes >= 0 and recv_bytes >= 0:
                                self.current_upload_mbps = (sent_bytes * 8) / (dt * 1_000_000)
                                self.current_download_mbps = (recv_bytes * 8) / (dt * 1_000_000)
                            else:
                                self.current_upload_mbps = 0.0
                                self.current_download_mbps = 0.0

                    self.last_net_bytes = (now_net.bytes_sent, now_net.bytes_recv)
                    self.last_net_time = now_time
            except Exception:
                pass

        return {
            "is_running": is_run,
            "state": state,
            "proxy_reachable": proxy_reach,
            "last_error": last_err,
            "error_seq": err_seq,
            "speed_upload": f"{self.current_upload_mbps:.1f} Mb/s",
            "speed_download": f"{self.current_download_mbps:.1f} Mb/s",
            "system_ip": self.current_system_ip
        }

    def toggle_tun(self) -> Dict[str, Any]:
        """Атомарный запуск/остановка TUN-режима в фоне."""
        with self._lock:
            if self._closing or getattr(self,'_release_pending',False):
                return {"success": False, "busy": True}

            if self._state == TunState.STARTING:
                self._protection.cancel.set()
                return {"success": True, "state": "stopping"}
            if self._state == TunState.STOPPING:
                return {"success": False, "busy": True, "state": self._state}

            if self._state == TunState.RUNNING:
                self._state = TunState.STOPPING
                self._protection.cancel.set()
                target = "stop"
            else:
                if not self.is_admin:
                    return {
                        "success": False,
                        "error": "Для режима TUN требуются права Администратора Windows!"
                    }
                sel = self._get_selected_proxy()
                if not sel:
                    return {"success": False, "error": "Список серверов пуст. Добавьте прокси!"}
                self._protection.cancel.clear()
                self._state = TunState.STARTING
                target = "start"

            self._ip_gen += 1
            self.current_system_ip = {"ip": "IP после подключения" if target == "start" else "Туннель отключён", "country_code": "", "status": "unavailable"}
            self._op_generation=getattr(self,'_op_generation',0)+1
            if target == 'start':
                self._snapshot_session(sel, self._op_generation)
            threading.Thread(target=self._do_toggle, args=(target,self._op_generation), daemon=True).start()
            return {"success": True, "state": self._state}

    def _do_toggle(self, target: str, generation=None):
        """Выполняет длинные операции запуска/остановки без удержания _lock."""
        with self._op_lock:
            with self._lock:
                if self._closing or getattr(self,'_release_pending',False) or (generation is not None and generation!=getattr(self,'_op_generation',0)):
                    return
                sel = self._get_selected_proxy()
                if target == 'start' and (not hasattr(self, '_session_generation') or
                                          self._session_generation != generation):
                    if not sel:
                        self._state = TunState.ERROR
                        self._last_error = "Список серверов пуст. Выберите или добавьте прокси!"
                        self._error_seq += 1
                        return
                    self._snapshot_session(sel, generation)

            try:
                if target == "start":
                    with self._lock:
                        candidates = self._remaining_session_candidates()
                    success = self._protection.connect(candidates)
                    with self._lock:
                        self._finish_session_attempt(success)
                        if getattr(self,'_release_pending',False) or self._closing:
                            return
                        self.connected_since = time.time() if success else None
                        self._probe_fail_count = 0
                        self._state = TunState.RUNNING if success else TunState.ERROR
                        self._last_error = None if success else "Интернет заблокирован: серверы недоступны"
                        if not success: self._error_seq += 1
                else:
                    self._protection.stop()
                    with self._lock:
                        self.connected_since = None
                        self._probe_fail_count = 0
                        self._state = TunState.IDLE
                        self._last_error = None
            except Exception as e:
                self._protection.state = "unknown"
                with self._lock:
                    if getattr(self,'_release_pending',False):
                        return
                    self._state = TunState.ERROR
                    self._last_error = "Ошибка защиты Windows или остановки TUN. Повторите попытку."
                    self._error_seq += 1
                    self.connected_since = None
                try:
                    self._sb.stop()
                except Exception:
                    # ERROR is already published; retain protection and allow retry.
                    pass

        self._refresh_ip_async()

    def select_proxy(self, proxy_id: str) -> Dict[str, Any]:
        """Выбор активного сервера с безопасным перезапуском."""
        with self._lock:
            if self._closing or getattr(self,'_release_pending',False) or self._state in (TunState.STARTING, TunState.STOPPING):
                return {"success": False, "busy": True}

            changed = (proxy_id != self.selected_proxy_id)
            self.selected_proxy_id = proxy_id
            sel = self._get_selected_proxy()

            if changed and self._state == TunState.RUNNING and sel:
                self._protection.cancel.clear()
                self._state = TunState.STARTING
                self._op_generation=getattr(self,'_op_generation',0)+1
                self._snapshot_session(sel, self._op_generation)
                threading.Thread(target=self._do_toggle, args=("start",self._op_generation), daemon=True).start()

            return {"success": True, "selected_proxy": self._proxy_to_dict(sel)}

    def delete_proxy(self, proxy_id: str) -> Dict[str, Any]:
        """Удаление сервера из списка с откатом при сбое сохранения (R4)."""
        with self._lock:
            prev = list(self.proxies), self.selected_proxy_id
            self.proxies = [p for p in self.proxies if p.id != proxy_id]
            if self.selected_proxy_id == proxy_id:
                self.selected_proxy_id = self.proxies[0].id if self.proxies else None
            try:
                self._save()
            except Exception as e:
                self.proxies, self.selected_proxy_id = prev  # Откат
                return {"success": False, "error": str(e)}

            sel = self._get_selected_proxy()
            return {
                "success": True,
                "proxies": [self._proxy_to_dict(p) for p in self.proxies],
                "selected_proxy": self._proxy_to_dict(sel)
            }

    def edit_proxy(self, proxy_id, host, port, protocol, username='', password=None,
                   tag='', clear_password=False) -> Dict[str, Any]:
        """Replace the saved record; a running session keeps its original snapshot."""
        import ipaddress
        import re
        if not all(isinstance(value, str) for value in (proxy_id, host, protocol, username, tag)) or not (
                password is None or isinstance(password, str)) or type(clear_password) is not bool:
            return {"success": False, "error": "Некорректные поля сервера."}
        host = host.strip()
        valid_host = False
        try:
            ipaddress.ip_address(host)
            valid_host = '%' not in host
        except ValueError:
            try:
                ascii_host = host.encode('idna').decode('ascii').rstrip('.')
                valid_host = len(ascii_host) <= 253 and all(
                    re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                    for label in ascii_host.split('.'))
            except UnicodeError:
                pass
        if not valid_host:
            return {"success": False, "error": "Укажите корректный хост или IP."}
        if type(port) not in (str, int) or len(str(port)) > 5 or not re.fullmatch(r'[0-9]+', str(port)) or not 1 <= int(port) <= 65535:
            return {"success": False, "error": "Порт должен быть в диапазоне 1-65535."}
        protocol = protocol.strip().lower()
        if protocol not in ('socks5', 'http'):
            return {"success": False, "error": "Выберите SOCKS5 или HTTP."}
        with self._lock:
            if self._closing or getattr(self, '_release_pending', False) or self._state in (TunState.STARTING, TunState.STOPPING):
                return {"success": False, "busy": True, "error": "Дождитесь завершения текущей операции."}
            old = next((p for p in self.proxies if p.id == proxy_id), None)
            if old is None:
                return {"success": False, "error": "Сервер не найден."}
            item = replace(old, host=host, port=int(port), protocol=protocol,
                           username=username or None, tag=tag or f'{host}:{port}',
                           password=None if clear_password else (password if password else old.password))
            changed = (item.host, item.port, item.protocol, item.username, item.password) != (
                old.host, old.port, old.protocol, old.username, old.password)
            if changed:
                item.country = item.country_code = item.city = ''
                item.latency_ms = None
                item.last_status = 'unknown'
            previous = self.proxies
            self.proxies = [item if p is old else p for p in previous]
            try:
                self._save()
            except Exception:
                self.proxies = previous
                return {"success": False, "error": "Не удалось сохранить сервер. Повторите попытку."}
            if changed:
                self._protection.cache.pop(proxy_id, None)
                self._protection.cache_hosts.pop(proxy_id, None)
            return {"success": True, "proxies": [self._proxy_to_dict(p) for p in self.proxies],
                    "selected_proxy": self._proxy_to_dict(self._get_selected_proxy())}

    def add_proxy(self, host: str, port: int, protocol: str, username: str = "", password: str = "") -> Dict[str, Any]:
        """Добавление нового прокси с валидацией, автоопределением гео и защитой явного выбора протокола (R4)."""
        import re
        host_clean = re.sub(r"[<>&\"\'/\\]", "", host or "").strip()
        if not host_clean:
            return {"success": False, "error": "Хост не может быть пустым."}
        try:
            port_num = int(port)
            if not (1 <= port_num <= 65535):
                return {"success": False, "error": "Порт должен быть в диапазоне 1-65535."}
        except (ValueError, TypeError):
            return {"success": False, "error": "Некорректный номер порта."}

        # Валидация протокола: явный выбор пользователя защищен от автозамены
        proto_in = (protocol or "socks5").lower().strip()
        if proto_in not in ("socks5", "http", "auto"):
            return {"success": False, "error": "Недопустимый протокол. Допустимы: SOCKS5, HTTP, Auto."}

        if proto_in == "auto":
            # Режим Auto: зондируем сокет, но НЕ сохраняем догадку при неудаче
            probed = probe_proxy_protocol(host_clean, port_num, timeout=1.5)
            if probed in ("socks5", "http"):
                final_proto = probed
            else:
                return {
                    "success": False,
                    "error": "Не удалось автоматически определить протокол узла (таймаут или сервер не отвечает). Пожалуйста, выберите протокол явно: SOCKS5 или HTTP."
                }
        else:
            # Явный выбор пользователя сохраняется строго как есть
            final_proto = proto_in

        # Быстрая проверка гео в локальном кэше памяти без сетевых задержек
        from core.ip_service import _geo_cache
        cached_geo = _geo_cache.get(host_clean)
        c = cached_geo[0] if cached_geo else ""
        cc = cached_geo[1] if cached_geo else ""
        city = cached_geo[2] if cached_geo else ""

        with self._lock:
            prev = list(self.proxies), self.selected_proxy_id
            item = ProxyItem(
                id=f"p_{int(time.time() * 1000)}_{os.urandom(2).hex()}",
                host=host_clean,
                port=port_num,
                protocol=final_proto,
                username=username.strip() if username else None,
                password=password.strip() if password else None,
                country=c,
                country_code=cc if cc != "PX" else "",
                city=city
            )
            self.proxies.append(item)
            if not self.selected_proxy_id:
                self.selected_proxy_id = item.id
            try:
                self._save()
            except Exception as e:
                self.proxies, self.selected_proxy_id = prev  # Откат
                return {"success": False, "error": str(e)}

            # Геоопределение вынесено строго в ограниченный пул воркеров ПОСЛЕ сохранения
            if not c or cc == "PX":
                self._geo_pool.submit(self._resolve_single_proxy_async, item.id)

            sel = self._get_selected_proxy()
            return {
                "success": True,
                "proxies": [self._proxy_to_dict(p) for p in self.proxies],
                "selected_proxy": self._proxy_to_dict(sel)
            }

    def bulk_import(self, raw_text: str) -> Dict[str, Any]:
        """Пакетный импорт списка прокси с параллельным гео-определением (R4)."""
        with self._lock:
            items = parse_bulk_proxies(raw_text)
            if not items:
                return {"success": False, "count": 0}

            prev = list(self.proxies), self.selected_proxy_id
            self.proxies.extend(items)
            if not self.selected_proxy_id and self.proxies:
                self.selected_proxy_id = self.proxies[0].id
            try:
                self._save()
            except Exception as e:
                self.proxies, self.selected_proxy_id = prev  # Откат
                return {"success": False, "error": str(e)}

        # Запускаем пакетное определение гео в пуле воркеров без мутации протоколов
        self._geo_pool.submit(self._resolve_proxies_batch_async, [p.id for p in items])

        return {"success": True, "count": len(items)}

    def ping_proxy(self, proxy_id: str) -> Dict[str, Any]:
        if self._protection.state != "unarmed":
            return {"success": False, "error": "Фоновые прямые проверки отключены при защите"}

        """Быстрый замер задержки конкретного сервера и доопределение гео при необходимости."""
        with self._lock:
            target_proxy = next((p for p in self.proxies if p.id == proxy_id), None)

        if target_proxy:
            lat = quick_ping_proxy(target_proxy, timeout=2.5)
            # Если страна не определена, запустим доопределение
            if not target_proxy.country or target_proxy.get_country_code() == "PX":
                self._geo_pool.submit(self._resolve_single_proxy_async, target_proxy.id)
            with self._lock:
                try:
                    self._save()
                except Exception as e:
                    import logging
                    logging.getLogger("ProxyTUN").warning("Ошибка сохранения задержки: %s", e)
            return {"success": True, "latency": lat}

        return {"success": False, "latency": None}

    def ping_all(self) -> Dict[str, Any]:
        if self._protection.state != "unarmed":
            return {"success": False, "error": "Фоновые прямые проверки отключены при защите"}

        """Параллельный замер задержки всех серверов с доопределением неизвестных гео."""
        with self._lock:
            proxies_copy = list(self.proxies)

        def _ping_and_geo(p):
            lat = quick_ping_proxy(p, timeout=2.5)
            if not p.country or p.get_country_code() == "PX":
                c, cc, city = resolve_host_geo(p.host, timeout=2.0)
                if c or cc != "PX":
                    p.country = c
                    p.country_code = cc if cc != "PX" else ""
                    p.city = city
            return lat

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(_ping_and_geo, proxies_copy))

        with self._lock:
            try:
                self._save()
            except Exception as e:
                import logging
                logging.getLogger("ProxyTUN").warning("Ошибка сохранения после ping_all: %s", e)
            return {
                "success": True,
                "proxies": [self._proxy_to_dict(p) for p in self.proxies]
            }

    def refresh_system_ip(self) -> Dict[str, Any]:
        """Принудительное обновление внешнего IP."""
        self._refresh_ip_async()
        with self._lock:
            return self.current_system_ip

    def _network_warning(self):
        # Read only the enable flag; never export configured proxy endpoints.
        now = time.monotonic()
        if now-getattr(self,'_proxy_warning_checked',-100)>10:
            warning = ''
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                    enabled,_ = winreg.QueryValueEx(key,'ProxyEnable')
                if enabled:
                    warning = 'Включён системный прокси Windows: он может мешать TUN и скрывать имена сайтов. Для TUN отключите прежний прокси Windows или расширение браузера вручную.'
            except (ImportError,OSError):
                pass
            self._proxy_warning_checked = now
            self._proxy_warning = warning
        return self._proxy_warning

    def copy_proxy_by_id(self, proxy_id: str) -> Dict[str, Any]:
        """Копирует строку прокси в буфер обмена Windows через clip.exe без передачи пароля в JS."""
        with self._lock:
            p = next((x for x in self.proxies if x.id == proxy_id), None)
            if p:
                raw = p.get_raw_line()
                try:
                    subprocess.run(
                        [sys_exe("clip.exe")],
                        input=raw.encode("utf-16"),
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    return {"success": True}
                except Exception:
                    pass
        return {"success": False}

    def copy_to_clipboard(self, text: str) -> Dict[str, Any]:
        """Безопасное копирование произвольного текста в буфер обмена Windows через clip.exe."""
        try:
            subprocess.run(
                [sys_exe("clip.exe")],
                input=text.encode("utf-16"),
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
        except Exception:
            pass
        return {"success": True}

    def get_settings(self) -> Dict[str, Any]:
        """Возвращает текущие настройки приложения."""
        with self._lock:
            return dict(self.settings)

    def set_bypass_telegram(self, enabled: bool) -> Dict[str, Any]:
        return {"success": False, "error": "Прямые исключения отключены в защищённом режиме", "bypass_telegram": False}

    def shutdown(self):
        """Гарантированная остановка сетевой службы при закрытии приложения."""
        with self._lock:
            self._protection.cancel.set()
            self._closing = True
            self._op_generation=getattr(self,'_op_generation',0)+1
        self._journal.clear()
        if hasattr(self, "_geo_pool"):
            try:
                self._geo_pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                self._geo_pool.shutdown(wait=False)
            except Exception:
                pass
        with self._op_lock:
            try:
                self._protection.stop()
            finally:
                self._journal.clear()


_single_instance_mutex = None

def check_single_instance() -> bool:
    """Гарантирует запуск только одного экземпляра ProxyTUN в системе."""
    global _single_instance_mutex
    if os.name != 'nt':
        return True
    try:
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = wintypes.HANDLE
        _single_instance_mutex = k32.CreateMutexW(None, False, "Global\\ProxyTUN_SingleInstance_Mutex")
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            return False
    except Exception:
        pass
    return True


def start_app():
    """Точка входа запуска графического приложения на базе WebView2."""
    if not check_single_instance():
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "KROTTUN уже запущен!", "KROTTUN", 0x40 | 0x0)
        except Exception:
            pass
        sys.exit(0)

    # Привязываем сам процесс к Windows Job Object (все дочерние процессы закрываются с ним)
    bind_self_to_job()

    try:
        api = ProxyTunBridgeApi()
    except Exception as e:
        import logging
        logging.critical("Fatal init error", exc_info=True)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"KROTTUN не может быть запущен:\n\n{e}\n\nПодробности: %ProgramData%\\ProxyTUN\\logs\\proxytun.log",
                "KROTTUN — ошибка безопасности",
                0x10
            )
        except Exception:
            pass
        sys.exit(1)

    html_content = get_html_content()

    window = webview.create_window(
        title=f"KROTTUN — v{APP_VERSION}",
        html=html_content,
        js_api=api,
        width=520,
        height=760,
        resizable=False,
        background_color="#070d1a"
    )

    api.set_window(window)

    try:
        webview.start(debug=False)
    finally:
        # Гарантированное завершение сетевой службы в главном потоке после закрытия окна
        api.shutdown()
