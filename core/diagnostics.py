"""Ephemeral, bounded network diagnostics. No lifecycle or policy mutations."""
import copy
import ipaddress
import json
import multiprocessing
import socket
import threading
import time
import uuid
from types import SimpleNamespace
from urllib.parse import quote
import requests
from core.win_job import bind_to_lifetime

LABELS = {'proxy':'Прокси / туннель','dns':'DNS','https':'HTTPS','ip':'Внешний IP','system_proxy':'Системный прокси Windows'}
DETAILS = {
 'waiting':'Выполняется проверка…',
 'pass':'Проверка пройдена.',
 'fail':'Нет подтверждённого ответа. Проверьте сервер и доступность сети; таймаут не доказывает утечку.',
 'skipped':'Проверка недоступна в текущем состоянии. Подключите туннель или выберите сервер при снятой защите.',
 'cancelled':'Состояние подключения изменилось. Запустите проверку снова.',
 'timeout':'Время проверки истекло. Проверьте сервер и повторите; это не доказательство утечки.',
 'unknown':'Не удалось прочитать флаг Windows. Проверьте параметры прокси вручную.',
 'enabled':'Включён системный прокси Windows. Проверьте его вручную: возможен конфликт с TUN.',
 'disabled':'Системный прокси Windows выключен.',
 'unavailable':'Не удалось безопасно запустить проверку. Повторите диагностику.'}


def checks(mode, flag):
    rows=[{'id':key,'label':label,'status':'running' if mode else 'skipped',
           'detail':DETAILS['waiting' if mode else 'skipped']} for key,label in LABELS.items()]
    if mode=='proxy':
        rows[0]['label']='Доступность прокси (TCP)'
        rows[1]['label']='DNS через прокси (DoH)'
    elif mode=='protected':
        rows[0]['label']='Состояние туннеля'
        rows[1]['label']='Системный DNS через TUN'
    rows[-1].update(status='skipped' if flag is None else ('warning' if flag else 'pass'),
                    detail=DETAILS['unknown' if flag is None else ('enabled' if flag else 'disabled')])
    return rows


def system_proxy_flag():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
            value,_=winreg.QueryValueEx(key,'ProxyEnable')
        return bool(value) if isinstance(value,int) else None
    except (ImportError,OSError):
        return None


def perform_checks(mode, proxy, deadline, emit, session_factory=requests.Session,
                   resolve=socket.getaddrinfo, connect=socket.create_connection, clock=time.monotonic):
    """Child-only transport seam; emit only check IDs and categorical results."""
    def remaining():
        value=min(2.5,deadline-clock())
        if value<=0: raise TimeoutError()
        return value
    def get_json(session,url):
        with session.get(url,timeout=remaining(),allow_redirects=False,stream=True,headers={'Accept':'application/dns-json'} if 'dns-query?' in url else {}) as response:
            if response.status_code!=200: raise ValueError()
            body=bytearray()
            for chunk in response.iter_content(1024):
                remaining(); body.extend(chunk)
                if len(body)>8192: raise ValueError()
            return json.loads(body)
    with session_factory() as session:
        session.trust_env=False
        if mode=='proxy':
            host=proxy.host
            if ':' in host: host='['+host+']'
            auth=''
            if proxy.username is not None:
                auth=quote(proxy.username,safe='')+':'+quote(proxy.password or '',safe='')+'@'
            scheme='socks5h' if proxy.protocol=='socks5' else 'http'
            url=f'{scheme}://{auth}{host}:{proxy.port}'
            session.proxies={'http':url,'https':url}
        for key in ('proxy','dns','https','ip'):
            try:
                remaining()
                value=None
                if key=='proxy':
                    if mode=='proxy':
                        with connect((proxy.host,proxy.port),timeout=remaining()): pass
                    # Protected mode is authorized only by existing runtime health.
                elif key=='dns':
                    if mode=='proxy':
                        data=get_json(session,'https://cloudflare-dns.com/dns-query?name=example.com&type=A')
                        if data.get('Status')!=0 or not any(a.get('type')==1 and ipaddress.ip_address(a.get('data','')).version==4 for a in data.get('Answer',[])): raise ValueError()
                    elif not resolve('example.com',443,type=socket.SOCK_STREAM): raise ValueError()
                elif key=='https':
                    with session.get('https://example.com',timeout=remaining(),allow_redirects=False,stream=True) as response:
                        if response.status_code!=200: raise ValueError()
                        if not next(response.iter_content(1024),b''): raise ValueError()
                else:
                    value=str(ipaddress.ip_address(get_json(session,'https://api.ipify.org?format=json')['ip']))
                emit((key,'pass',value))
            except Exception:
                emit((key,'fail',None))


def diagnostic_worker(sender, mode, proxy, deadline, gate):
    try:
        if not gate.wait(max(0,deadline-time.monotonic())): return
        if time.monotonic()>=deadline: return
        perform_checks(mode,proxy,deadline,sender.send)
    except Exception:
        pass  # No raw exceptions or credentials cross the process boundary.
    finally:
        sender.close()


class DiagnosticsService:
    def __init__(self, valid, context_factory=None, binder=bind_to_lifetime, clock=time.monotonic):
        self._valid=valid; self._factory=context_factory or (lambda:multiprocessing.get_context('spawn'))
        self._binder=binder; self._clock=clock; self._lock=threading.RLock()
        self._process=None; self._cancel=threading.Event(); self._busy=False
        self._done=threading.Event(); self._done.set()
        self._data={'run_id':None,'status':'idle','checks':[]}

    def start(self, context, mode, proxy=None, flag=None):
        with self._lock:
            self._reap_exited()
            if self._busy or self._process is not None:
                return {'success':False,'busy':True,'run_id':self._data['run_id'],'error':'Диагностика уже выполняется'}
            run=uuid.uuid4().hex
            self._data={'run_id':run,'status':'running' if mode else 'done','checks':checks(mode,flag)}
            if mode:
                self._busy=True; self._cancel.clear(); self._done.clear()
                deadline=self._clock()+10.5 # reserve 1 s for bounded terminate/kill confirmation
                threading.Thread(target=self._run,args=(context,mode,proxy,deadline),daemon=True).start()
            return {'success':True,'run_id':run}

    def snapshot(self, valid=True):
        with self._lock:
            if not valid and self._data['run_id']:
                self._cancel.set()
                self._finish_rows('cancelled')
            return copy.deepcopy(self._data)

    def cancel(self):
        self._cancel.set()
        with self._lock:
            if self._data['run_id']: self._finish_rows('cancelled')

    def stop(self, timeout=1.25):
        """Cancel and confirm exit before a caller removes the protected route."""
        self.cancel()
        if not self._done.wait(timeout): return False
        with self._lock:
            self._reap_exited()
            return not self._busy and self._process is None

    def _reap_exited(self):
        # Called under the service lock; never discard a live or uncertain child.
        if not self._busy and self._process is not None:
            try:
                if not self._process.is_alive():
                    self._process.join(timeout=0)
                    self._process.close()
                    self._process=None
            except Exception:
                pass

    def _finish_rows(self,reason):
        for row in self._data['checks']:
            if row['id']!='system_proxy' and (reason=='cancelled' or row['status']=='running'):
                row.update(status='skipped' if reason=='cancelled' else 'fail',detail=DETAILS[reason])
        self._data['status']='cancelled' if reason=='cancelled' else 'done'

    def _run(self,context,mode,proxy,deadline):
        receiver=sender=process=None; reason='unavailable'
        def valid(): return not self._cancel.is_set() and self._valid(context)
        try:
            if not valid(): reason='cancelled'; return
            spawn=self._factory(); receiver,sender=spawn.Pipe(duplex=False); gate=spawn.Event()
            process=spawn.Process(target=diagnostic_worker,args=(sender,mode,proxy,deadline,gate),daemon=True)
            process.start()
            with self._lock: self._process=process
            sender.close()
            if not self._binder(SimpleNamespace(_handle=process.sentinel)): return
            if not valid(): reason='cancelled'; return
            gate.set()
            while self._clock()<deadline and valid():
                if receiver.poll(.025):
                    try: message=receiver.recv()
                    except EOFError: break
                    if not valid(): break
                    if not isinstance(message,tuple) or len(message)!=3: continue
                    key,status,value=message
                    if key not in ('proxy','dns','https','ip') or status not in ('pass','fail'): continue
                    if key=='ip' and status=='pass':
                        try: value=str(ipaddress.ip_address(value))
                        except (ValueError,TypeError): status='fail'; value=None
                    with self._lock:
                        if self._cancel.is_set(): break
                        row=next(r for r in self._data['checks'] if r['id']==key)
                        detail=DETAILS[status]
                        if status=='pass':
                            if key=='ip': detail=value
                            elif key=='proxy': detail='TCP-соединение доступно; авторизацию проверяет HTTPS.' if mode=='proxy' else 'Ядро работает, существующая проверка туннеля успешна.'
                            elif key=='dns': detail='Получен DNS-ответ через выбранный прокси (DoH); системный DNS не проверялся.' if mode=='proxy' else 'Системный getaddrinfo вернул адрес example.com через маршрутизацию TUN.'
                            elif key=='https': detail='Получен HTTPS-ответ через выбранный прокси.' if mode=='proxy' else 'Получен HTTPS-ответ через системную маршрутизацию TUN.'
                        row.update(status=status,detail=detail)
                elif not process.is_alive(): break
            reason='cancelled' if not valid() else ('timeout' if self._clock()>=deadline else 'unavailable')
        except Exception:
            reason='cancelled' if not valid() else 'unavailable'
        finally:
            exited=True
            if process is not None and process.pid is not None:
                try:
                    if process.is_alive(): process.terminate()
                    process.join(timeout=.45)
                    if process.is_alive(): process.kill(); process.join(timeout=.45)
                    exited=not process.is_alive()
                    if exited: process.close()
                except Exception: exited=False
            for pipe in (receiver,sender):
                if pipe is not None:
                    try: pipe.close()
                    except Exception: pass
            final_reason='cancelled' if not valid() else reason
            with self._lock:
                self._finish_rows(final_reason)
                if exited: self._process=None
                self._busy=False
                self._done.set()
