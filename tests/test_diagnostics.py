import threading
import unittest
from unittest.mock import Mock, patch, MagicMock
from core.proxy_model import ProxyItem
from gui.app_webview import ProxyTunBridgeApi, TunState

class DiagnosticsTests(unittest.TestCase):
    def test_unavailable_diagnostics_has_explicit_context_reason(self):
        for protection, expected in [('blocked','protection_blocked'),('unknown','protection_unknown'),('unarmed','no_proxy')]:
            api=self.bridge(); api._protection.state=protection
            if protection=='unarmed': api.proxies=[]; api.selected_proxy_id=None
            with patch('gui.app_webview.system_proxy_flag',return_value=False),patch('multiprocessing.get_context') as spawn:
                self.assertTrue(api.start_diagnostics()['success'])
                data=api.get_diagnostics()
            self.assertEqual(data['availability_reason'],expected)
            self.assertEqual(data['status'],'done');spawn.assert_not_called()
            api._protection.release.assert_not_called();api._sb.stop.assert_not_called()

    def test_stale_or_cancelled_diagnostic_cannot_claim_confirmed_blocking(self):
        for change in ['generation','cancel']:
            api=self.bridge();api._protection.state='blocked'
            with patch('gui.app_webview.system_proxy_flag',return_value=False):api.start_diagnostics()
            if change=='generation':api._protection.generation+=1
            else:api.cancel_diagnostics()
            data=api.get_diagnostics()
            self.assertEqual(data['status'],'cancelled')
            self.assertIsNone(data['availability_reason'])

    def test_live_or_transitioning_core_does_not_claim_disconnected_blocking(self):
        for state,running in [(TunState.STARTING,False),(TunState.IDLE,True)]:
            api=self.bridge();api._state=state;api._sb.is_running.return_value=running
            api._protection.state='blocked'
            with patch('gui.app_webview.system_proxy_flag',return_value=False):api.start_diagnostics()
            self.assertNotEqual(api.get_diagnostics()['availability_reason'],'protection_blocked')

    def bridge(self):
        api=ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock=threading.RLock(); api._closing=False; api._ip_gen=1
        api._state=TunState.IDLE; api.selected_proxy_id='one'
        api.proxies=[ProxyItem('one','proxy.invalid',1080)]
        api._protection=Mock(state='unarmed',generation=1,cancel=threading.Event())
        api._sb=Mock(process=None,proxy_reachable=False); api._sb.is_running.return_value=False
        return api

    def test_blocked_never_spawns_and_registry_unknown_is_honest(self):
        api=self.bridge(); api._protection.state='blocked'
        with patch('multiprocessing.get_context') as spawn, patch.dict('sys.modules',{'winreg':None}):
            result=api.start_diagnostics(); data=api.get_diagnostics()
        self.assertTrue(result['success']); spawn.assert_not_called()
        self.assertEqual(len(data['checks']),5)
        self.assertTrue(all(c['status']=='skipped' for c in data['checks']))

    def test_cancel_discards_completed_network_rows(self):
        from core.diagnostics import DiagnosticsService
        service=DiagnosticsService(lambda context: True)
        service.start(None,None,flag=False)
        service._data['checks'][0].update(status='pass',detail='old route')
        service.cancel()
        data=service.snapshot()
        self.assertEqual(data['status'],'cancelled')
        self.assertEqual(data['checks'][0]['status'],'skipped')
        self.assertNotIn('old route',str(data))

    def test_transport_modes_are_explicit_and_bodies_bounded(self):
        from core.diagnostics import perform_checks
        import json
        for mode in ('proxy','protected'):
            session=MagicMock(); session.__enter__.return_value=session
            def response(url, **kwargs):
                body = b'ok'
                if 'dns-query?' in url: body=json.dumps({'Status':0,'Answer':[{'type':1,'data':'192.0.2.1'}]}).encode()
                if 'ipify' in url: body=b'{"ip":"192.0.2.2"}'
                reply=MagicMock(); reply.__enter__.return_value=reply
                reply.status_code=200; reply.iter_content.return_value=iter([body])
                return reply
            session.get.side_effect=response
            resolve=Mock(return_value=[('address',)]); connect=MagicMock(); emitted=[]
            perform_checks(mode,ProxyItem('one','proxy.invalid',1080),100,emitted.append,
                           lambda:session,resolve,connect,lambda:0)
            self.assertFalse(session.trust_env)
            self.assertEqual([r[1] for r in emitted],['pass']*4)
            self.assertEqual(session.get.call_count,3 if mode=='proxy' else 2)
            for call in session.get.call_args_list:
                self.assertFalse(call.kwargs['allow_redirects']); self.assertTrue(call.kwargs['stream'])
                self.assertLessEqual(call.kwargs['timeout'],2.5)
            if mode=='proxy':
                resolve.assert_not_called(); connect.assert_called_once()
                self.assertTrue(session.proxies['https'].startswith('socks5h://'))
                self.assertEqual(session.get.call_args_list[0].kwargs['headers']['Accept'],'application/dns-json')
            else:
                resolve.assert_called_once(); connect.assert_not_called()

    def test_healthy_runtime_does_not_confirm_tunnel_when_current_https_fails(self):
        from core.diagnostics import perform_checks
        api=self.bridge(); api._state=TunState.RUNNING
        api._protection.state='protected'; api._sb.process=object()
        api._sb.is_running.return_value=True; api._sb.proxy_reachable=True
        _,mode,proxy=api._diagnostic_context()
        self.assertEqual(mode,'protected')
        session=MagicMock(); session.__enter__.return_value=session
        emitted=[]; before_https=[]
        def timeout(url, **kwargs):
            if url=='https://example.com': before_https.extend(emitted)
            raise TimeoutError()
        session.get.side_effect=timeout
        connect=MagicMock()
        perform_checks(mode,proxy,100,emitted.append,lambda:session,
                       Mock(return_value=[('address',)]),connect,lambda:0)
        statuses={key:status for key,status,_ in emitted}
        self.assertEqual(statuses['https'],'fail')
        self.assertEqual(statuses['ip'],'fail')
        self.assertEqual(statuses['proxy'],'fail')
        self.assertFalse(any(key=='proxy' and status=='pass' for key,status,_ in before_https))
        connect.assert_not_called()

    def test_bridge_context_rejects_selection_edit_delete_cancel_and_process_changes(self):
        for change in ('selection','edit','delete','cancel','process','generation','close','stop','release'):
            api=self.bridge(); context,mode,_=api._diagnostic_context()
            self.assertEqual(mode,'proxy'); self.assertTrue(api._diagnostic_valid(context))
            if change=='selection': api.selected_proxy_id='other'
            elif change=='edit': api.proxies=[ProxyItem('one','proxy.invalid',1080)]
            elif change=='delete': api.proxies=[]
            elif change=='cancel': api._protection.cancel.set()
            elif change=='process': api._sb.process=object()
            elif change=='generation': api._protection.generation+=1
            elif change=='close': api._closing=True
            elif change=='stop': api._state=TunState.STOPPING
            elif change=='release': api._release_pending=True
            self.assertFalse(api._diagnostic_valid(context),change)

    def test_job_gate_singleflight_safe_results_and_cleanup(self):
        from core.diagnostics import DiagnosticsService
        callbacks=[]; events=[]
        process=Mock(pid=7,sentinel=3); process.is_alive.return_value=False
        process.start.side_effect=lambda:events.append('start')
        gate=Mock(); gate.set.side_effect=lambda:events.append('gate')
        receiver=Mock(); receiver.poll.side_effect=[True,True,True,False]
        receiver.recv.side_effect=[('https','pass',None),('ip','pass','invalid input'),('dns','bad status','private error')]
        spawn=Mock(); spawn.Pipe.return_value=(receiver,Mock()); spawn.Process.return_value=process; spawn.Event.return_value=gate
        binder=Mock(side_effect=lambda handle:events.append('bind') or True)
        service=DiagnosticsService(lambda context:True,lambda:spawn,binder,lambda:0)
        with patch('core.diagnostics.threading.Thread',side_effect=lambda **kwargs:callbacks.append(kwargs['target']) or Mock()):
            self.assertTrue(service.start('context','protected',flag=False)['success'])
            self.assertTrue(service.start('context','protected')['busy'])
        # Run the captured controller with the public start arguments and a fixed deadline.
        service._run('context','protected',None,10.5)
        self.assertEqual(events,['start','bind','gate'])
        data=service.snapshot(); self.assertEqual(data['status'],'done')
        self.assertEqual(data['checks'][2]['status'],'pass')
        self.assertEqual(data['checks'][3]['status'],'fail')
        self.assertNotIn('private error',str(data)); self.assertNotIn('invalid input',str(data))
        data['checks'].clear(); self.assertEqual(len(service.snapshot()['checks']),5)
        process.close.assert_called_once()

    def test_job_binding_failure_never_opens_gate_and_unconfirmed_exit_keeps_ownership(self):
        from core.diagnostics import DiagnosticsService
        process=Mock(pid=7,sentinel=3); process.is_alive.return_value=True
        spawn=Mock(); spawn.Pipe.return_value=(Mock(),Mock()); spawn.Process.return_value=process
        service=DiagnosticsService(lambda context:True,lambda:spawn,lambda handle:False,lambda:0)
        with patch('core.diagnostics.threading.Thread'):
            service.start('context','protected',flag=None)
        service._run('context','protected',None,10.5)
        spawn.Event.return_value.set.assert_not_called()
        process.terminate.assert_called_once(); process.kill.assert_called_once(); process.close.assert_not_called()
        self.assertTrue(service.start('context','protected')['busy'])

    def test_worker_gate_prevents_transport_and_timeout_kills_worker(self):
        from core.diagnostics import diagnostic_worker, DiagnosticsService
        gate=Mock(); gate.wait.return_value=False
        with patch('core.diagnostics.perform_checks') as network:
            diagnostic_worker(Mock(),'proxy',None,10.5,gate)
        network.assert_not_called()
        process=Mock(pid=7,sentinel=3); process.is_alive.side_effect=[True,True,False,False]
        spawn=Mock(); spawn.Pipe.return_value=(Mock(),Mock()); spawn.Process.return_value=process
        times=iter([0,0,20,20])
        service=DiagnosticsService(lambda context:True,lambda:spawn,lambda handle:True,lambda:next(times,20))
        with patch('core.diagnostics.threading.Thread'): service.start('context','protected')
        service._run('context','protected',None,10.5)
        process.kill.assert_called_once()
        self.assertIn('Время проверки истекло',str(service.snapshot()))

    def test_context_retains_original_selected_object_for_identity_comparison(self):
        api=self.bridge(); original=api.proxies[0]
        context,mode,_=api._diagnostic_context()
        self.assertIs(context[-1],original)
        api.proxies=[ProxyItem('one','proxy.invalid',1080)]
        self.assertFalse(api._diagnostic_valid(context))

    def test_release_does_not_remove_policy_until_diagnostic_exit_is_confirmed(self):
        api=self.bridge(); api._op_lock=threading.Lock()
        api._diagnostics=Mock(); api._diagnostics.stop.return_value=False
        result=api.release_protection()
        self.assertFalse(result['success'])
        api._protection.release.assert_not_called()
        self.assertFalse(api._release_pending)

    def test_orphan_blocks_replacement_until_exit_then_can_be_reaped(self):
        from core.diagnostics import DiagnosticsService
        process=Mock(pid=7,sentinel=3); process.is_alive.return_value=True
        spawn=Mock(); spawn.Pipe.return_value=(Mock(),Mock()); spawn.Process.return_value=process
        service=DiagnosticsService(lambda context:True,lambda:spawn,lambda handle:False,lambda:0)
        with patch('core.diagnostics.threading.Thread'): service.start('context','protected')
        service._run('context','protected',None,10.5)
        self.assertFalse(service.stop())
        process.is_alive.return_value=False
        self.assertTrue(service.stop())
        process.close.assert_called_once()

if __name__=='__main__': unittest.main()
