"""Single serialized protection lifecycle, independent of presentation."""
import dataclasses
import ipaddress
import socket
import os
import json
import threading
import time
from core.kill_switch import KillSwitch, WindowsWfpBackend, Endpoint, ProtectionError, tunnel_luid

class ProtectionSession:
    def __init__(self, manager, journal, backend_factory=WindowsWfpBackend, interface_lookup=tunnel_luid):
        self.manager=manager; self.journal=journal; self.backend_factory=backend_factory
        self.interface_lookup=interface_lookup; self.guard=None; self.cache={}
        self._dns_slots=threading.BoundedSemaphore(4)
        self.cancel=threading.Event(); self.generation=0; self.state='unarmed'
        directory=getattr(manager,'bin_dir',None)
        self.marker=os.path.join(os.path.dirname(directory),'protection-recovery.json') if isinstance(directory,str) else None
        if self.marker and os.path.exists(self.marker):
            self.state='unknown'
            try:
                with open(self.marker,'rb') as stream: payload=stream.read(65537)
                if len(payload)>65536: raise ValueError('recovery metadata oversized')
                data=json.loads(payload)
                self.cache={str(k):str(ipaddress.ip_address(v)) for k,v in data.get('endpoints',{}).items()}
                status=self._guard().status()
                self.state='blocked' if status['armed'] else 'unknown'
            except Exception:
                self.state='unknown'

    def _guard(self):
        if self.guard is None: self.guard=KillSwitch(self.backend_factory())
        return self.guard
    def _snapshot(self, proxies):
        protected=self._guard().status()['policy_present']
        snapshots=[]
        deadline=time.monotonic()+15
        for proxy in proxies:
            item=dataclasses.replace(proxy)
            try:
                address=str(ipaddress.ip_address(item.host))
            except ValueError:
                address=self.cache.get(item.id)
                if not address and not protected and time.monotonic()<deadline and not self.cancel.is_set() and self._dns_slots.acquire(blocking=False):
                    result=[]; done=threading.Event()
                    def resolve(host=item.host, result=result, done=done):
                        try: result.extend(socket.getaddrinfo(host,None,socket.AF_INET,socket.SOCK_STREAM))
                        except OSError: pass
                        finally:
                            done.set()
                            self._dns_slots.release()
                    threading.Thread(target=resolve,daemon=True).start()
                    done.wait(min(3,max(0,deadline-time.monotonic())))
                    if result: address=result[0][4][0]
            if not address:
                self.journal.append(kind='resolution',proxy_id=item.id,state='unavailable; cached numeric endpoint required')
                continue
            self.cache[item.id]=address; item.host=address; snapshots.append(item)
        return snapshots
    def connect(self,proxies):
        self.cancel.clear(); self.generation+=1; self.state='connecting'
        candidates=self._snapshot(tuple(proxies))
        self.manager._verify_or_raise()
        app=self._guard().backend.app_id(self.manager.exe_path)
        if self.marker:
            from core.storage import _atomic_write_file
            _atomic_write_file(self.marker,json.dumps({'owner':'038538ab-ff8d-4956-9ae6-531ed0cf58a4',
                'endpoints':self.cache,'recovery':'python -m core.kill_switch --release'}).encode())
        # No candidate still installs a deny-only policy before returning blocked.
        self._guard().arm((),app)
        self.state='blocked'
        for index,proxy in enumerate(candidates):
            if self.cancel.is_set(): break
            if index and self.cancel.wait(min(30,2**min(index,5))): break
            endpoints=(Endpoint(proxy.host,proxy.port),)
            # UDP SOCKS relay endpoints are not known a priori. Disable UDP in the
            # strict engine config rather than granting arbitrary relay egress.
            self._guard().arm(endpoints,app)
            self.state='switching'
            self.journal.append(kind='failover',proxy_id=proxy.id,state='connecting',session=self.generation)
            self.manager.protected=True
            self.manager.on_tunnel_ready=lambda: self._guard().arm(endpoints,app,self.interface_lookup())
            try:
                self.manager.start(proxy,bypass_telegram=False)
                if self.cancel.is_set() or not self.manager.proxy_reachable:
                    raise ProtectionError('Tunnel verification failed or cancelled')
                self.state='protected'
                self.journal.append(kind='protection',proxy_id=proxy.id,state='verified tunnel',session=self.generation)
                return True
            except Exception:
                self.manager.stop()
                self._guard().arm((),app)
                self.journal.append(kind='failover',proxy_id=proxy.id,state='failed',session=self.generation)
        self.manager.stop(); self._guard().arm((),app); self.state='blocked'
        return False
    def stop(self):
        self.cancel.set(); self.generation+=1
        self.manager.stop()
        self.journal.source(False)
        if self.guard is not None:
            app=self.guard.backend.app_id(self.manager.exe_path)
            if self.guard.status()['policy_present']: self.guard.arm((),app)
        self.state='blocked' if self.guard and self.guard.status()['policy_present'] else 'unarmed'
    def release(self):
        self.stop()
        self._guard().disarm(); self.state='unarmed'
        if self.marker and os.path.exists(self.marker): os.remove(self.marker)
        self.journal.append(kind='protection',state='explicit release')
