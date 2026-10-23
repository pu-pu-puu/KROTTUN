from __future__ import annotations

import os
import sys
import json
import subprocess
import time
import socket
import ipaddress
import threading
import logging
import uuid
from typing import Optional, List, Tuple
from core.proxy_model import ProxyItem
from core.admin_utils import is_admin
from core.win_job import bind_to_lifetime
from core.paths import (
    sys_exe,
    get_secure_bin_dir,
    get_log_dir,
    verify_file_sha256,
    PINNED_HASHES
)

try:
    import psutil
except ImportError:
    psutil = None

class IntegrityError(RuntimeError):
    """Исключение при нарушении целостности исполняемых файлов."""
    pass

def _resolve_v4(host: str) -> List[str]:
    """Разрешает доменное имя прокси в список IPv4 адресов для прямого маршрута."""
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            return sorted({ai[4][0] for ai in socket.getaddrinfo(host, None, socket.AF_INET)})
        except Exception:
            return []

_console_lock = threading.Lock()

class SingBoxManager:
    @property
    def interface_name(self) -> str:
        if not getattr(self,'_interface_name',None):
            self._interface_name='sing-tun-'+uuid.uuid4().hex
        return self._interface_name

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            if getattr(sys, 'frozen', False):
                self.base_dir = os.path.dirname(sys.executable)
            else:
                self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.base_dir = base_dir

        # Защищенный каталог бинарников в %ProgramData%\ProxyTUN\bin (ACL Administrators only, Users RX)
        self.bin_dir = get_secure_bin_dir()
        self.log_dir = get_log_dir()

        self.exe_path = os.path.join(self.bin_dir, "sing-box.exe")
        self.wintun_path = os.path.join(self.bin_dir, "wintun.dll")
        self.log_path = os.path.join(self.log_dir, "sing-box.log")
        self.stderr_path = os.path.join(self.log_dir, "sing-box.stderr.log")

        self.process: Optional[subprocess.Popen] = None
        self.active_proxy: Optional[ProxyItem] = None
        self.proxy_reachable: bool = False
        self.err_file = None
        self.protected = False
        self.on_tunnel_ready = None

        # Установка и проверка целостности бинарников
        for fname in PINNED_HASHES:
            self._install_binary(fname)

    def _install_binary(self, fname: str) -> None:
        """Копирует бинарник во временный файл в защищенном каталоге, проверяет копию и подменяет."""
        pinned = PINNED_HASHES.get(fname)
        if not pinned:
            return
        dst = os.path.join(self.bin_dir, fname)
        if verify_file_sha256(dst, pinned):
            return

        meipass = getattr(sys, "_MEIPASS", None)
        src = os.path.join(meipass, "bin", fname) if meipass else os.path.join(self.base_dir, "bin", fname)
        if not os.path.exists(src):
            src = os.path.join(self.base_dir, "bin", fname)

        if not os.path.exists(src):
            raise IntegrityError(f"Исходный файл {fname} не найден в дистрибутиве.")

        tmp = dst + ".new"
        try:
            import shutil
            shutil.copyfile(src, tmp)
            # Проверяем КОПИЮ внутри защищенного каталога (защита от TOCTOU в %TEMP%)
            if not verify_file_sha256(tmp, pinned):
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise IntegrityError(f"Целостность {fname} нарушена (хеш не совпал) — запуск отменён!")
            os.replace(tmp, dst)
        except Exception:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
            raise

    def _verify_or_raise(self) -> None:
        """Проверяет SHA-256 хеши всех бинарников перед каждым запуском."""
        for fname, pinned in PINNED_HASHES.items():
            p = os.path.join(self.bin_dir, fname)
            if not verify_file_sha256(p, pinned):
                raise IntegrityError(f"Целостность бинарника {fname} нарушена — запуск отменён!")

    def flush_dns(self):
        """Сбрасывает системный кэш DNS Windows через System32."""
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            subprocess.run([sys_exe("ipconfig.exe"), "/flushdns"], capture_output=True, creationflags=flags)
        except Exception:
            pass

    def generate_config(self, proxy: ProxyItem, bypass_telegram: bool = False) -> dict:
        """
        Генерирует проверенную конфигурацию sing-box:
        - strict_route: False и исключение подсетей для совместимости с локальными службами Windows
        - Обход для локальных сервисов обхода цензуры (ag_dns, xray, AGUnlocker)
        - Опциональный обход Telegram.exe
        - Уровень логирования 'warn' для защиты приватности
        """
        proto = (proxy.protocol or "socks5").lower().strip()
        if proto == "socks5":
            proto_type = "socks"
        elif proto == "http":
            proto_type = "http"
        else:
            raise ValueError(f"Неподдерживаемый протокол прокси: '{proxy.protocol}'. Допустимы только 'socks5' и 'http'.")

        outbound_proxy = {
            "type": proto_type,
            "tag": "proxy-out",
            "server": proxy.host,
            "server_port": proxy.port
        }
        if proxy.username:
            outbound_proxy["username"] = proxy.username
        if proxy.password:
            outbound_proxy["password"] = proxy.password

        resolved_ips = _resolve_v4(proxy.host)
        proxy_ip_cidrs = [f"{ip}/32" for ip in resolved_ips] if resolved_ips else []

        route_rules = [
            {"protocol": "dns", "action": "hijack-dns"},
            {"ip_version": 6, "action": "reject"}
        ]

        # Для HTTP-прокси UDP не поддерживается протоколом — отклоняем с RST для мгновенного перехода приложений на TCP
        if proto_type == "http":
            route_rules.append({"network": "udp", "action": "reject"})
        else:
            route_rules.append({"network": "udp", "port": [443], "action": "reject"})

        if proxy_ip_cidrs:
            route_rules.append({
                "ip_cidr": proxy_ip_cidrs,
                "outbound": "direct"
            })
        else:
            route_rules.append({
                "domain": [proxy.host],
                "outbound": "direct"
            })

        # Маршруты прямого выхода для системных служб обхода и локальных портов
        route_rules.append({
            "process_name": [
                "xray.exe",
                "AG_2.21.1.exe",
                "ag_dns.exe"
            ],
            "outbound": "direct"
        })

        if bypass_telegram:
            route_rules.append({
                "process_name": ["Telegram.exe"],
                "outbound": "direct"
            })

        route_rules.append({
            "ip_cidr": [
                "127.0.0.0/8"
            ],
            "outbound": "direct"
        })
        route_rules.append({"domain": ["localhost"], "outbound": "direct"})
        route_rules.append({"ip_is_private": True, "outbound": "direct"})

        norm_log_path = self.log_path.replace("\\", "/")

        config = {
            "log": {
                "level": "warn",
                "output": norm_log_path,
                "timestamp": True
            },
            "dns": {
                "servers": [
                    {
                        "tag": "dns-remote-cf",
                        "type": "https",
                        "server": "1.1.1.1",
                        "detour": "proxy-out"
                    },
                    {
                        "tag": "dns-remote-google",
                        "type": "https",
                        "server": "8.8.8.8",
                        "detour": "proxy-out"
                    },
                    {
                        "tag": "dns-remote-tcp",
                        "type": "tcp",
                        "server": "1.1.1.1",
                        "detour": "proxy-out"
                    },
                    {
                        "tag": "dns-direct",
                        "type": "local",
                        "detour": "direct"
                    }
                ],
                "rules": [
                    {"domain": ["localhost"], "action": "route", "server": "dns-direct"},
                    {"domain_suffix": [".local", ".lan", ".home", ".home.arpa"], "action": "route", "server": "dns-direct"},
                    # Tier 1: Cloudflare DoH
                    {"action": "evaluate", "server": "dns-remote-cf", "tag": "cf_resp"},
                    {"match_response": "cf_resp", "response_rcode": "NOERROR", "action": "respond"},
                    # Tier 2: Google DoH
                    {"action": "evaluate", "server": "dns-remote-google", "tag": "google_resp"},
                    {"match_response": "google_resp", "response_rcode": "NOERROR", "action": "respond"},
                    # Tier 3: TCP DNS
                    {"action": "route", "server": "dns-remote-tcp"}
                ],
                "final": "dns-remote-tcp",
                "strategy": "ipv4_only"
            },
            "inbounds": [
                {
                    "type": "tun",
                    "tag": "tun-in",
                    "interface_name": self.interface_name,
                    "address": ["198.18.0.1/30"],
                    "auto_route": True,
                    "strict_route": False,
                    "stack": "gvisor",
                    "route_exclude_address": [
                        "127.0.0.0/8",
                        "10.0.0.0/8",
                        "172.16.0.0/12",
                        "192.168.0.0/16"
                    ]
                }
            ],
            "outbounds": [
                outbound_proxy,
                {"type": "direct", "tag": "direct"}
            ],
            "route": {
                "rules": route_rules,
                "find_process": True,
                "auto_detect_interface": True,
                "default_domain_resolver": "dns-direct"
            }
        }

        if getattr(self, "protected", False):
            # The outer socket is permitted by WFP, never by a broad direct route.
            ipaddress.ip_address(proxy.host)
            config["inbounds"][0]["strict_route"] = True
            config["inbounds"][0]["route_exclude_address"] = ["127.0.0.0/8"]
            config["route"]["rules"] = [r for r in route_rules if r.get("outbound") != "direct"]
            config["route"]["rules"].append({"network": "udp", "action": "reject"})
            config["route"]["final"] = "proxy-out"
            config["route"].pop("default_domain_resolver", None)
            config["dns"]["servers"] = [x for x in config["dns"]["servers"] if x["tag"] != "dns-direct"]
            config["dns"]["rules"] = [x for x in config["dns"]["rules"] if x.get("server") != "dns-direct"]
            config["outbounds"] = [outbound_proxy]
            import secrets
            self.controller_secret = secrets.token_urlsafe(32)
            self.controller_port = 49152 + secrets.randbelow(16384)
            config["experimental"] = {"clash_api": {
                "external_controller": "127.0.0.1:" + str(self.controller_port),
                "secret": self.controller_secret}}
        return config

    def is_adapter_present(self, name: Optional[str] = None) -> bool:
        """Проверяет наличие сетевого интерфейса через psutil без запуска процессов netsh."""
        name = self.interface_name if name is None else name
        if psutil is not None:
            try:
                return name in psutil.net_if_stats()
            except Exception:
                pass
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            res = subprocess.run(
                [sys_exe("netsh.exe"), "interface", "show", "interface", name],
                capture_output=True,
                creationflags=flags,
                timeout=1.0
            )
            return res.returncode == 0
        except Exception:
            return False

    def is_running(self) -> bool:
        """Только чтение состояния процесса без мутации (M2)."""
        p = self.process
        return p is not None and p.poll() is None

    def _graceful_stop(self, p: subprocess.Popen, timeout: float = 3.0) -> bool:
        """Синхронно посылает сигнал CTRL_C и ожидает выхода без гонки Timer."""
        try:
            import ctypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            with _console_lock:
                k32.FreeConsole()
                if not k32.AttachConsole(p.pid):
                    return False
                try:
                    k32.SetConsoleCtrlHandler(None, True)
                    if not k32.GenerateConsoleCtrlEvent(0, 0):
                        return False
                    try:
                        p.wait(timeout=timeout)
                        return True
                    except subprocess.TimeoutExpired:
                        return False
                finally:
                    k32.FreeConsole()
                    k32.SetConsoleCtrlHandler(None, False)
        except Exception:
            pass
        return False

    def stop(self):
        """Останавливает только свой процесс sing-box с корректной выгрузкой Wintun."""
        p = self.process
        if p and p.poll() is None:
            stopped = False
            try:
                stopped = self._graceful_stop(p, timeout=3.0)
            except Exception:
                pass

            if not stopped and p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=1.5)
                except Exception:
                    try:
                        p.kill()
                        p.wait(timeout=1.0)
                    except Exception:
                        pass

        # Keep ownership and protection intact unless exit is observable.
        if p is not None and p.poll() is None:
            raise RuntimeError("sing-box did not exit; protection retained")
        self.process = None

        if self.err_file and not self.err_file.closed:
            try:
                self.err_file.close()
            except Exception:
                pass
            self.err_file = None

        # Ожидаем полного освобождения драйвера Wintun стеком Windows
        start_wait = time.time()
        while time.time() - start_wait < 2.5:
            if not self.is_adapter_present():
                break
            time.sleep(0.05)

        self.active_proxy = None
        self.proxy_reachable = False
        self.flush_dns()

    def _wait_ready(self, p: subprocess.Popen, timeout: float = 15.0) -> bool:
        """
        Надежная проверка готовности адаптера (M1):
        Проверка IP текущего интерфейса и отсутствия ошибок в логе.
        """
        deadline = time.monotonic() + timeout
        has_ip = False
        while time.monotonic() < deadline:
            if p.poll() is not None:
                return False

            if psutil is not None:
                addrs = psutil.net_if_addrs().get(self.interface_name, [])
                if any(getattr(a, "address", "") == "198.18.0.1" for a in addrs):
                    has_ip = True
                    break
            elif self.is_adapter_present():
                has_ip = True
                break

            if os.path.exists(self.log_path):
                try:
                    with open(self.log_path, "r", encoding="utf-8", errors="ignore") as lf:
                        content = lf.read()
                        if "FATAL" in content or "panic" in content:
                            return False
                except Exception:
                    pass
            time.sleep(0.1)

        return has_ip

    def _probe_tunnel(self, p: subprocess.Popen, deadline: float, endpoints: Optional[List[Tuple[str, str]]] = None) -> bool:
        """
        Проверяет доступность интернета через поднятый туннель (R2/R6).
        Строго различает типы ответов: 204 без редиректа для generate_204 и тело 'success' для Firefox.
        Исключает ложное срабатывание при перехвате captive portal / заглушкой провайдера.
        """
        import requests
        targets = endpoints or [
            ("https://cp.cloudflare.com/generate_204", "204"),
            ("https://www.gstatic.com/generate_204", "204"),
            ("http://cp.cloudflare.com/generate_204", "204"),
            ("http://detectportal.firefox.com/success.txt", "firefox_success"),
        ]
        with requests.Session() as s:
            s.trust_env = False
            while time.monotonic() < deadline and p.poll() is None:
                for url, check_type in targets:
                    rem = deadline - time.monotonic()
                    if rem <= 0.1 or p.poll() is not None:
                        break
                    req_timeout = min(1.5, rem)
                    try:
                        resp = s.get(url, timeout=req_timeout, allow_redirects=False)
                        if check_type == "204" and resp.status_code == 204:
                            return True
                        elif check_type == "firefox_success" and resp.status_code == 200:
                            if resp.text.strip() == "success":
                                return True
                    except requests.RequestException:
                        pass
                    except Exception:
                        pass
                time.sleep(0.2)
        return False

    def start(self, proxy: ProxyItem, bypass_telegram: bool = False) -> bool:
        """Запускает TUN подключение с передачей конфига через stdin и проверкой SHA-256."""
        if not is_admin():
            raise PermissionError("Для создания TUN сетевого адаптера требуются права Администратора Windows.")

        self.stop()

        # Гарантированное ожидание освобождения старого адаптера Wintun
        start_wait = time.time()
        while time.time() - start_wait < 3.0:
            if not self.is_adapter_present():
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("Wintun адаптер ещё не освобождён системой. Подождите пару секунд и повторите.")

        # sing-box derives the Windows adapter GUID from its name. Never reuse
        # a crashed core's stale native identity; old process exit is confirmed
        # by stop() before rotating this exact adapter identity.
        self._interface_name='sing-tun-'+uuid.uuid4().hex
        config_data = self.generate_config(proxy, bypass_telegram=bypass_telegram)
        cfg_bytes = json.dumps(config_data, ensure_ascii=False).encode("utf-8")

        # Очищаем старый лог перед новым запуском
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, "w", encoding="utf-8") as lf:
                    lf.write("")
        except Exception:
            pass

        try:
            self.err_file = open(self.stderr_path, "wb")
        except Exception:
            self.err_file = None

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE

        # Обязательная проверка целостности непосредственно перед запуском Popen (R1: устранение окна TOCTOU)
        self._verify_or_raise()

        # Запуск с передачей конфигурации через stdin (пароль не касается диска)
        p = subprocess.Popen(
            [self.exe_path, "run", "-c", "stdin"],
            cwd=self.bin_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=self.err_file if self.err_file else subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            startupinfo=si
        )
        self.process = p

        # Передаем конфигурацию в stdin и закрываем поток
        try:
            p.stdin.write(cfg_bytes)
            p.stdin.flush()
            p.stdin.close()
        except Exception as e:
            self.stop()
            raise RuntimeError(f"Не удалось передать конфиг в sing-box через stdin: {e}")
        finally:
            del cfg_bytes

        self.active_proxy = proxy

        # Ожидание готовности (проверка поднятия адаптера и IP)
        ready = self._wait_ready(p, timeout=15.0)

        if not ready or p.poll() is not None:
            err_msg = ""
            if os.path.exists(self.stderr_path):
                try:
                    with open(self.stderr_path, "r", encoding="utf-8", errors="ignore") as ef:
                        err_msg = ef.read().strip()
                except Exception:
                    pass
            if not err_msg and os.path.exists(self.log_path):
                try:
                    with open(self.log_path, "r", encoding="utf-8", errors="ignore") as lf:
                        err_msg = lf.read().strip()
                except Exception:
                    pass

            self.stop()
            raise RuntimeError(f"Не удалось инициализировать TUN-адаптер sing-box:\n{err_msg or 'Ошибка запуска службы'}")

        if self.on_tunnel_ready is not None:
            self.on_tunnel_ready()

        # Проверка фактической доступности прокси через поднятый туннель (R2)
        self.proxy_reachable = self._probe_tunnel(p, deadline=time.monotonic() + 6.0)

        return True
