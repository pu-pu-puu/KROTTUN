"""Explicit bounded live deny smoke. Invoked only by stage2.ps1 after review."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from core.kill_switch import WindowsWfpBackend, KillSwitch, policy, OWNER
from core.wfp_native import GUID, Sublayer, Display
from preflight import assert_stopped

RULES = policy((),b'identity')  # No endpoints/interface: identity not serialized in these rules.
FILTER_NOT_FOUND = 0x80320003
REPORTS = Path(__file__).resolve().parent/'reports'


def error(exc):
    import re
    return {'type':type(exc).__name__,'winerror':getattr(exc,'winerror',None),
            'native_codes':re.findall(r'0x[0-9a-fA-F]{8}',str(exc))}


def write(path,data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
    temporary.replace(path)


def cleanup(backend):
    """Delete only deterministic smoke keys; never decode metadata to find keys."""
    backend._call('FwpmTransactionBegin0',backend.handle,0)
    try:
        for rule in RULES:
            key = GUID.of(uuid.uuid5(OWNER,rule.name))
            result = backend.dll.FwpmFilterDeleteByKey0(backend.handle,C.byref(key))
            if result not in (0,FILTER_NOT_FOUND):
                raise RuntimeError('delete failed 0x%08x'%result)
        if backend.read():
            raise RuntimeError('Owned filters remain; refusing success')
        backend._call('FwpmTransactionCommit0',backend.handle)
    except BaseException:
        backend._call('FwpmTransactionAbort0',backend.handle)
        raise
    if backend.read():
        raise RuntimeError('Owned filters remain after cleanup commit')


def rehearse(backend):
    """Check native add AND delete before any policy commit; always abort."""
    backend._call('FwpmTransactionBegin0',backend.handle,0)
    try:
        if backend.read():
            raise RuntimeError('Existing policy')
        sub = Sublayer()
        sub.key = GUID.of(OWNER)
        sub.display = Display('KROTTUN protection',None)
        sub.flags = 1
        sub.weight = 0x7fff
        result = backend.dll.FwpmSubLayerAdd0(backend.handle,C.byref(sub),None)
        if result not in (0,0x80320009):
            raise RuntimeError('sublayer failed 0x%08x'%result)
        for rule in RULES:
            backend._add(rule)
        if set(backend.read()) != set(RULES):
            raise RuntimeError('Rehearsal readback mismatch')
        for rule in RULES:
            key = GUID.of(uuid.uuid5(OWNER,rule.name))
            backend._call('FwpmFilterDeleteByKey0',backend.handle,C.byref(key))
        if backend.read():
            raise RuntimeError('Rehearsal delete mismatch')
    finally:
        backend._call('FwpmTransactionAbort0',backend.handle)


def tcp(address):
    family = socket.AF_INET6 if ':' in address else socket.AF_INET
    try:
        with socket.socket(family,socket.SOCK_STREAM) as connection:
            connection.settimeout(1.5)
            connection.connect((address,443))
        return 'connected'
    except OSError as exc:
        if getattr(exc,'winerror',None) == 10013:
            return 'firewall-denied-10013'
        if isinstance(exc,TimeoutError) or getattr(exc,'winerror',None) == 10060:
            return 'timeout-inconclusive'
        return 'unavailable-%s'%(getattr(exc,'winerror',None) or type(exc).__name__)


def stop_exact_parent(identity, process_factory=None):
    """Return only after the original test parent is confirmed gone.

    An unverifiable process is NEVER killed; caller must keep waiting/retrying.
    PID reuse means the original parent has exited, not permission to kill its
    replacement. psutil.kill additionally checks PID identity internally.
    """
    import psutil
    process_factory = process_factory or psutil.Process
    try:
        parent = process_factory(identity['pid'])
        if parent.create_time() != identity['created']:
            return True
        expected = os.path.normcase(os.path.realpath(identity['executable']))
        if os.path.normcase(os.path.realpath(parent.exe())) != expected:
            return False
        args = parent.cmdline()
        helper = os.path.normcase(os.path.abspath(identity.get('helper',str(Path(__file__).resolve()))))
        if not any(os.path.normcase(os.path.abspath(arg)) == helper for arg in args):
            return False
        if not any(args[i:i+2] == ['--run-nonce',identity['nonce']]
                   for i in range(len(args)-1)):
            return False
        parent.kill()
        parent.wait(timeout=2)
        return True
    except psutil.NoSuchProcess:
        return True
    except (psutil.AccessDenied, psutil.TimeoutExpired):
        return False


def expire_and_cleanup(identity, backend, stop=stop_exact_parent, recover=cleanup):
    # Critical ordering: no policy deletion/exit while parent can later arm.
    if not stop(identity):
        return False
    recover(backend)
    return True


def watchdog(folder, identity):
    backend = None
    deadline = time.monotonic()+20
    result = {'ok':False,'phase':'watchdog-open'}
    try:
        backend = WindowsWfpBackend()
        result['phase'] = 'watchdog-empty-read'
        if backend.read():
            raise RuntimeError('Existing policy')
        write(folder/'ready.json',{'ready':True,'nonce':folder.name})
        while time.monotonic() < deadline and not (folder/'cleanup-now').exists():
            time.sleep(.1)
        if (folder/'cleanup-now').exists():
            # Parent writes this only after its arm path ends permanently.
            result['phase'] = 'watchdog-normal-cleanup'
            cleanup(backend)
        else:
            result['deadline_expired'] = True
            result['phase'] = 'watchdog-stop-parent-before-cleanup'
            while True:
                try:
                    if expire_and_cleanup(identity,backend):
                        break
                except BaseException as exc:
                    result['retry_error'] = error(exc)
                # No success or exit until parent gone AND cleanup verified.
                try:
                    write(folder/'watchdog-progress.json',result)
                except OSError:
                    pass  # Reporting failure must not abandon recovery.
                time.sleep(.5)
        result.update(ok=True,phase='watchdog-complete')
    except BaseException as exc:
        result['error'] = error(exc)
    finally:
        if backend:
            backend.close()
        write(folder/'watchdog-result.json',result)
    return 0 if result['ok'] else 1


def run(backend, guard, connect=tcp, stopped=assert_stopped, log=lambda *args:None):
    """Injected lifecycle for offline tests; guard readiness precedes any live arm."""
    attempted = False
    result = {'ok':False,'classification':'failed','phase':'stopped-check'}
    try:
        stopped()
        log('stopped-check','passed')
        result['phase'] = 'initial-policy-read'
        if backend.read():
            raise RuntimeError('Existing policy')
        log('initial-policy-read','empty')
        result['phase'] = 'baseline'
        baseline = connect('1.1.1.1')
        log('baseline-ipv4',baseline)
        if baseline != 'connected':
            raise RuntimeError('IPv4 baseline unavailable')
        ipv6 = connect('2606:4700:4700::1111') == 'connected'
        log('baseline-ipv6','connected' if ipv6 else 'unavailable')
        result['phase'] = 'abort-rehearsal'
        rehearse(backend)
        log('abort-rehearsal','passed')
        result['phase'] = 'watchdog-readiness'
        guard.start()
        guard.require_ready()
        log('watchdog','ready-alive')
        result['phase'] = 'application-identity'
        app = backend.app_id(str(ROOT/'bin/sing-box.exe'))
        log('application-identity','resolved')
        stopped()
        if backend.read():
            raise RuntimeError('Policy appeared before arm')
        guard.require_alive()
        result['phase'] = 'live-arm'
        log('live-arm','attempting-commit-watchdog-alive')
        attempted = True  # Also clean up if arm throws after commit/readback.
        KillSwitch(backend).arm((),app)
        log('live-arm','committed')
        result['phase'] = 'blocked-tcp'
        checks = [connect('1.1.1.1')]
        if ipv6:
            checks.append(connect('2606:4700:4700::1111'))
        result['blocked_checks'] = checks
        log('blocked-tcp',checks)
        result['classification'] = ('passed' if all(x == 'firewall-denied-10013' for x in checks)
                                    else 'inconclusive' if any('inconclusive' in x for x in checks)
                                    else 'failed')
        result['ipv6'] = 'tested' if ipv6 else 'unavailable'
    except BaseException as exc:
        result['error'] = error(exc)
    finally:
        if attempted:
            try:
                cleanup(backend)
                log('parent-cleanup','empty-readback')
                result['cleanup_ok'] = True
            except BaseException as exc:
                result['cleanup_ok'] = False
                result['cleanup_error'] = error(exc)
        try:
            guard.finish()
        except BaseException as exc:
            result['watchdog_finish_error'] = error(exc)
    if attempted and result.get('cleanup_ok'):
        result['restored_tcp'] = connect('1.1.1.1')
        log('restored-ipv4',result['restored_tcp'])
        result['ok'] = (result['classification'] == 'passed' and result['restored_tcp'] == 'connected'
                        and not result.get('watchdog_finish_error') and guard.success())
    return result


class Guard:
    def __init__(self,folder):
        self.folder = folder
        self.process = None
    def start(self):
        import psutil
        parent = psutil.Process(os.getpid())
        self.process = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--watchdog',self.folder.name,
                                       '--parent-pid',str(parent.pid),'--parent-created',repr(parent.create_time()),
                                       '--parent-executable',parent.exe()],
                                       cwd=str(ROOT),creationflags=subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS,
                                       stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    def require_alive(self):
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError('Watchdog not alive')
    def require_ready(self):
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            self.require_alive()
            ready = self.folder/'ready.json'
            if ready.exists():
                data = json.loads(ready.read_text(encoding='utf-8'))
                if data == {'ready':True,'nonce':self.folder.name}:
                    return
                raise RuntimeError('Invalid readiness nonce')
            time.sleep(.05)
        raise RuntimeError('Watchdog readiness timed out')
    def finish(self):
        if self.process:
            (self.folder/'cleanup-now').touch()
            try:
                self.process.wait(timeout=23)
            except subprocess.TimeoutExpired:
                pass  # Never terminate the independent recovery process.
    def success(self):
        path = self.folder/'watchdog-result.json'
        return path.exists() and json.loads(path.read_text(encoding='utf-8')).get('ok',False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--watchdog')
    parser.add_argument('--run-nonce')
    parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--parent-created',type=float)
    parser.add_argument('--parent-executable')
    args = parser.parse_args()
    if os.name != 'nt' or not C.windll.shell32.IsUserAnAdmin():
        raise RuntimeError('Administrator required')
    REPORTS.mkdir(exist_ok=True)
    if args.watchdog:
        nonce = str(uuid.UUID(args.watchdog))
        folder = REPORTS/nonce
        if not folder.is_dir():
            raise RuntimeError('Unknown watchdog run')
        if not all((args.parent_pid,args.parent_created,args.parent_executable)):
            raise RuntimeError('Watchdog parent identity required')
        if args.parent_pid != os.getppid():
            raise RuntimeError('Watchdog must be direct child of test parent')
        identity = {'pid':args.parent_pid,'created':args.parent_created,
                    'executable':args.parent_executable,'nonce':nonce}
        return watchdog(folder,identity)
    if not args.run_nonce:
        raise RuntimeError('Explicit run nonce required; use stage2.ps1')
    folder = REPORTS/str(uuid.UUID(args.run_nonce))
    folder.mkdir()
    events = []
    def log(phase,value):
        events.append({'phase':phase,'value':value})
        write(folder/'events.json',events)
    backend = None
    try:
        backend = WindowsWfpBackend()
        result = run(backend,Guard(folder),log=log)
    except BaseException as exc:
        result = {'ok':False,'phase':'engine-open','error':error(exc)}
    finally:
        if backend:
            backend.close()
    result['run'] = folder.name
    result['scope'] = 'connectivity-smoke-only-no-TUN-no-packet-capture'
    write(folder/'result.json',result)
    write(REPORTS/'stage2.json',result)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
