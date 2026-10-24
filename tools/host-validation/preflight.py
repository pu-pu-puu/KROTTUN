"""Noncommitting native ABI probe. Never call backend.replace() here."""
import ctypes as C
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.kill_switch import WindowsWfpBackend, Endpoint, policy, OWNER
from core.wfp_native import Sublayer, GUID, Display


def probe(factory, app_path, running_check):
    report = {'ok': False, 'phase': 'process-check', 'committed': False,
              'abort_attempted': False, 'abort_ok': False}
    backend = None
    active = False
    try:
        running_check()
        report['phase'] = 'engine-open'
        backend = factory()
        report['phase'] = 'existing-policy-read'
        if backend.read():
            raise RuntimeError('Existing owned policy; refusing probe')
        report['phase'] = 'application-identity'
        app = backend.app_id(str(app_path))
        if not app:
            raise RuntimeError('Empty application identity')
        # Documentation ranges, no DNS, connections, or actual TUN creation.
        desired = policy((Endpoint('192.0.2.1',443), Endpoint('2001:db8::1',443,17)), app, 1)
        report['rule_count'] = len(desired)
        report['phase'] = 'transaction-begin'
        backend._call('FwpmTransactionBegin0', backend.handle, 0)
        active = True
        report['phase'] = 'transaction-existing-policy-read'
        if backend.read():
            raise RuntimeError('Owned policy appeared; refusing probe')
        report['phase'] = 'sublayer-add'
        sub = Sublayer()
        sub.key = GUID.of(OWNER)
        sub.display = Display('KROTTUN protection',None)
        sub.flags = 1
        sub.weight = 0x7fff
        result = backend.dll.FwpmSubLayerAdd0(backend.handle,C.byref(sub),None)
        if result not in (0,0x80320009):
            raise RuntimeError('Native sublayer error 0x%08x' % result)
        for index, rule in enumerate(desired):
            report['phase'] = 'filter-add-%d-%s' % (index,rule.layer)
            backend._add(rule)
        report['phase'] = 'transaction-readback'
        if set(backend.read()) != set(desired):
            raise RuntimeError('Native transaction readback mismatch')
        report['ok'] = True
    except BaseException as exc:
        report['error_type'] = type(exc).__name__
        # Never serialize arbitrary exception text, paths, identities or config.
        report['native_codes'] = re.findall(r'0x[0-9a-fA-F]{8}', str(exc))
        report['winerror'] = getattr(exc, 'winerror', None)
    finally:
        if active:
            report['abort_attempted'] = True
            try:
                backend._call('FwpmTransactionAbort0', backend.handle)
                report['abort_ok'] = True
            except BaseException as exc:
                report['ok'] = False
                report['abort_error_type'] = type(exc).__name__
                report['abort_native_codes'] = re.findall(r'0x[0-9a-fA-F]{8}', str(exc))
        if backend is not None:
            try:
                # Checked close, unlike production close() which ignores status.
                backend._call('FwpmEngineClose0', backend.handle)
                backend.handle = None
                report['close_ok'] = True
            except BaseException as exc:
                report['ok'] = False
                report['close_ok'] = False
                report['close_error_type'] = type(exc).__name__
    return report


def assert_stopped():
    import psutil
    for process in psutil.process_iter(['pid','name','cmdline']):
        if process.pid == os.getpid():
            continue
        try:
            name = (process.info['name'] or '').lower()
            if name in ('sing-box.exe','krottun.exe'):
                raise RuntimeError('Close KROTTUN and sing-box first')
            if name.startswith(('python','pythonw')):
                args = process.cmdline()
                if any(Path(arg).name.lower() == 'main.py' for arg in args):
                    raise RuntimeError('Close Python GUI first')
        except psutil.NoSuchProcess:
            continue
        # AccessDenied deliberately fails closed.


def main():
    out = Path(__file__).resolve().parent / 'reports'
    out.mkdir(exist_ok=True)
    if os.name != 'nt' or not C.windll.shell32.IsUserAnAdmin():
        report = {'ok':False,'phase':'admin-check','committed':False}
    else:
        report = probe(WindowsWfpBackend, ROOT / 'bin' / 'sing-box.exe', assert_stopped)
    (out / 'stage1.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (out / 'stage1.txt').write_text('\n'.join('%s: %s' % item for item in report.items())+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
