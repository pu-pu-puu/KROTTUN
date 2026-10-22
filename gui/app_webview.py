import os
import sys
import time
import threading
import subprocess
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

        self.is_admin = is_admin()
        self.connected_since: Optional[float] = None
        self.current_system_ip: Dict[str, Any] = {"ip": "Загрузка...", "country_code": ""}

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
        self._protection.cancel.set()
        with self._op_lock:
            try:
                self._protection.release()
                self._state = TunState.IDLE
                return {"success": True}
            except Exception:
                return {"success": False, "error": "Не удалось снять защиту Windows; используйте локальное восстановление"}

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

        c, cc, city = resolve_host_geo(host, timeout=3.0)
        if self._closing:
            return

        with self._lock:
            if self._closing:
                return
            p = next((x for x in self.proxies if x.id == proxy_id), None)
            if p and (c or (cc and cc != "PX")):
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
            c, cc, city = resolve_host_geo(host, timeout=3.0)
            if self._closing:
                return
            with self._lock:
                if self._closing:
                    return
                p = next((x for x in self.proxies if x.id == pid), None)
                if p and (c or (cc and cc != "PX")):
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

    def _refresh_ip_async(self):
        if hasattr(self, "_protection") and self._protection.state != "unarmed":
            return

        """Асинхронный опрос IP с защитой поколения от устаревших ответов."""
        with self._lock:
            self._ip_gen += 1
            current_gen = self._ip_gen

        def _worker():
            for delay in (0.8, 2.0):
                time.sleep(delay)
                with self._lock:
                    if current_gen != self._ip_gen or self._closing:
                        return
                    is_run = self._sb.is_running()

                data = get_current_system_ip(timeout=3.0)
                ip_val = data.get("ip", "")
                if ip_val and ip_val not in ("Unknown", "Не удалось определить"):
                    country_code = (data.get("country_code") or "").upper().strip()
                    if not country_code and is_run:
                        with self._lock:
                            act = self._sb.active_proxy
                            if act and act.get_country_code():
                                country_code = act.get_country_code()

                    with self._lock:
                        if current_gen == self._ip_gen and not self._closing:
                            self.current_system_ip = {
                                "ip": ip_val,
                                "country_code": country_code,
                                "country": data.get("country", "")
                            }
                    return

        threading.Thread(target=_worker, daemon=True).start()

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
                    current = self._sb.active_proxy.id if self._sb.active_proxy else None
                    with self._lock:
                        candidates = [p for p in self.proxies if p.id != current]
                        self._state = TunState.STARTING
                    success = self._protection.connect(candidates)
                    with self._lock:
                        self._state = TunState.RUNNING if success else TunState.ERROR
                        self._last_error = None if success else "Интернет заблокирован: резервные серверы недоступны"
                        self.connected_since = time.time() if success else None
                        if not success: self._error_seq += 1
            except Exception:
                with self._lock:
                    self._state = TunState.ERROR
                    self._last_error = "Ошибка защиты Windows; подключение остановлено"
                    self._error_seq += 1
                self._sb.stop()
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

        # Точный подсчет скорости конкретно интерфейса sing-tun
        if psutil is not None:
            try:
                pernic = psutil.net_io_counters(pernic=True)
                tun_stat = pernic.get("sing-tun") or pernic.get("ProxyTUN")
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
            if self._closing:
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
                self._state = TunState.STARTING
                target = "start"

            threading.Thread(target=self._do_toggle, args=(target,), daemon=True).start()
            return {"success": True, "state": self._state}

    def _do_toggle(self, target: str):
        """Выполняет длинные операции запуска/остановки без удержания _lock."""
        with self._op_lock:
            with self._lock:
                if self._closing:
                    return
                sel = self._get_selected_proxy()
                if target == "start" and not sel:
                    self._state = TunState.ERROR
                    self._last_error = "Список серверов пуст. Выберите или добавьте прокси!"
                    self._error_seq += 1
                    return
                bypass_tg = bool(self.settings.get("bypass_telegram", False))

            try:
                if target == "start":
                    if sel:
                        with self._lock:
                            candidates = [sel] + [p for p in self.proxies if p.id != sel.id]
                        success = self._protection.connect(candidates)
                        with self._lock:
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
                self._sb.stop()
                self._protection.state = "unknown"
                with self._lock:
                    self._state = TunState.ERROR
                    self._last_error = "Ошибка установки или проверки защиты Windows; TUN остановлен"
                    self._error_seq += 1
                    self.connected_since = None

        self._refresh_ip_async()

    def select_proxy(self, proxy_id: str) -> Dict[str, Any]:
        """Выбор активного сервера с безопасным перезапуском."""
        with self._lock:
            if self._closing or self._state in (TunState.STARTING, TunState.STOPPING):
                return {"success": False, "busy": True}

            changed = (proxy_id != self.selected_proxy_id)
            self.selected_proxy_id = proxy_id
            sel = self._get_selected_proxy()

            if changed and self._state == TunState.RUNNING and sel:
                self._state = TunState.STARTING
                threading.Thread(target=self._do_toggle, args=("start",), daemon=True).start()

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
        self._journal.clear()
        if hasattr(self, "_geo_pool"):
            try:
                self._geo_pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                self._geo_pool.shutdown(wait=False)
            except Exception:
                pass
        with self._op_lock:
            self._protection.stop()
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
        title="KROTTUN — L3 TUN Proxy Manager",
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
