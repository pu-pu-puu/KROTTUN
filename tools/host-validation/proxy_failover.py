"""Explicit saved EE -> US production failover exercise; no UI or saved edits."""
import argparse
import ctypes as C
import dataclasses
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from preflight import assert_stopped
import live_smoke as smoke
from core.kill_switch import WindowsWfpBackend, OWNER, Endpoint, policy
from core.wfp_native import P, U32, Filter, EnumTemplate, GUID, KEYS


def select_pair(proxies):
    groups = {code:[p for p in proxies if p.get_country_code() == code] for code in ('EE','US')}
    counts = {code:len(rows) for code,rows in groups.items()}
    if counts != {'EE':1,'US':1}:
        return None, counts
    return [dataclasses.replace(groups[code][0]) for code in ('EE','US')],counts


def raw_keys(backend):
    keys = []
    for family in (4,6):
        for layer in ('packet','connect','accept'):
            template = EnumTemplate()
            template.layer = GUID.of(KEYS[layer+str(family)])
            template.flags = 0x18
            template.action_mask = 0xffffffff
            enum = P()
            backend._call('FwpmFilterCreateEnumHandle0',backend.handle,C.byref(template),C.byref(enum))
            try:
                while True:
                    ptr, count = P(),U32()
                    backend._call('FwpmFilterEnum0',backend.handle,enum,128,C.byref(ptr),C.byref(count))
                    try:
                        rows = C.cast(ptr,C.POINTER(C.POINTER(Filter)))
                        for i in range(count.value):
                            row = rows[i].contents
                            if bytes(row.sublayer) == OWNER.bytes_le:
                                keys.append(GUID.from_buffer_copy(bytes(row.key)))
                    finally:
                        if ptr:
                            backend.dll.FwpmFreeMemory0(C.byref(ptr))
                    if count.value < 128:
                        break
            finally:
                backend._call('FwpmFilterDestroyEnumHandle0',backend.handle,enum)
    return keys


def cores_gone():
    """Conservative: never kill unrelated cores; wait rather than release."""
    import psutil
    for process in psutil.process_iter(['name']):
        try:
            if (process.info['name'] or '').lower() == 'sing-box.exe':
                return False
        except psutil.NoSuchProcess:
            continue
    return True


def tun_absent():
    import psutil
    return not any(name.casefold()=='sing-tun' for name in psutil.net_if_addrs())


def watchdog_cleanup(backend,marker):
    # A dead process does not prove that Windows has released its TUN adapter.
    # Never delete adapters: retain policy/marker and retry until absence proven.
    if not cores_gone() or not tun_absent():
        return False
    raw_cleanup(backend)
    if not tun_absent():
        return False
    marker.unlink(missing_ok=True)
    return True


def raw_cleanup(backend):
    if not cores_gone():
        raise RuntimeError('Core exit unconfirmed')
    backend._call('FwpmTransactionBegin0',backend.handle,0)
    try:
        for key in raw_keys(backend):
            result = backend.dll.FwpmFilterDeleteByKey0(backend.handle,C.byref(key))
            if result not in (0,smoke.FILTER_NOT_FOUND):
                raise RuntimeError('delete error 0x%08x'%result)
        if raw_keys(backend):
            raise RuntimeError('Owned filters remain')
        backend._call('FwpmTransactionCommit0',backend.handle)
    except BaseException:
        backend._call('FwpmTransactionAbort0',backend.handle)
        raise
    if raw_keys(backend):
        raise RuntimeError('Readback not empty')


def parent_outside_watchdog_job(process):
    from core import win_job
    from ctypes import wintypes
    fn = win_job._k32.IsProcessInJob
    fn.argtypes = [wintypes.HANDLE,wintypes.HANDLE,C.POINTER(wintypes.BOOL)]
    fn.restype = wintypes.BOOL
    inside = wintypes.BOOL()
    if not fn(wintypes.HANDLE(int(process._handle)),win_job._job,C.byref(inside)) or inside.value:
        raise RuntimeError('Watchdog job isolation not proven')


def marker_path():
    from core.paths import get_program_data_dir
    return Path(get_program_data_dir())/'ProxyTUN/protection-recovery.json'


def watchdog(folder,identity):
    backend = WindowsWfpBackend()
    result = {'ok':False,'phase':'watchdog-initial-read'}
    expired = False
    try:
        if raw_keys(backend) or marker_path().exists():
            raise RuntimeError('Preexisting protection')
        smoke.write(folder/'ready.json',{'ready':True,'nonce':folder.name})
        deadline = time.monotonic()+100
        while time.monotonic()<deadline and not (folder/'cleanup-now').exists():
            time.sleep(.1)
        expired = not (folder/'cleanup-now').exists()
        result['deadline_expired'] = expired
        while True:
            try:
                # On expiry prevent all future starts before any release.
                if expired and not smoke.stop_exact_parent(identity):
                    time.sleep(.5)
                    continue
                if not watchdog_cleanup(backend,marker_path()):
                    time.sleep(.5)
                    continue
                result.update(ok=True,phase='watchdog-cleaned')
                break
            except BaseException as exc:
                result['phase'] = 'watchdog-retrying-recovery'
                result['error'] = smoke.error(exc)
                time.sleep(.5)
    except BaseException as exc:
        result['error'] = smoke.error(exc)
    finally:
        backend.close()
        smoke.write(folder/'watchdog-result.json',result)
    return 0 if result['ok'] else 1


class Guard(smoke.Guard):
    def start(self):
        import psutil
        parent = psutil.Process()
        self.process = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--watchdog',self.folder.name,
            '--parent-pid',str(parent.pid),'--parent-created',repr(parent.create_time()),
            '--parent-executable',parent.exe()],cwd=str(ROOT),
            creationflags=subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def wait_for(predicate,seconds):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():
            return
        time.sleep(.1)
    raise TimeoutError('Stage deadline')


def exit_ip():
    import ipaddress
    import requests
    with requests.Session() as session:
        session.trust_env = False
        response = session.get('https://api.ipify.org',timeout=3)
        response.raise_for_status()
        return str(ipaddress.ip_address(response.text.strip()))


def kill_owned(manager):
    import psutil
    process = manager.process
    if process is None:
        raise RuntimeError('Missing owned core')
    candidate = psutil.Process(process.pid)
    if candidate.ppid()!=os.getpid() or os.path.normcase(candidate.exe())!=os.path.normcase(manager.exe_path):
        raise RuntimeError('Core ownership unverified')
    process.kill()
    process.wait(timeout=3)


def exercise(pair,backend,guard,record):
    bridge = None
    signal_safe = False
    result = {'ok':False,'phase':'baseline'}
    try:
        if smoke.tcp('1.1.1.1')!='connected':
            raise RuntimeError('Baseline unavailable')
        baseline = exit_ip()
        record('baseline',True)
        result['phase'] = 'abort-endpoint-interface-rehearsal'
        # Reuse the tested abort-only native rehearsal with full synthetic rules.
        app = backend.app_id(str(ROOT/'bin/sing-box.exe'))
        with patch.object(smoke,'RULES',policy((Endpoint('192.0.2.1',443),Endpoint('2001:db8::1',443)),app,1)):
            smoke.rehearse(backend)
        result['phase'] = 'watchdog-start'
        guard.start()
        guard.require_ready()
        from core.win_job import bind_self_to_job
        if not bind_self_to_job():
            raise RuntimeError('Job bind failed')
        parent_outside_watchdog_job(guard.process)
        guard.require_alive()
        record('watchdog-outside-core-job',True)
        from gui.app_webview import ProxyTunBridgeApi, TunState
        # No saved settings/proxy mutation or background geolocation requests.
        with patch('gui.app_webview.load_proxies',return_value=pair),patch('gui.app_webview.load_settings',return_value={}),patch.object(ProxyTunBridgeApi,'_refresh_ip_async',return_value=None):
            bridge = ProxyTunBridgeApi()
            bridge._sb.log_path = os.devnull
            bridge._sb.stderr_path = os.devnull
            bridge.proxies = pair
            bridge.selected_proxy_id = pair[0].id
            result['phase'] = 'EE-start'
            bridge.toggle_tun()
            wait_for(lambda:bridge._state==TunState.RUNNING and bridge._sb.proxy_reachable,30)
            if bridge._sb.active_proxy.id!=pair[0].id:
                raise RuntimeError('EE primary did not connect')
            ee = exit_ip()
            record('EE-exit-differs-baseline',ee!=baseline)
            if ee==baseline:
                raise RuntimeError('Egress unchanged')
            result['phase'] = 'live-connections'
            with socket.create_connection(('1.1.1.1',443),timeout=3):
                bridge._source.poll(bridge._sb,bridge._protection.generation)
                snapshot = bridge._journal.read()
                rows = [row for row in snapshot['rows'] if row.get('kind')=='connection']
                record('connections-source-available',snapshot['source']=='snapshot')
                record('connections-observed',bool(rows))
                record('connections-count',len(rows))
                record('connections-process-fields',any(row.get('process') not in (None,'unavailable') for row in rows))
                if snapshot['source']!='snapshot' or not rows:
                    raise RuntimeError('Live connection source unavailable')
                result['phase'] = 'EE-core-kill-block'
                with bridge._op_lock:
                    kill_owned(bridge._sb)
                    if not bridge._protection._guard().status()['armed']:
                        raise RuntimeError('Deny policy absent')
                    denied = smoke.tcp('1.1.1.1')
                    record('EE-kill-local-deny',denied=='firewall-denied-10013')
                    if denied!='firewall-denied-10013':
                        raise RuntimeError('Local deny inconclusive')
            result['phase'] = 'US-automatic-failover'
            wait_for(lambda:bridge._state==TunState.RUNNING and bridge._sb.is_running() and bridge._sb.active_proxy.id==pair[1].id and bridge._sb.proxy_reachable,30)
            us = exit_ip()
            record('US-exit-differs-baseline',us!=baseline)
            record('US-exit-differs-EE',us!=ee)
            if us==baseline:
                raise RuntimeError('Egress unchanged')
            result['phase'] = 'reserve-exhaustion'
            with bridge._op_lock:
                bridge.proxies = []
                kill_owned(bridge._sb)
            wait_for(lambda:bridge._state==TunState.ERROR,12)
            blocked = bridge._protection._guard().status()['armed'] and smoke.tcp('1.1.1.1')=='firewall-denied-10013'
            record('exhaustion-blocked',blocked)
            if not blocked:
                raise RuntimeError('Exhaustion block unproven')
            result['ok'] = True
    except BaseException as exc:
        result['error'] = smoke.error(exc)
    finally:
        if bridge:
            bridge._closing = True
            bridge._protection.cancel.set()
            # Serialize against every production startup before releasing.
            bridge._op_lock.acquire()
            try:
                bridge._sb.stop()
                if not cores_gone():
                    raise RuntimeError('Core exit unverified')
                if not tun_absent():
                    raise RuntimeError('TUN removal unverified')
                bridge._protection.release()
                raw_cleanup(backend)
                marker_path().unlink(missing_ok=True)
                signal_safe = True
                result['cleanup_ok'] = True
                result['no_tun'] = not bridge._sb.is_adapter_present('sing-tun')
            except BaseException as exc:
                result['ok'] = False
                result['cleanup_error'] = smoke.error(exc)
            finally:
                bridge._op_lock.release()
                bridge._geo_pool.shutdown(wait=False,cancel_futures=True)
        else:
            signal_safe = True  # No manager ever instantiated/started.
        if signal_safe:
            guard.finish()
        # Otherwise leave watchdog armed: it terminates this parent before release.
    if signal_safe:
        result['restored_tcp'] = smoke.tcp('1.1.1.1')=='connected'
        result['ok'] = bool(result['ok'] and result.get('cleanup_ok') and result.get('no_tun') and result['restored_tcp'] and guard.success())
    return result


def main():
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-nonce')
    parser.add_argument('--inspect-only',action='store_true')
    parser.add_argument('--watchdog')
    parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--parent-created',type=float)
    parser.add_argument('--parent-executable')
    args = parser.parse_args()
    if os.name!='nt' or not C.windll.shell32.IsUserAnAdmin():
        raise RuntimeError('Administrator required')
    smoke.REPORTS.mkdir(exist_ok=True)
    if args.watchdog:
        nonce = str(uuid.UUID(args.watchdog))
        if args.parent_pid!=os.getppid() or not args.parent_created or not args.parent_executable:
            raise RuntimeError('Direct parent identity required')
        return watchdog(smoke.REPORTS/nonce,{'pid':args.parent_pid,'created':args.parent_created,
            'executable':args.parent_executable,'nonce':nonce,'helper':str(Path(__file__).resolve())})
    result = {'ok':False,'phase':'initial-check'}
    backend = None
    try:
        assert_stopped()
        import psutil
        if 'sing-tun' in psutil.net_if_addrs():
            raise RuntimeError('Preexisting TUN interface')
        backend = WindowsWfpBackend()
        if raw_keys(backend) or marker_path().exists():
            raise RuntimeError('Preexisting protection')
        from core.storage import get_secure_storage_path, load_proxies
        # Do not trigger legacy migration for absent storage.
        path = get_secure_storage_path()
        pair, counts = select_pair(load_proxies() if os.path.isfile(path) else [])
        result['counts'] = counts
        if pair is None:
            raise RuntimeError('Unique EE/US pair unavailable')
        if args.inspect_only:
            result.update(ok=True,phase='inventory-valid')
        else:
            folder = smoke.REPORTS/str(uuid.UUID(args.run_nonce))
            folder.mkdir()
            events = []
            def record(phase,value):
                if not isinstance(value,(bool,int)):
                    raise TypeError('Only booleans/counts allowed')
                events.append({'phase':phase,'value':value})
                smoke.write(folder/'events.json',events)
            result = exercise(pair,backend,Guard(folder),record)
            result['run'] = folder.name
            smoke.write(folder/'result.json',result)
    except BaseException as exc:
        result['error'] = smoke.error(exc)
    finally:
        if backend:
            backend.close()
    smoke.write(smoke.REPORTS/'stage3.json',result)
    return 0 if result['ok'] else 1


if __name__=='__main__':
    raise SystemExit(main())
