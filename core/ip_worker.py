"""Single-flight IP query with an owned, gated and killable spawn child."""
import ipaddress
import multiprocessing
import threading
import time
from types import SimpleNamespace

from core.ip_service import get_current_system_ip
from core.win_job import bind_to_lifetime


def unavailable():
    return {'ip': 'IP недоступен', 'country_code': '', 'status': 'unavailable'}


def ip_worker(sender, deadline, gate):
    try:
        if gate.wait(max(0, deadline - time.monotonic())):
            remaining = deadline - time.monotonic()
            if remaining > 0:
                sender.send(get_current_system_ip(timeout=remaining))
    except Exception:
        pass
    finally:
        sender.close()


class IpQueryService:
    def __init__(self, valid, binder=bind_to_lifetime, context_factory=None, target=ip_worker):
        self._valid = valid
        self._binder = binder
        self._factory = context_factory or (lambda: multiprocessing.get_context('spawn'))
        self._target = target
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._done = threading.Event(); self._done.set()
        self._busy = False
        self._process = None

    def cancel(self):
        self._cancel.set()

    def _reap(self):
        if self._process is not None and not self._busy:
            try:
                if not self._process.is_alive():
                    self._process.join(timeout=0)
                    self._process.close()
                    self._process = None
            except Exception:
                pass

    def stop(self, timeout=1.1):
        self.cancel()
        if not self._done.wait(timeout):
            return False
        with self._lock:
            self._reap()
            return not self._busy and self._process is None

    def run(self, context, timeout=3.0):
        with self._lock:
            self._reap()
            if self._busy or self._process is not None:
                return unavailable()
            self._busy = True
            self._cancel.clear(); self._done.clear()
        receiver = sender = process = None
        exited = True
        data = unavailable()
        deadline = time.monotonic() + timeout

        def valid():
            return not self._cancel.is_set() and self._valid(context)

        try:
            if not valid(): return unavailable()
            spawn = self._factory()
            receiver, sender = spawn.Pipe(duplex=False)
            gate = spawn.Event()
            process = spawn.Process(target=self._target, args=(sender, deadline, gate), daemon=True)
            process.start()
            with self._lock: self._process = process
            sender.close()
            if not self._binder(SimpleNamespace(_handle=process.sentinel)):
                return unavailable()
            if not valid() or time.monotonic() >= deadline: return unavailable()
            gate.set()
            while time.monotonic() < deadline and valid():
                if receiver.poll(.025):
                    message = receiver.recv()
                    if isinstance(message, dict) and message.get('status') == 'ready':
                        address = str(ipaddress.ip_address(message.get('ip')))
                        data = {'ip': address, 'country': '', 'country_code': '', 'status': 'ready'}
                    break
                if not process.is_alive(): break
        except Exception:
            data = unavailable()
        finally:
            if process is not None and process.pid is not None:
                # Try kill even when terminate itself fails. Retain the handle
                # if neither operation produces an observable exit.
                try:
                    if process.is_alive(): process.terminate()
                    process.join(timeout=.4)
                except Exception:
                    pass
                try:
                    if process.is_alive(): process.kill(); process.join(timeout=.4)
                    exited = not process.is_alive()
                    if exited: process.close()
                except Exception:
                    exited = False
            for pipe in (receiver, sender):
                if pipe is not None:
                    try: pipe.close()
                    except Exception: pass
            if not exited or not valid() or time.monotonic() >= deadline:
                data = unavailable()
            with self._lock:
                self._process = None if exited else process
                self._busy = False; self._done.set()
        return data
