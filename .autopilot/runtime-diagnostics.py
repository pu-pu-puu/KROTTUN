"""Read-only local diagnostics. Never export proxy addresses or credentials."""
import ctypes
import json
import re
import sys
import winreg
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
report = {'ok': False, 'phase': 'admin-check'}
try:
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError()
    report['phase'] = 'system-proxy'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
        enabled = bool(winreg.QueryValueEx(key, 'ProxyEnable')[0])
        server = winreg.QueryValueEx(key, 'ProxyServer')[0]
    targets = []
    for item in server.split(';'):
        item = item.split('=', 1)[-1].strip()
        parsed = urlsplit(item if '://' in item else 'http://' + item)
        if parsed.hostname:
            targets.append((parsed.hostname.casefold(), parsed.port))
    report['system_proxy_enabled'] = enabled
    report['phase'] = 'local-store-match'
    from core.storage import load_proxies, get_secure_storage_path
    proxies = load_proxies() if Path(get_secure_storage_path()).is_file() else []
    indices = {}
    matches = []
    for proxy in proxies:
        country = proxy.get_country_code()
        indices[country] = indices.get(country, 0) + 1
        if any(proxy.host.casefold() == host and (port is None or proxy.port == port) for host, port in targets):
            city = re.sub(r'[^a-zа-я]', '', (proxy.city or '').casefold())
            matches.append({'country': country, 'index': indices[country], 'los_angeles': city in ('losangeles', 'лосанджелес')})
    report['system_proxy_matches_saved'] = matches
    report['phase'] = 'native-status'
    import psutil
    report['core_process_count'] = sum((p.info.get('name') or '').casefold() == 'sing-box.exe' for p in psutil.process_iter(['name']))
    report['tun_adapter_count'] = sum(n == 'sing-tun' or n.startswith('sing-tun-') for n in psutil.net_if_addrs())
    from core.kill_switch import WindowsWfpBackend, KillSwitch
    backend = WindowsWfpBackend()
    try:
        status = KillSwitch(backend).status()
        report['protection_armed'] = status['armed']
        report['policy_present'] = status['policy_present']
    finally:
        backend.close()
    report.update(ok=True, phase='complete')
except Exception as exc:
    report['error_type'] = type(exc).__name__
    report['native_codes'] = re.findall(r'0x[0-9a-fA-F]{8}', str(exc))
(ROOT / '.autopilot/runtime-diagnostics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
