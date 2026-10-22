import unittest
from core.kill_switch import KillSwitch, Endpoint, ProtectionError, policy, BLOCK, PERMIT
from core.connection_log import ConnectionJournal

class MemoryBackend:
    def __init__(self): self.rules=()
    def read(self): return self.rules
    def replace(self,rules): self.rules=tuple(rules)

class ProtectionTests(unittest.TestCase):
    def test_reject_missing_verified_application_identity(self):
        guard=KillSwitch(MemoryBackend())
        with self.assertRaises(ProtectionError):
            guard.arm([Endpoint('203.0.113.7',1080)],b'')

    def test_dual_stack_owned_persistent_policy_and_explicit_release(self):
        backend=MemoryBackend(); guard=KillSwitch(backend)
        result=guard.arm([Endpoint('203.0.113.7',1080)],b'engine-path')
        self.assertTrue(result['armed']); self.assertTrue(result['boot_policy'])
        self.assertEqual(len([r for r in backend.rules if r.action==BLOCK and not r.boot]),6)
        for row in backend.rules:
            if row.name.startswith(('connect4-203','accept4-203')):
                self.assertIn(('app',0,b'engine-path'),row.conditions)
                self.assertIn(('port',0,1080),row.conditions)
                self.assertIn(('protocol',0,6),row.conditions)
        guard.disarm(); self.assertFalse(guard.status()['policy_present'])

    def test_readback_failure_prevents_success(self):
        backend=MemoryBackend(); backend.replace=lambda rules: None
        with self.assertRaises(ProtectionError):
            KillSwitch(backend).arm([Endpoint('203.0.113.7',1080)],b'engine-path')

    def test_endpoint_family_port_and_protocol_validation(self):
        self.assertEqual(Endpoint('2001:db8::1',443).address,'2001:db8::1')
        for args in [('name.invalid',443),('203.0.113.7',0),('203.0.113.7',443,1)]:
            with self.assertRaises(ValueError): Endpoint(*args)

    def test_bounded_private_journal_cursor_and_source(self):
        journal=ConnectionJournal(limit=2,clock=lambda:123)
        journal.append(destination='https://name:secret@example.test/private?q=secret',password='secret',protocol='tcp\n')
        first=journal.read()['rows'][0]
        self.assertEqual(first['destination'],'example.test')
        self.assertNotIn('password',first); self.assertEqual(first['protocol'],'tcp')
        self.assertEqual(journal.read()['source'],'unavailable')
        journal.append(kind='event'); journal.append(kind='event')
        self.assertEqual(len(journal.read()['rows']),2); self.assertTrue(journal.read()['truncated'])
        journal.clear(); journal.append(kind='event')
        self.assertEqual(journal.read()['rows'][0]['sequence'],4)


class LifecycleTests(unittest.TestCase):
    def session(self, reachable):
        from core.protection_session import ProtectionSession
        from unittest.mock import Mock
        events=[]
        backend=MemoryBackend()
        backend.app_id=lambda path:b'verified-engine'
        original=backend.replace
        def replace(rules):
            events.append(('policy',bool(rules))); original(rules)
        backend.replace=replace
        manager=Mock(); manager.bin_dir=None; manager.exe_path='engine'
        manager.proxy_reachable=reachable
        def start(proxy,**kwargs):
            events.append(('start',proxy.id))
            self.assertTrue(any(r.name=='packet4-deny' for r in backend.rules))
            manager.on_tunnel_ready()
        manager.start.side_effect=start
        session=ProtectionSession(manager,ConnectionJournal(),lambda:backend,lambda:99)
        session.cancel.wait=lambda seconds:session.cancel.is_set()
        return session,manager,backend,events

    def test_guard_precedes_tun_and_stop_retains_policy(self):
        from core.proxy_model import ProxyItem
        session,manager,backend,events=self.session(True)
        self.assertTrue(session.connect([ProxyItem('one','203.0.113.1',1080)]))
        self.assertEqual(events[0],('policy',True))
        self.assertEqual(session.state,'protected')
        session.stop()
        self.assertEqual(session.state,'blocked')
        self.assertTrue(session.guard.status()['armed'])
        self.assertFalse(any(any(c[0]=='interface' for c in r.conditions) for r in backend.rules))
        session.release(); self.assertEqual(backend.rules,())

    def test_exhaustion_single_pass_retains_deny(self):
        from core.proxy_model import ProxyItem
        session,manager,backend,events=self.session(False)
        self.assertFalse(session.connect([ProxyItem('one','203.0.113.1',1080),ProxyItem('two','203.0.113.2',1080)]))
        self.assertEqual([v for k,v in events if k=='start'],['one','two'])
        self.assertEqual(session.state,'blocked')
        self.assertTrue(session.guard.status()['armed'])
        self.assertFalse(any(r.action==PERMIT and any(c[0]=='remote' for c in r.conditions) for r in backend.rules))

    def test_cancel_prevents_next_candidate(self):
        from core.proxy_model import ProxyItem
        session,manager,backend,events=self.session(False)
        original=manager.start.side_effect
        def cancel(*args,**kwargs):
            original(*args,**kwargs); session.cancel.set()
        manager.start.side_effect=cancel
        session.connect([ProxyItem('one','203.0.113.1',1080),ProxyItem('two','203.0.113.2',1080)])
        self.assertEqual([v for k,v in events if k=='start'],['one'])
        self.assertTrue(session.guard.status()['armed'])

    def test_journal_redacts_bare_userinfo(self):
        journal=ConnectionJournal()
        journal.append(destination='name:private@example.test')
        self.assertEqual(journal.read()['rows'][0]['destination'],'example.test')


class ConfigTests(unittest.TestCase):
    def test_protected_config_offline_schema(self):
        import tempfile,json,subprocess,os
        from core.singbox_manager import SingBoxManager
        from core.proxy_model import ProxyItem
        manager=SingBoxManager.__new__(SingBoxManager)
        manager.protected=True
        with tempfile.TemporaryDirectory() as directory:
            manager.log_path=os.path.join(directory,'engine.log')
            for protocol in ('http','socks5'):
                config=manager.generate_config(ProxyItem('one','203.0.113.1',1080,protocol))
                self.assertEqual([x['tag'] for x in config['outbounds']],['proxy-out'])
                self.assertTrue(config['inbounds'][0]['strict_route'])
                self.assertEqual(config['route']['final'],'proxy-out')
                self.assertFalse(any(x.get('detour')=='direct' for x in config['dns']['servers']))
                self.assertEqual(config['experimental']['clash_api']['external_controller'].split(':')[0],'127.0.0.1')
                path=os.path.join(directory,'check.json')
                with open(path,'w',encoding='utf-8') as stream: json.dump(config,stream)
                result=subprocess.run(['bin/sing-box.exe','check','-c',path],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__': unittest.main()
