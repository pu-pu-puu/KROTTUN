import time
import requests
import re
from typing import Dict, Any, Optional, Tuple
from core.proxy_model import ProxyItem

def get_current_system_ip(timeout: float = 4.0) -> Dict[str, Any]:
    """Получает текущий внешний IP-адрес системы с защитой от кэширования."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Connection": "close",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    t = int(time.time() * 1000)

    # 1. Попробуем ipwho.is с параметром антикэша
    try:
        resp = requests.get(f"https://ipwho.is/?_t={t}", headers=headers, proxies={"http": None, "https": None}, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success", True):
                return {
                    "ip": data.get("ip", "Unknown"),
                    "country": data.get("country", ""),
                    "country_code": data.get("country_code", ""),
                    "city": data.get("city", ""),
                    "isp": data.get("connection", {}).get("isp", "") or data.get("isp", "")
                }
    except Exception:
        pass

    # 2. Быстрый гео-сервис ip-api.com
    try:
        resp = requests.get(f"http://ip-api.com/json/?_t={t}", headers=headers, proxies={"http": None, "https": None}, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return {
                    "ip": data.get("query", "Unknown"),
                    "country": data.get("country", ""),
                    "country_code": data.get("countryCode", ""),
                    "city": data.get("city", ""),
                    "isp": data.get("isp", "")
                }
    except Exception:
        pass

    # 3. Быстрый и безотказный api.ipify.org
    try:
        resp = requests.get(f"https://api.ipify.org?format=json&_t={t}", headers=headers, proxies={"http": None, "https": None}, timeout=timeout)
        if resp.status_code == 200:
            return {
                "ip": resp.json().get("ip", "Unknown"),
                "country": "",
                "country_code": "",
                "city": "",
                "isp": ""
            }
    except Exception:
        pass

    # 4. Дополнительный fallback - httpbin.org
    try:
        resp = requests.get(f"https://httpbin.org/ip?_t={t}", headers=headers, proxies={"http": None, "https": None}, timeout=timeout)
        if resp.status_code == 200:
            ip_val = resp.json().get("origin", "Unknown").split(",")[0].strip()
            return {
                "ip": ip_val,
                "country": "",
                "country_code": "",
                "city": "",
                "isp": ""
            }
    except Exception:
        pass

    return {
        "ip": "Не удалось определить",
        "country": "",
        "country_code": "",
        "city": "",
        "isp": ""
    }


def test_proxy(proxy: ProxyItem, timeout: float = 5.0) -> Tuple[bool, Optional[int], str, str]:
    """
    Проверяет работоспособность прокси, измеряет задержку и определяет страну выхода.
    """
    from urllib.parse import quote
    proto = "socks5h" if proxy.protocol.lower() == "socks5" else "http"
    if proxy.username:
        u_enc = quote(proxy.username, safe="")
        p_enc = quote(proxy.password or "", safe="")
        proxy_url = f"{proto}://{u_enc}:{p_enc}@{proxy.host}:{proxy.port}"
    else:
        proxy_url = f"{proto}://{proxy.host}:{proxy.port}"

    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }

    t = int(time.time() * 1000)
    headers = {"Connection": "close"}
    start = time.time()

    # Быстрый чек через api.ipify.org
    try:
        resp = requests.get(f"https://api.ipify.org?format=json&_t={t}", proxies=proxies, headers=headers, timeout=timeout)
        latency = int((time.time() - start) * 1000)
        if resp.status_code == 200:
            proxy.latency_ms = latency
            proxy.last_status = "alive"

            # Попробуем доопределить гео
            try:
                g = requests.get(f"https://ipwho.is/?_t={t}", proxies=proxies, headers=headers, timeout=3.0).json()
                proxy.country = g.get("country", "")
                proxy.city = g.get("city", "")
                proxy.country_code = (g.get("country_code") or "").upper()
            except Exception:
                if not proxy.country:
                    proxy.country = "OK"

            return True, latency, proxy.country, proxy.city
    except Exception:
        pass

    proxy.latency_ms = None
    proxy.last_status = "dead"
    return False, None, "", ""


def quick_ping_proxy(proxy: ProxyItem, timeout: float = 2.5) -> Optional[int]:
    """Быстрый замер задержки TCP до сервера прокси с безопасным закрытием сокета."""
    import socket
    start = time.perf_counter()
    try:
        with socket.create_connection((proxy.host, proxy.port), timeout=timeout):
            lat = int((time.perf_counter() - start) * 1000)
    except OSError:
        lat = None

    proxy.latency_ms = lat
    proxy.last_status = "alive" if lat is not None else "dead"
    return lat


_geo_cache: Dict[str, Tuple[str, str, str]] = {}

def _clean_geo_str(s: Any) -> str:
    """Очищает строку геоданных от спецсимволов HTML, управляющих кодов и ограничивает длину."""
    if not s:
        return ""
    text = str(s).strip()
    # Убираем любые скобки, кавычки, слэши, теги HTML
    clean = re.sub(r"[<>&\"\'/\\]", "", text).strip()
    return clean[:50]

def _clean_code(c: Any) -> str:
    """Строго валидирует ISO код страны или служебный код."""
    if not c:
        return "PX"
    code = str(c).strip().upper()
    if code in ("LAN", "LOC", "UNK", "PX"):
        return code
    if len(code) == 2 and code.isalpha():
        return code
    return "PX"

import threading
import queue
import socket
import ipaddress


def _resolve_ip_with_timeout(host: str, timeout: float = 1.0) -> str:
    """Безопасно и с жестким ограничением по времени разрешает имя хоста в IP адрес через daemon-поток."""
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host) or ":" in host:
        return host

    res_q: queue.Queue = queue.Queue()

    def _worker():
        try:
            ip = socket.gethostbyname(host)
            res_q.put(ip)
        except Exception:
            res_q.put(host)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    try:
        return res_q.get(timeout=max(0.05, timeout))
    except queue.Empty:
        return host


def resolve_host_geo(host: str, timeout: float = 2.5) -> Tuple[str, str, str]:
    """
    Быстро определяет страну, 2-буквенный код страны и город по адресу/домену прокси.
    Возвращает (country, country_code, city). Результаты кэшируются в памяти.
    Использует ИСКЛЮЧИТЕЛЬНО шифрованные HTTPS сервисы и общий монотонный deadline.
    """
    h = re.sub(r"[<>&\"\'/\\]", "", host or "").strip()
    if not h:
        return "", "PX", ""

    if h in _geo_cache:
        return _geo_cache[h]

    deadline = time.monotonic() + timeout

    rem_dns = max(0.1, deadline - time.monotonic())
    ip = _resolve_ip_with_timeout(h, timeout=min(1.0, rem_dns))

    # Локальные/приватные IP
    if ip.startswith(("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.",
                      "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                      "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.")):
        res = ("Local Network", "LAN", "Local")
        _geo_cache[h] = res
        return res

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Connection": "close"
    }

    # 1. Приоритетный HTTPS сервис freeipapi.com
    rem = deadline - time.monotonic()
    if rem > 0.2:
        try:
            r = requests.get(
                f"https://freeipapi.com/api/json/{ip}",
                headers=headers,
                proxies={"http": None, "https": None},
                timeout=min(1.2, rem)
            )
            if r.status_code == 200:
                d = r.json()
                country = _clean_geo_str(d.get("countryName"))
                code = _clean_code(d.get("countryCode"))
                city = _clean_geo_str(d.get("cityName"))
                if country or code != "PX":
                    res = (country, code, city)
                    _geo_cache[h] = res
                    return res
        except Exception:
            pass

    # 2. Резервный HTTPS сервис ipwho.is
    rem = deadline - time.monotonic()
    if rem > 0.2:
        try:
            r = requests.get(
                f"https://ipwho.is/{ip}",
                headers=headers,
                proxies={"http": None, "https": None},
                timeout=min(1.2, rem)
            )
            if r.status_code == 200:
                d = r.json()
                if d.get("success", True) and d.get("country"):
                    country = _clean_geo_str(d.get("country"))
                    code = _clean_code(d.get("country_code"))
                    city = _clean_geo_str(d.get("city"))
                    res = (country, code, city)
                    _geo_cache[h] = res
                    return res
        except Exception:
            pass

    return "", "PX", ""


def probe_proxy_protocol(host: str, port: int, timeout: float = 2.0) -> Optional[str]:
    """
    Быстро зондирует сокет для автоматического определения протокола прокси (socks5 или http).
    - Разрешает DNS с жестким ограничением времени до открытия сокетов.
    - Зондирует SOCKS5 handshake и HTTP CONNECT параллельно, исключая зависание на HTTP серверах.
    - Обрабатывает фрагментированные TCP-ответы.
    - Корректно определяет SOCKS5 (методы 00, 01, 02 и ответ 0xFF) и HTTP CONNECT (статусы 200/2xx и 407).
    - Ограничен общим монотонным дедлайном.
    """
    deadline = time.monotonic() + timeout
    h = (host or "").strip()
    if not h or port <= 0 or port > 65535:
        return None

    # 1. Разрешаем домен в IP с ограниченным тайм-аутом
    try:
        ipaddress.ip_address(h)
        target_ip = h
    except ValueError:
        rem_dns = max(0.05, min(0.6, (deadline - time.monotonic()) * 0.4))
        resolved = _resolve_ip_with_timeout(h, timeout=rem_dns)
        try:
            ipaddress.ip_address(resolved)
            target_ip = resolved
        except ValueError:
            # Не удалось разрешить домен в IP за отведенное время
            return None

    rem = deadline - time.monotonic()
    if rem < 0.15:
        return None

    result_queue: queue.Queue = queue.Queue()

    def _probe_socks():
        s = None
        try:
            cur_rem = max(0.05, deadline - time.monotonic())
            s = socket.create_connection((target_ip, int(port)), timeout=cur_rem)
            s.sendall(b"\x05\x02\x00\x02")
            resp = b""
            while len(resp) < 2 and time.monotonic() < deadline:
                r_timeout = max(0.05, deadline - time.monotonic())
                s.settimeout(r_timeout)
                chunk = s.recv(2 - len(resp))
                if not chunk:
                    break
                resp += chunk
            if len(resp) == 2 and resp[0] == 0x05 and resp[1] in (0x00, 0x01, 0x02, 0xFF):
                result_queue.put("socks5")
        except Exception:
            pass
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass

    def _probe_http():
        s = None
        try:
            cur_rem = max(0.05, deadline - time.monotonic())
            s = socket.create_connection((target_ip, int(port)), timeout=cur_rem)
            r_timeout = max(0.05, deadline - time.monotonic())
            s.settimeout(r_timeout)
            s.sendall(b"CONNECT 1.1.1.1:443 HTTP/1.1\r\nHost: 1.1.1.1:443\r\nProxy-Connection: keep-alive\r\n\r\n")
            resp = b""
            while b"\r\n" not in resp and len(resp) < 256 and time.monotonic() < deadline:
                r_timeout = max(0.05, deadline - time.monotonic())
                s.settimeout(r_timeout)
                chunk = s.recv(256 - len(resp))
                if not chunk:
                    break
                resp += chunk
            if resp.startswith((b"HTTP/1.0", b"HTTP/1.1")):
                parts = resp.split(b" ", 2)
                if len(parts) >= 2:
                    try:
                        code_str = parts[1].strip()
                        if len(code_str) == 3 and code_str.isdigit():
                            code = int(code_str)
                            # Только успешный туннель (200 / 2xx) или запрос аутентификации прокси (407)
                            # Обычные веб-ответы (400, 403, 404, 405 Method Not Allowed) и ошибки не являются прокси
                            if code == 200 or (200 <= code < 300) or code == 407:
                                result_queue.put("http")
                                return
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass

    t_socks = threading.Thread(target=_probe_socks, daemon=True)
    t_http = threading.Thread(target=_probe_http, daemon=True)

    t_socks.start()
    t_http.start()

    wait_time = max(0.05, deadline - time.monotonic())
    try:
        return result_queue.get(timeout=wait_time)
    except queue.Empty:
        return None

