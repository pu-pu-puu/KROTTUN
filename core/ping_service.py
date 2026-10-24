"""Bounded manual TCP measurements using the current OS route, never a fallback."""
import copy
import math
import multiprocessing
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from core.win_job import bind_to_lifetime


def perform_pings(targets, deadline, emit, connect=socket.create_connection, clock=time.monotonic, mode='direct'):
    def check(target):
        remaining=min(2.5, deadline-clock())
        if remaining<=0: return
        started=clock()
        try:
            with connect((target['host'],target['port']),timeout=remaining) as sock:
                if mode == 'tun':
                    # TUN may acknowledge TCP locally: require a response from the
                    # known proxy protocol, without sending stored credentials.
                    response=bytearray()
                    def receive(limit):
                        timeout=min(2.5,deadline-clock())
                        if timeout<=0: raise TimeoutError()
                        sock.settimeout(timeout)
                        chunk=sock.recv(limit)
                        if not chunk: raise ValueError()
                        return chunk
                    if target['protocol']=='socks5':
                        sock.sendall(b'\x05\x02\x00\x02')
                        while len(response)<2: response.extend(receive(2-len(response)))
                        if response[0]!=5 or response[1] not in (0,2,255): raise ValueError()
                    elif target['protocol']=='http':
                        sock.sendall(b'CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n')
                        while b'\r\n' not in response and len(response)<256:
                            response.extend(receive(min(64,256-len(response))))
                        import re
                        if b'\r\n' not in response: raise ValueError()
                        if not re.fullmatch(rb'HTTP/1\.[01] [1-5][0-9]{2}(?: [^\r\n]*)?',bytes(response).split(b'\r\n')[0]): raise ValueError()
                    else: raise ValueError()
            latency=max(0,round((clock()-started)*1000))
            emit((target['id'],latency,'alive'))
        except Exception:
            emit((target['id'],None,'timeout'))
    # At most eight socket tasks; the parent kills this entire process at deadline,
    # including DNS calls that do not honor socket timeouts.
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(check,targets))


def ping_worker(sender, targets, deadline, gate, mode):
    try:
        if gate.wait(max(0,deadline-time.monotonic())) and time.monotonic()<deadline:
            # Serialize pipe sends from the eight socket threads.
            lock=threading.Lock()
            def emit(value):
                with lock: sender.send(value)
            perform_pings(targets,deadline,emit,mode=mode)
    except Exception:
        pass
    finally:
        sender.close()


class PingService:
    def __init__(self, valid, context_factory=None, binder=bind_to_lifetime, clock=time.monotonic):
        self._valid=valid; self._factory=context_factory or (lambda:multiprocessing.get_context('spawn'))
        self._binder=binder; self._clock=clock; self._lock=threading.Lock()
        self._process=None; self._busy=False; self._cancel=threading.Event()
        self._done=threading.Event(); self._done.set()

    def cancel(self):
        self._cancel.set()

    def _reap(self):
        if not self._busy and self._process is not None:
            try:
                if not self._process.is_alive():
                    self._process.join(timeout=0); self._process.close(); self._process=None
            except Exception: pass

    def stop(self, timeout=1.1):
        self.cancel()
        if not self._done.wait(timeout): return False
        with self._lock:
            self._reap()
            return not self._busy and self._process is None

    def run(self, context, targets, mode):
        with self._lock:
            self._reap()
            if self._busy or self._process is not None:
                return {'success':False,'busy':True,'error':'Замер уже выполняется или процесс ещё завершается'}
            self._busy=True; self._cancel.clear(); self._done.clear()
        rows={t['id']:{'id':t['id'],'latency':None,'status':'notchecked'} for t in targets}
        receiver=sender=process=None; exited=True; error=None
        deadline=self._clock()+8
        def valid(): return not self._cancel.is_set() and self._valid(context)
        try:
            if not valid(): raise InterruptedError()
            spawn=self._factory(); receiver,sender=spawn.Pipe(duplex=False); gate=spawn.Event()
            process=spawn.Process(target=ping_worker,args=(sender,copy.deepcopy(targets),deadline,gate,mode),daemon=True)
            process.start()
            with self._lock: self._process=process
            sender.close()
            if not self._binder(SimpleNamespace(_handle=process.sentinel)):
                raise RuntimeError()
            if not valid(): raise InterruptedError()
            gate.set()
            while self._clock()<deadline and valid():
                if receiver.poll(.025):
                    try: message=receiver.recv()
                    except EOFError: break
                    if not isinstance(message,tuple) or len(message)!=3: continue
                    key,latency,status=message
                    if key not in rows or status not in ('alive','timeout'): continue
                    if status=='alive' and (isinstance(latency,bool) or not isinstance(latency,(int,float)) or not math.isfinite(latency) or latency<0): continue
                    if not valid(): break
                    rows[key].update(latency=latency if status=='alive' else None,status=status)
                    if all(r['status']!='notchecked' for r in rows.values()): break
                elif not process.is_alive(): break
            if not valid(): raise InterruptedError()
        except InterruptedError:
            error='Состояние подключения изменилось. Повторите замер.'
        except Exception:
            error='Не удалось безопасно выполнить TCP-замер. Повторите попытку.'
        finally:
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
            if not valid(): error='Состояние подключения изменилось. Повторите замер.'
            if not exited: error='Выход процесса замера не подтверждён. Повторите после его завершения.'
            with self._lock:
                if exited: self._process=None
                self._busy=False; self._done.set()
        if error: return {'success':False,'error':error,'mode':mode}
        return {'success':True,'mode':mode,'results':copy.deepcopy(list(rows.values()))}
