"""Explicit saved EE -> US production failover exercise; no UI or saved edits."""
import argparse
import ctypes as C
import dataclasses
import logging
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
import threading
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from preflight import assert_stopped
import live_smoke as smoke
from core.kill_switch import WindowsWfpBackend, OWNER, Endpoint, policy, tunnel_luid
from core.wfp_native import P, U32, Filter, EnumTemplate, GUID, KEYS


def select_pair(proxies,primary='EE',us_index=1):
    groups = {code:[p for p in proxies if p.get_country_code() == code] for code in ('EE','US')}
    counts = {code:len(rows) for code,rows in groups.items()}
    if not all(counts.values()) or not 1<=us_index<=counts['US']:
        return None, counts
    order = ('EE','US') if primary=='EE' else ('US','EE')
    return [dataclasses.replace(groups[code][us_index-1 if code=='US' else 0]) for code in order],counts


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
    return not any(name.casefold()=='sing-tun' or name.casefold().startswith('sing-tun-') for name in psutil.net_if_addrs())


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


def wait_for(predicate,seconds,sample=None):
    deadline = time.monotonic()+seconds
    next_sample = 0
    while time.monotonic()<deadline:
        if sample and time.monotonic()>=next_sample:
            sample()
            next_sample = time.monotonic()+.5
        if predicate():
            return
        time.sleep(.1)
    raise TimeoutError('Stage deadline')


class Diagnostics:
    """Bounded allowlisted evidence, no payloads, IDs, addresses or errors text."""
    def __init__(self,pair):
        self.countries = {p.id:p.get_country_code() for p in pair}
        self.started = time.monotonic()
        self.calls = []
        self.samples = []
        self.core_capture = None
    def snapshot(self,bridge):
        state = bridge._state
        protection = bridge._protection.state
        active = bridge._sb.active_proxy
        return {'elapsed':round(time.monotonic()-self.started,3),
            'bridge':state if state in ('idle','starting','running','stopping','error') else 'other',
            'protection':protection if protection in ('unarmed','connecting','blocked','switching','protected','unknown') else 'other',
            'active_country':self.countries.get(active.id,'unknown') if active else 'none',
            'running':bool(bridge._sb.is_running()),'reachable':bool(bridge._sb.proxy_reachable),
            'adapters':adapter_snapshot(getattr(bridge._sb,'interface_name',None))}
    def sample(self,bridge):
        if len(self.samples)<180:
            self.samples.append(self.snapshot(bridge))
    def wrap(self,manager,name,label):
        original = getattr(manager,name)
        def wrapped(*args,**kwargs):
            start = time.monotonic()
            event = {'operation':label,'began':round(start-self.started,3)}
            if label=='wait-ready':
                event['adapters_before'] = adapter_snapshot(getattr(manager,'interface_name',None))
            if len(self.calls)<64:
                self.calls.append(event)
            try:
                result = original(*args,**kwargs)
                if label in ('probe','wait-ready'):
                    event['returned'] = bool(result)
                return result
            except BaseException as exc:
                event['error'] = smoke.error(exc)
                event['exception_classification'] = classify_startup_error(exc)
                raise
            finally:
                event['seconds'] = round(time.monotonic()-start,3)
                if label=='wait-ready':
                    event['adapters_after'] = adapter_snapshot(getattr(manager,'interface_name',None))
                    process = args[0] if args else getattr(manager,'process',None)
                    try:
                        code = process.poll() if process else None
                        event['process_present'] = process is not None
                        event['process_exited'] = process is not None and code is not None
                        if isinstance(code,int):
                            event['process_exit_code'] = code
                    except Exception as exc:
                        event['poll_error_type'] = type(exc).__name__
        setattr(manager,name,wrapped)
    def capture(self,bridge):
        states = ('connecting','failed','verified tunnel','explicit release')
        counts = {}
        for row in bridge._journal.read(limit=200)['rows']:
            kind,state = row.get('kind'),row.get('state')
            if kind in ('failover','protection'):
                key = kind+':'+(state if state in states else 'other')
                counts[key] = counts.get(key,0)+1
        result = {'snapshot':self.snapshot(bridge),'samples':list(self.samples),
                  'calls':list(self.calls),'journal_counts':counts}
        if self.core_capture:
            result['core_startups'] = self.core_capture.snapshot()
        return result


class MemoryCoreCapture:
    """Target core stderr only; drain continuously, export fixed classifications."""
    def __init__(self,module,executable):
        self.module = module
        self.executable = os.path.normcase(os.path.realpath(executable))
        self.attempts = []
        self.lock = threading.Lock()
    def __getattr__(self,name):
        return getattr(self.module,name)
    def Popen(self,*args,**kwargs):
        command = args[0] if args else kwargs.get('args')
        if not isinstance(command,(list,tuple)) or not command or os.path.normcase(os.path.realpath(command[0]))!=self.executable:
            return self.module.Popen(*args,**kwargs)
        attempt = {'flags':{key:False for key in ('default-interface-found','tun-create','tun-start',
                   'route-update','clash-listening','core-started','fatal','error')},
                   'last_component':'unknown','reason':'unknown','native_codes':[],'lines':0,
                   'startup_errors':[]}
        with self.lock:
            if len(self.attempts)<8:
                self.attempts.append(attempt)
        options = dict(kwargs)
        options['stderr'] = self.module.PIPE
        process = self.module.Popen(*args,**options)
        threading.Thread(target=self._drain,args=(process.stderr,attempt),daemon=True).start()
        return process
    def feed(self,attempt,line):
        import re
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',line[:4096]).casefold()
        with self.lock:
            flags = attempt['flags']
            flags['default-interface-found'] |= any(token in text for token in ('found default interface','updated default interface','default interface changed'))
            flags['tun-create'] |= any(token in text for token in ('creating tun','create tun','create adapter','wintuncreateadapter'))
            flags['tun-start'] |= 'inbound/tun' in text and any(token in text for token in ('started','start '))
            flags['route-update'] |= 'route' in text and any(token in text for token in ('update','adding','add route','set route'))
            flags['clash-listening'] |= 'clash' in text and any(token in text for token in ('listening','started','serving'))
            flags['core-started'] |= 'sing-box started' in text
            flags['fatal'] |= bool(re.search(r'\bfatal\b',text))
            flags['error'] |= bool(re.search(r'\berror\b',text))
            for token,component in (('inbound/tun','adapter'),('wintun','adapter'),('router:','router'),('dns:','dns'),('clash','clash'),('sing-box started','engine')):
                if token in text:
                    attempt['last_component'] = component
                    break
            if re.search(r'\b(?:fatal|error)\b',text):
                attempt['reason'] = classify_startup_error(text)['reason']
                codes = re.findall(r'0x[0-9a-f]{8}',text)
                attempt['native_codes'] = list(dict.fromkeys(attempt['native_codes']+codes))[:8]
                if not flags['core-started'] and len(attempt['startup_errors'])<8:
                    attempt['startup_errors'].append(startup_error_facts(text))
            attempt['lines'] = min(1000000,attempt['lines']+1)
    def _drain(self,stream,attempt):
        buffer = b''
        try:
            while True:
                chunk = os.read(stream.fileno(),4096)
                if not chunk:
                    break
                buffer += chunk
                while b'\n' in buffer:
                    line,buffer = buffer.split(b'\n',1)
                    self.feed(attempt,line[:4096].decode('utf-8',errors='replace'))
                # Bounded pending line; retain no raw log outside this thread.
                buffer = buffer[-4096:]
            if buffer:
                self.feed(attempt,buffer.decode('utf-8',errors='replace'))
        except Exception as exc:
            with self.lock:
                attempt['capture_error_type'] = type(exc).__name__
        finally:
            stream.close()
    def snapshot(self):
        with self.lock:
            return [{**item,'flags':dict(item['flags']),'native_codes':list(item['native_codes']),
                     'startup_errors':list(item['startup_errors'])} for item in self.attempts]


def enable_debug_config(manager):
    original = manager.generate_config
    def generate(*args,**kwargs):
        result = dict(original(*args,**kwargs))
        result['log'] = dict(result.get('log') or {})
        result['log']['level'] = 'debug'
        result['log'].pop('output',None)
        return result
    manager.generate_config = generate


def adapter_snapshot(alias=None):
    """Only presence/count facts; never persist interface aliases or addresses."""
    import psutil
    try:
        interfaces = psutil.net_if_addrs()
        alias = alias if isinstance(alias,str) else 'sing-tun'
        expected = '198.18.0.1'
        return {'alias_exact_present':alias in interfaces,
                'tun_alias_count':sum(name.casefold().startswith('sing-tun') for name in interfaces),
                'expected_address_anywhere':any(getattr(address,'address',None)==expected
                    for addresses in interfaces.values() for address in addresses),
                'expected_address_exact_alias':any(getattr(address,'address',None)==expected
                    for address in interfaces.get(alias,[]))}
    except Exception as exc:
        return {'error_type':type(exc).__name__}


def classify_startup_error(exc):
    """Inspect exception in memory only; classification is not a native log capture."""
    text = str(exc).casefold()
    categories = (
        ('file-exists',('cannot create a file when that file already exists','file already exists','file exists')),
        ('already-exists',('already exists','already exist')),
        ('object-in-use',('object is in use','object in use','resource is in use','resource busy')),
        ('sharing-violation',('sharing violation','used by another process','being used by another process')),
        ('invalid-handle',('invalid handle','handle is invalid')),
        ('device-not-ready',('device is not ready','device not ready')),
        ('cannot-create-file',('cannot create file','cannot create a file')),
        ('mutex',('mutex',)),
        ('timeout',('timed out','timeout','time out')),
        ('address-in-use',('address already in use','only one usage','10048')),
        ('access-denied',('access denied','access is denied','permission denied','отказано в доступе')),
        ('adapter-create',('create adapter','create tun','wintuncreateadapter','failed to create interface')),
        ('route',('add route','route table','create route','set route')),
        ('dns',('dns server','dns exchange','dns lookup')),
    )
    reason = next((label for label,tokens in categories if any(token in text for token in tokens)),'unknown')
    return {'reason':reason,'fatal_flag':'fatal' in text,'error_flag':'error' in text}


def startup_error_facts(text):
    """Export ONLY fixed labels/tokens, never excerpts requiring redaction.

    This intentionally cannot preserve arbitrary object names, addresses, paths,
    proxy fields, request details or unknown error words from native output.
    """
    import re
    text = text.casefold()
    phrases = (
        ('cannot-create-file-already-exists','cannot create a file when that file already exists'),
        ('already-exists','already exists'),('file-exists','file exists'),
        ('cannot-create-file','cannot create a file'),('invalid-handle','invalid handle'),
        ('handle-is-invalid','handle is invalid'),('device-not-ready','device is not ready'),
        ('object-in-use','object is in use'),('resource-in-use','resource is in use'),
        ('sharing-violation','sharing violation'),('used-by-another-process','used by another process'),
        ('access-denied','access is denied'),('permission-denied','permission denied'),
        ('address-in-use','address already in use'),('timed-out','timed out'),
        ('operation-timed-out','operation timed out'),('cannot-find-file','cannot find the file'),
        ('cannot-find-device','cannot find the device'),('specified-device','specified device'),
        ('system-cannot-find','system cannot find'),('rpc-unavailable','rpc server is unavailable'),
    )
    operations = (
        ('WintunCreateAdapter',('wintuncreateadapter',)),
        ('WintunOpenAdapter',('wintunopenadapter',)),
        ('WintunStartSession',('wintunstartsession',)),
        ('configure-address',('configure address','set ip address','set address','configure interface address')),
        ('configure-interface',('configure tun interface','configure interface')),
        ('routes',('configure routes','add route','set route','route table')),
    )
    vocabulary = frozenset(('cannot','could','failed','failure','create','open','start','file','already','exists',
        'device','handle','invalid','address','bind','driver','adapter','resource','mutex','timeout','timed','out',
        'access','denied','certificate','permission','rpc','server','unavailable','not','ready','busy','object',
        'sharing','violation','another','process','configure','interface','route','routes','session','system',
        'find','specified','parameter','incorrect','operation','unsupported','network','unreachable'))
    return {'reason':classify_startup_error(text)['reason'],
            'phrases':[label for label,phrase in phrases if phrase in text][:16],
            'operations':[label for label,tokens in operations if any(token in text for token in tokens)],
            'recognized_words':[word for word in re.findall(r'[a-z]+',text) if word in vocabulary][:48]}


def exit_ip(timeout=3):
    import ipaddress
    import requests
    with requests.Session() as session:
        session.trust_env = False
        response = session.get('https://api.ipify.org',timeout=timeout)
        response.raise_for_status()
        return str(ipaddress.ip_address(response.text.strip()))


def get_proxy_url(proxy):
    # Same credential quoting/protocol mapping as core.ip_service.test_proxy;
    # that function also performs geo calls, so it cannot be used here.
    from urllib.parse import quote
    proto = 'socks5h' if proxy.protocol.lower()=='socks5' else 'http'
    host = '['+proxy.host+']' if ':' in proxy.host else proxy.host
    auth = (quote(proxy.username,safe='')+':'+quote(proxy.password or '',safe='')+'@') if proxy.username else ''
    return '%s://%s%s:%s'%(proto,auth,host,proxy.port)


def availability(pair,us_index=1):
    import ipaddress
    import requests
    results = []
    for proxy in pair:
        country = proxy.get_country_code()
        item = {'country':country,'index':us_index if country=='US' else 1,'success':False}
        try:
            url = get_proxy_url(proxy)
            with requests.Session() as session:
                session.trust_env = False
                with session.get('https://api.ipify.org',proxies={'http':url,'https':url},
                                 timeout=3,allow_redirects=False,stream=True) as response:
                    response.raise_for_status()
                    ipaddress.ip_address(response.raw.read(65).decode('ascii').strip())
            item['success'] = True
        except Exception as exc:
            item['error_type'] = type(exc).__name__
        results.append(item)
    return results


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


def inject_proxy_outage(bridge,lookup=tunnel_luid):
    """Caller holds _op_lock. Withdraw physical endpoint permit; keep core/TUN."""
    manager = bridge._sb
    process = manager.process
    if process is None or process.poll() is not None:
        raise RuntimeError('Core must remain alive during proxy outage')
    guard = bridge._protection._guard()
    app = guard.backend.app_id(manager.exe_path)
    luid = lookup(manager.interface_name)
    if not isinstance(luid,int) or isinstance(luid,bool) or luid<=0:
        raise RuntimeError('Current TUN LUID unverified')
    guard.arm((),app,luid)
    if manager.process is not process or process.poll() is not None or not guard.status()['armed']:
        raise RuntimeError('Core/policy changed during outage injection')


def observe_exit_check(check=None,seconds=3):
    """Any completed success is failure; unfinished request is inconclusive.

    Daemon worker bounds the harness wait to three seconds without logging IPs.
    Default request timeout is two seconds; no retry/health-probe substitution.
    """
    import requests
    check = check or (lambda:exit_ip(timeout=2))
    done = threading.Event()
    observations = []
    def worker():
        try:
            check()
            observations.append('successful-response')
        except (requests.Timeout,TimeoutError):
            observations.append('timeout-inconclusive')
        except requests.HTTPError:
            observations.append('http-response')
        except (OSError,requests.RequestException):
            observations.append('network-failure')
        except Exception:
            observations.append('invalid-inconclusive')
        finally:
            done.set()
    threading.Thread(target=worker,daemon=True).start()
    return observations[0] if done.wait(seconds) else 'timeout-inconclusive'


def blocked_exit_check(check=None,seconds=3):
    return observe_exit_check(check,seconds)=='network-failure'


def accept_outage_observation(result,country,observation):
    allowed=('network-failure','timeout-inconclusive','http-response','successful-response','invalid-inconclusive')
    if observation not in allowed:
        raise ValueError('Unknown observation')
    result.setdefault('negative_checks',[]).append({'country':country,'observation':observation})
    return observation in ('network-failure','timeout-inconclusive')


def finalize_verdict(result,restored,watchdog_ok):
    negative_checks=result.get('negative_checks',[])
    acceptable=all(row['observation'] in ('network-failure','timeout-inconclusive') for row in negative_checks)
    functional=bool(result.get('functional_ok') and result.get('cleanup_ok') and result.get('no_tun') and restored and watchdog_ok and acceptable)
    inconclusive=any(row['observation']=='timeout-inconclusive' for row in result.get('negative_checks',[]))
    result['functional_ok']=functional
    result['ok']=functional and not inconclusive
    result['classification']='inconclusive' if functional and inconclusive else 'passed' if result['ok'] else 'failed'


def exercise(pair,backend,guard,record,fault_mode='Core'):
    bridge = None
    capture_patch = None
    signal_safe = False
    result = {'ok':False,'functional_ok':False,'classification':'failed','phase':'baseline','fault_mode':fault_mode}
    diagnostics = Diagnostics(pair)
    primary,reserve = [p.get_country_code() for p in pair]
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
            enable_debug_config(bridge._sb)
            import core.singbox_manager as manager_module
            diagnostics.core_capture = MemoryCoreCapture(manager_module.subprocess,bridge._sb.exe_path)
            capture_patch = patch('core.singbox_manager.subprocess',diagnostics.core_capture)
            capture_patch.start()
            diagnostics.wrap(bridge._sb,'start','start')
            diagnostics.wrap(bridge._sb,'_probe_tunnel','probe')
            diagnostics.wrap(bridge._sb,'_wait_ready','wait-ready')
            bridge.proxies = pair
            bridge.selected_proxy_id = pair[0].id
            result['phase'] = primary+'-start'
            bridge.toggle_tun()
            wait_for(lambda:bridge._state==TunState.RUNNING and bridge._sb.proxy_reachable,30,lambda:diagnostics.sample(bridge))
            if bridge._sb.active_proxy.id!=pair[0].id:
                raise RuntimeError('EE primary did not connect')
            ee = exit_ip()
            record(primary+'-exit-differs-baseline',ee!=baseline)
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
                result['phase'] = primary+('-proxy-outage' if fault_mode=='Proxy' else '-core-kill-block')
                with bridge._op_lock:
                    if fault_mode=='Proxy':
                        inject_proxy_outage(bridge)
                        record(primary+'-outage-core-alive',bridge._sb.is_running())
                        record(primary+'-outage-policy-armed',bridge._protection._guard().status()['armed'])
                        observation = observe_exit_check()
                        record(primary+'-outage-egress-network-failure',observation=='network-failure')
                        if not accept_outage_observation(result,primary,observation):
                            raise RuntimeError('Proxy fault egress success or inconclusive')
                    else:
                        kill_owned(bridge._sb)
                        if not bridge._protection._guard().status()['armed']:
                            raise RuntimeError('Deny policy absent')
                        denied = smoke.tcp('1.1.1.1')
                        record(primary+'-kill-local-deny',denied=='firewall-denied-10013')
                        if denied!='firewall-denied-10013':
                            raise RuntimeError('Local deny inconclusive')
            result['phase'] = reserve+'-automatic-failover'
            wait_for(lambda:bridge._state==TunState.RUNNING and bridge._sb.is_running() and bridge._sb.active_proxy.id==pair[1].id and bridge._sb.proxy_reachable,45 if fault_mode=='Proxy' else 30,lambda:diagnostics.sample(bridge))
            us = exit_ip()
            record(reserve+'-exit-differs-baseline',us!=baseline)
            record(reserve+'-exit-differs-'+primary,us!=ee)
            if us==baseline:
                raise RuntimeError('Egress unchanged')
            result['phase'] = 'reserve-exhaustion'
            with bridge._op_lock:
                bridge.proxies = []
                if fault_mode=='Proxy':
                    inject_proxy_outage(bridge)
                    record(reserve+'-outage-core-alive',bridge._sb.is_running())
                    record(reserve+'-outage-policy-armed',bridge._protection._guard().status()['armed'])
                    observation = observe_exit_check()
                    record(reserve+'-outage-egress-network-failure',observation=='network-failure')
                    if not accept_outage_observation(result,reserve,observation):
                        raise RuntimeError('Reserve fault egress success or inconclusive')
                else:
                    kill_owned(bridge._sb)
            wait_for(lambda:bridge._state==TunState.ERROR,45 if fault_mode=='Proxy' else 12,lambda:diagnostics.sample(bridge))
            blocked = bridge._protection._guard().status()['armed'] and smoke.tcp('1.1.1.1')=='firewall-denied-10013'
            record('exhaustion-blocked',blocked)
            if not blocked:
                raise RuntimeError('Exhaustion block unproven')
            result['functional_ok'] = True
    except BaseException as exc:
        result['error'] = smoke.error(exc)
        if bridge:
            result['diagnostics'] = diagnostics.capture(bridge)
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
                result['no_tun'] = tun_absent()
            except BaseException as exc:
                result['ok'] = False
                result['functional_ok'] = False
                result['cleanup_error'] = smoke.error(exc)
            finally:
                bridge._op_lock.release()
                bridge._geo_pool.shutdown(wait=False,cancel_futures=True)
                if capture_patch:
                    capture_patch.stop()
        else:
            signal_safe = True  # No manager ever instantiated/started.
        if signal_safe:
            guard.finish()
        # Otherwise leave watchdog armed: it terminates this parent before release.
    if signal_safe:
        result['restored_tcp'] = smoke.tcp('1.1.1.1')=='connected'
        finalize_verdict(result,result['restored_tcp'],guard.success())
    return result


def main():
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-nonce')
    parser.add_argument('--primary-country',choices=('EE','US'),default='EE')
    parser.add_argument('--us-index',type=int,default=1)
    parser.add_argument('--fault-mode',choices=('Core','Proxy'),default='Core')
    parser.add_argument('--inspect-only',action='store_true')
    parser.add_argument('--availability-only',action='store_true')
    parser.add_argument('--watchdog')
    parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--parent-created',type=float)
    parser.add_argument('--parent-executable')
    args = parser.parse_args()
    if args.inspect_only and args.availability_only:
        parser.error('Choose one inventory mode')
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
        if not tun_absent():
            raise RuntimeError('Preexisting TUN interface')
        backend = WindowsWfpBackend()
        if raw_keys(backend) or marker_path().exists():
            raise RuntimeError('Preexisting protection')
        from core.storage import get_secure_storage_path, load_proxies
        # Do not trigger legacy migration for absent storage.
        path = get_secure_storage_path()
        stored = load_proxies() if os.path.isfile(path) else []
        pair, counts = select_pair(stored,args.primary_country,args.us_index)
        result['counts'] = counts
        if pair is None:
            raise RuntimeError('EE/US pair unavailable')
        result['selected'] = [{'country':p.get_country_code(),'index':args.us_index if p.get_country_code()=='US' else 1} for p in pair]
        if args.availability_only:
            result.update(ok=True,phase='availability-complete',availability=availability(pair,args.us_index))
        elif args.inspect_only:
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
            result = exercise(pair,backend,Guard(folder),record,args.fault_mode)
            result['selected'] = [{'country':p.get_country_code(),'index':args.us_index if p.get_country_code()=='US' else 1} for p in pair]
            result['run'] = folder.name
            smoke.write(folder/'result.json',result)
    except BaseException as exc:
        result['error'] = smoke.error(exc)
    finally:
        if backend:
            backend.close()
    previous = smoke.REPORTS/'stage3.json'
    if previous.exists():
        shutil.copyfile(previous,smoke.REPORTS/('stage3-before-diagnostics-'+str(uuid.uuid4())+'.json'))
    smoke.write(previous,result)
    return 0 if result['ok'] else 1


if __name__=='__main__':
    raise SystemExit(main())
