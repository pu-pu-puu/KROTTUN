import time
import requests
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
            except Exception:
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
