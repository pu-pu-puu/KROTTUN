"""Fail-closed, machine-wide WFP policy. Call explicitly; never armed on import.

Packet egress + ALE authorization are both required. VM capture is mandatory:
readback proves policy installation, not packet-level absence of leaks.
"""
import ctypes as C
import ipaddress
import os
import threading
import uuid
from dataclasses import dataclass
from core.wfp_native import GUID, Blob, Display, Value, Condition, Action, Filter, Sublayer, KEYS, U32, U64, P, EnumTemplate

OWNER=uuid.UUID('038538ab-ff8d-4956-9ae6-531ed0cf58a4')
BLOCK,PERMIT=0x1001,0x1002

@dataclass(frozen=True)
class Endpoint:
    address: str
    port: int
    protocol: int = 6
    def __post_init__(self):
        object.__setattr__(self,'address',str(ipaddress.ip_address(self.address)))
        if not 1 <= self.port <= 65535 or self.protocol not in (6,17):
            raise ValueError('invalid proxy endpoint')

@dataclass(frozen=True)
class Rule:
    name: str
    layer: str
    action: int
    weight: int
    conditions: tuple = ()
    boot: bool = False

def policy(endpoints, app, interface=None):
    rules=[]
    for family in (4,6):
        # Boot policy deliberately permits nothing until persistent policy loads.
        rules.append(Rule('boot'+str(family),'packet'+str(family),BLOCK,0,boot=True))
        for layer in ('packet','connect','accept'):
            tag=layer+str(family)
            rules.append(Rule(tag+'-deny',tag,BLOCK,0))
            rules.append(Rule(tag+'-loopback',tag,PERMIT,30,(('flags',6,1),)))
            if interface:
                rules.append(Rule(tag+'-tun',tag,PERMIT,20,(('interface',0,interface),)))
            for endpoint in endpoints:
                if ipaddress.ip_address(endpoint.address).version != family: continue
                cond=(('remote',0,endpoint.address),)
                if layer != 'packet':
                    cond += (('app',0,app),('port',0,endpoint.port),('protocol',0,endpoint.protocol))
                name=tag+'-'+endpoint.address+'-'+str(endpoint.port)+'-'+str(endpoint.protocol)
                rules.append(Rule(name,tag,PERMIT,10,cond))
    return tuple(rules)

class ProtectionError(RuntimeError): pass

class KillSwitch:
    def __init__(self,backend):
        self.backend=backend
        self._lock=threading.RLock()
    def status(self):
        with self._lock:
            rows=self.backend.read()
            required={(layer+str(f)+'-deny') for layer in ('packet','connect','accept') for f in (4,6)}
            names={r.name for r in rows}
            defaults={r.name for r in rows if r.action==BLOCK and not r.conditions and not r.boot}
            return {'armed':required <= defaults,'policy_present':bool(rows),
                    'boot_policy':{'boot4','boot6'} <= names,
                    'validation':'native readback; VM packet capture still required'}
    def arm(self,endpoints,app,interface=None):
        if not isinstance(app, bytes) or not app:
            raise ProtectionError("Verified sing-box application identity is required")
        with self._lock:
            desired=policy(tuple(endpoints),app,interface)
            self.backend.replace(desired)
            if set(self.backend.read()) != set(desired):
                raise ProtectionError('WFP readback mismatch; do not start TUN')
            return self.status()
    def disarm(self):
        with self._lock:
            self.backend.replace(())
            if self.backend.read(): raise ProtectionError('WFP release readback mismatch')

class WindowsWfpBackend:
    """Own sublayer, NULL provider: no service-dependent provider activation.

    Do not substitute Windows Firewall rules. All replacements use one native
    transaction. Native GUIDs and immutable rule metadata identify owned policy.
    """
    def __init__(self):
        if os.name != 'nt': raise ProtectionError('Windows WFP is required')
        self.dll=C.WinDLL('fwpuclnt.dll',use_last_error=True)
        self.handle=P()
        signatures={
            'FwpmEngineOpen0':([C.c_wchar_p,U32,P,P,C.POINTER(P)],U32),
            'FwpmEngineClose0':([P],U32),
            'FwpmTransactionBegin0':([P,U32],U32),
            'FwpmTransactionCommit0':([P],U32),'FwpmTransactionAbort0':([P],U32),
            'FwpmSubLayerAdd0':([P,C.POINTER(Sublayer),P],U32),
            'FwpmFilterAdd0':([P,C.POINTER(Filter),P,C.POINTER(U64)],U32),
            'FwpmFilterDeleteByKey0':([P,C.POINTER(GUID)],U32),
            'FwpmFilterCreateEnumHandle0':([P,P,C.POINTER(P)],U32),
            'FwpmFilterEnum0':([P,P,U32,C.POINTER(P),C.POINTER(U32)],U32),
            'FwpmFilterDestroyEnumHandle0':([P,P],U32),
            'FwpmFreeMemory0':([C.POINTER(P)],None),
            'FwpmGetAppIdFromFileName0':([C.c_wchar_p,C.POINTER(P)],U32)}
        for name,(args,result) in signatures.items():
            fn=getattr(self.dll,name); fn.argtypes=args; fn.restype=result
        self._call('FwpmEngineOpen0',None,10,None,None,C.byref(self.handle))
    def _call(self,name,*args):
        result=getattr(self.dll,name)(*args)
        if result: raise ProtectionError('%s failed (0x%08x)'%(name,result))
    def app_id(self,path):
        ptr=P()
        self._call('FwpmGetAppIdFromFileName0',os.path.abspath(path),C.byref(ptr))
        try:
            blob=C.cast(ptr,C.POINTER(Blob)).contents
            return C.string_at(blob.data,blob.size)
        finally: self.dll.FwpmFreeMemory0(C.byref(ptr))
    def _owned(self,allow_disabled=False):
        # A non-NULL FWPM_FILTER_ENUM_TEMPLATE0 requires a real layerKey.
        # Enumerate every production layer separately so boot/disabled filters
        # remain visible without using an invalid all-zero layer GUID.
        result=[]
        for family in (4,6):
            for layer in ('packet','connect','accept'):
                result.extend(self._owned_layer(layer+str(family),allow_disabled))
        return result
    def _owned_layer(self,layer,allow_disabled=False):
        enum=P(); result=[]
        template=EnumTemplate(); template.flags=0x18; template.action_mask=0xffffffff
        template.layer=GUID.of(KEYS[layer])
        self._call('FwpmFilterCreateEnumHandle0',self.handle,C.byref(template),C.byref(enum))
        try:
            while True:
                ptr=P(); count=U32()
                self._call('FwpmFilterEnum0',self.handle,enum,128,C.byref(ptr),C.byref(count))
                try:
                    entries=C.cast(ptr,C.POINTER(C.POINTER(Filter)))
                    for i in range(count.value):
                        row=entries[i].contents
                        if bytes(row.sublayer)==OWNER.bytes_le:
                            result.append(self._decode(row,allow_disabled))
                finally:
                    if ptr: self.dll.FwpmFreeMemory0(C.byref(ptr))
                if count.value < 128: break
        finally: self.dll.FwpmFilterDestroyEnumHandle0(self.handle,enum)
        return result
    def _decode(self,row,allow_disabled=False):
        import json
        try:
            metadata=json.loads(C.string_at(row.data.data,row.data.size))
            conditions=[]
            for i in range(row.count):
                condition=row.conditions[i]
                key=next((k for k,v in KEYS.items() if bytes(GUID.of(v))==bytes(condition.key)),None)
                if key is None: raise ValueError('unknown condition')
                val=condition.value
                allowed={'remote':(3,11),'app':(12,),'interface':(4,),'port':(2,),'protocol':(1,),'flags':(3,)}
                if val.type not in allowed[key]: raise ValueError('unexpected condition value type')
                if key=='remote':
                    raw=(val.value.u32.to_bytes(4,'big') if val.type==3 else C.string_at(val.value.pointer,16))
                    value=str(ipaddress.ip_address(raw))
                elif key=='app':
                    blob=C.cast(val.value.pointer,C.POINTER(Blob)).contents
                    value=C.string_at(blob.data,blob.size)
                elif key=='interface': value=C.cast(val.value.pointer,C.POINTER(U64)).contents.value
                else: value={1:val.value.u8,2:val.value.u16,3:val.value.u32}[val.type]
                conditions.append((key,condition.match,value))
            layer=next(k for k,v in KEYS.items() if bytes(GUID.of(v))==bytes(row.layer))
            if row.provider or (row.flags & 0x20 and not allow_disabled): raise ValueError('disabled or foreign provider')
            if not row.flags & (2 if metadata['boot'] else 1): raise ValueError('nonpersistent policy')
            if row.weight.type != 4: raise ValueError("unexpected weight type")
            weight=C.cast(row.weight.value.pointer,C.POINTER(U64)).contents.value
            rule=Rule(metadata['name'],layer,row.action.type,weight,tuple(conditions),metadata['boot'])
            if bytes(row.key)!=uuid.uuid5(OWNER,rule.name).bytes_le: raise ValueError('ownership key mismatch')
            return rule
        except Exception as exc:
            raise ProtectionError('Owned WFP policy is corrupt; manual recovery required') from exc
    def read(self): return tuple(self._owned())
    def _add(self,rule):
        import json
        keep=[]
        def pointer(value):
            keep.append(value); return C.cast(C.pointer(value),P).value
        native_conditions=[]
        for key,match,value in rule.conditions:
            val=Value()
            if key=='remote':
                address=ipaddress.ip_address(value)
                if address.version==4: val.type=3; val.value.u32=int(address)
                else: val.type=11; val.value.pointer=pointer((C.c_ubyte*16).from_buffer_copy(address.packed))
            elif key=='app':
                data=C.create_string_buffer(value); keep.append(data)
                val.type=12; val.value.pointer=pointer(Blob(len(value),C.cast(data,P)))
            elif key=='interface': val.type=4; val.value.pointer=pointer(U64(value))
            else:
                val.type={'port':2,'protocol':1,'flags':3}[key]
                setattr(val.value,{1:'u8',2:'u16',3:'u32'}[val.type],value)
            native_conditions.append(Condition(GUID.of(KEYS[key]),match,val))
        conditions=(Condition*len(native_conditions))(*native_conditions)
        metadata=json.dumps({'name':rule.name,'boot':rule.boot}).encode()
        data=C.create_string_buffer(metadata)
        row=Filter(); row.key=GUID.of(uuid.uuid5(OWNER,rule.name)); row.display=Display('KROTTUN '+rule.name,None)
        row.flags=2 if rule.boot else 1; row.sublayer=GUID.of(OWNER); row.layer=GUID.of(KEYS[rule.layer])
        row.data=Blob(len(metadata),C.cast(data,P)); row.weight.type=4
        row.weight.value.pointer=pointer(U64(rule.weight)); row.count=len(conditions); row.conditions=conditions
        row.action=Action(rule.action,GUID()); native_id=U64()
        self._call('FwpmFilterAdd0',self.handle,C.byref(row),None,C.byref(native_id))
    def replace(self,rules):
        self._call('FwpmTransactionBegin0',self.handle,0)
        try:
            sub=Sublayer(); sub.key=GUID.of(OWNER); sub.display=Display('KROTTUN protection',None); sub.flags=1; sub.weight=0x7fff
            result=self.dll.FwpmSubLayerAdd0(self.handle,C.byref(sub),None)
            if result not in (0,0x80320009): raise ProtectionError('WFP sublayer error 0x%08x'%result)
            for rule in self._owned(allow_disabled=True):
                key=GUID.of(uuid.uuid5(OWNER,rule.name))
                self._call('FwpmFilterDeleteByKey0',self.handle,C.byref(key))
            for rule in rules: self._add(rule)
            if set(self.read()) != set(rules): raise ProtectionError('WFP transaction readback mismatch')
            self._call('FwpmTransactionCommit0',self.handle)
        except BaseException:
            self.dll.FwpmTransactionAbort0(self.handle)
            raise
    def close(self):
        if self.handle:
            self.dll.FwpmEngineClose0(self.handle); self.handle=P()


def tunnel_luid(alias='sing-tun'):
    dll=C.WinDLL('iphlpapi.dll'); fn=dll.ConvertInterfaceAliasToLuid
    fn.argtypes=[C.c_wchar_p,C.POINTER(U64)]; fn.restype=U32
    luid=U64(); result=fn(alias,C.byref(luid))
    if result: raise ProtectionError('TUN interface lookup failed: %s'%result)
    return luid.value


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='KROTTUN owned WFP recovery; close the GUI first')
    parser.add_argument('--release',action='store_true',required=True)
    parser.parse_args()
    from core.paths import get_secure_bin_dir
    import psutil
    engine=os.path.normcase(os.path.join(get_secure_bin_dir(),'sing-box.exe'))
    for process in psutil.process_iter(['exe']):
        try:
            if os.path.normcase(process.info.get('exe') or '')==engine:
                process.terminate(); process.wait(timeout=5)
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            raise ProtectionError('Cannot verify engine shutdown; close it before recovery')
    backend=WindowsWfpBackend()
    try:
        KillSwitch(backend).disarm()
        marker=os.path.join(os.path.dirname(get_secure_bin_dir()),'protection-recovery.json')
        if os.path.exists(marker): os.remove(marker)
        print('KROTTUN owned filters removed. Other firewall policy retained.')
    finally: backend.close()
