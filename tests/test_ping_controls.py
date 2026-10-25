import threading
import unittest
from unittest.mock import Mock, patch
from core.proxy_model import ProxyItem
from gui.app_webview import ProxyTunBridgeApi, TunState

class PingControlsTests(unittest.TestCase):
    def bridge(self, protected=True):
        a=ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        a._lock=threading.RLock(); a._op_lock=threading.Lock(); a._closing=False; a._ip_gen=1
        a._state=TunState.RUNNING if protected else TunState.IDLE
        a.proxies=[ProxyItem('one','proxy.invalid',1080,password='secret')]; a.selected_proxy_id='one'
        a._protection=Mock(state='protected' if protected else 'unarmed',generation=1,cancel=threading.Event(),cache={'one':'192.0.2.1'},cache_hosts={'one':'proxy.invalid'})
        a._sb=Mock(process=object() if protected else None,proxy_reachable=protected)
        a._sb.active_proxy=None
        a._sb.is_running.return_value=protected
        a._save=Mock()
        return a

    def test_healthy_protected_ping_uses_numeric_snapshot_and_mode(self):
        a=self.bridge()
        with patch('gui.app_webview.PingService', create=True) as service:
            service.return_value.run.return_value={'success':True,'mode':'tun','results':[{'id':'one','latency':15,'status':'alive'}]}
            result=a.ping_proxy('one')
        self.assertTrue(result['success']); self.assertEqual(result['mode'],'tun')
        self.assertEqual(a.proxies[0].latency_ms,15)
        self.assertEqual(service.return_value.run.call_args.args[1],[{'id':'one','host':'192.0.2.1','port':1080,'protocol':'socks5','active':False}])

    def test_blocked_unknown_transition_do_not_start(self):
        for state in ['blocked','unknown','connecting','switching']:
            a=self.bridge();a._protection.state=state
            self.assertFalse(a.ping_all()['success'])

    def test_edited_identity_does_not_receive_old_result(self):
        a=self.bridge(); replacement=ProxyItem('one','new.invalid',8080)
        def run(*args):
            a.proxies=[replacement]
            return {'success':True,'mode':'tun','results':[{'id':'one','latency':15,'status':'alive'}]}
        with patch('gui.app_webview.PingService', create=True) as service:
            service.return_value.run.side_effect=run
            a.ping_all()
        self.assertIsNone(replacement.latency_ms)

    def test_release_refuses_unconfirmed_ping_exit(self):
        a=self.bridge();a._pings=Mock();a._pings.stop.return_value=False
        result=a.release_protection()
        self.assertFalse(result['success']); a._protection.release.assert_not_called()

    def test_protected_connect_requires_fragmented_protocol_response(self):
        from core.ping_service import perform_pings
        from unittest.mock import MagicMock
        target={'id':'one','host':'192.0.2.1','port':1080,'protocol':'socks5'}
        for chunks,expected in [([b'\x05',b'\x02'],'alive'),([b'\x05',b'\xff'],'alive'),([TimeoutError()],'timeout')]:
            sock=MagicMock();sock.__enter__.return_value=sock;sock.recv.side_effect=chunks
            emitted=[]
            perform_pings([target],10,emitted.append,lambda *a,**k:sock,lambda:0,mode='tun')
            self.assertEqual(emitted[0][2],expected)
    def test_measurement_mode_survives_roundtrip_and_safe_bridge(self):
        a=self.bridge();p=a.proxies[0]
        p.latency_mode='tun'
        restored=ProxyItem.from_dict(p.to_dict())
        self.assertEqual(restored.latency_mode,'tun')
        self.assertEqual(a._proxy_to_dict(restored)['latency_mode'],'tun')
        self.assertEqual(ProxyItem.from_dict({'id':'old','host':'192.0.2.1','port':80}).latency_mode,'tcp')
    def test_gate_singleflight_detached_results_and_cleanup(self):
        from core.ping_service import PingService
        events=[];process=Mock(pid=7,sentinel=3);process.is_alive.return_value=False
        process.start.side_effect=lambda:events.append('start')
        gate=Mock();gate.set.side_effect=lambda:events.append('gate')
        receiver=Mock();receiver.poll.return_value=True;receiver.recv.return_value=('one',19,'alive')
        spawn=Mock();spawn.Pipe.return_value=(receiver,Mock());spawn.Process.return_value=process;spawn.Event.return_value=gate
        service=PingService(lambda c:True,lambda:spawn,lambda h:events.append('bind') or True,lambda:0)
        service._busy=True;self.assertTrue(service.run(None,[],'tun')['busy']);service._busy=False
        result=service.run(None,[{'id':'one','host':'192.0.2.1','port':1080,'protocol':'http'}],'tun')
        self.assertEqual(events,['start','bind','gate']);self.assertEqual(result['results'][0]['latency'],19)
        process.close.assert_called_once();self.assertTrue(service.stop())

    def test_unbound_orphan_retained_until_confirmed_exit(self):
        from core.ping_service import PingService
        process=Mock(pid=7,sentinel=3);process.is_alive.return_value=True
        spawn=Mock();spawn.Pipe.return_value=(Mock(),Mock());spawn.Process.return_value=process
        service=PingService(lambda c:True,lambda:spawn,lambda h:False,lambda:0)
        self.assertFalse(service.run(None,[{'id':'one'}],'tun')['success'])
        spawn.Event.return_value.set.assert_not_called()
        process.terminate.assert_called_once();process.kill.assert_called_once();process.close.assert_not_called()
        self.assertTrue(service.run(None,[],'tun')['busy']);self.assertFalse(service.stop())
        process.is_alive.return_value=False
        self.assertTrue(service.stop());process.close.assert_called_once()

    def test_worker_gate_and_context_cancellation_prevent_network(self):
        from core.ping_service import ping_worker, PingService
        gate=Mock();gate.wait.return_value=False
        with patch('core.ping_service.perform_pings') as perform:
            ping_worker(Mock(),[],100,gate,'tun')
        perform.assert_not_called()
        factory=Mock();service=PingService(lambda c:False,factory)
        self.assertFalse(service.run(None,[],'tun')['success']);factory.assert_not_called()

    def test_bridge_context_invalidates_each_runtime_change(self):
        for change in ['generation','process','ip','stop','cancel','close','release','select']:
            a=self.bridge();context,_=a._ping_context();self.assertTrue(a._ping_valid(context))
            if change=='generation':a._protection.generation+=1
            elif change=='process':a._sb.process=object()
            elif change=='ip':a._ip_gen+=1
            elif change=='stop':a._state=TunState.STOPPING
            elif change=='cancel':a._protection.cancel.set()
            elif change=='close':a._closing=True
            elif change=='release':a._release_pending=True
            else:a.selected_proxy_id='other'
            self.assertFalse(a._ping_valid(context),change)

    def test_http_protocol_response_and_direct_tcp_semantics(self):
        from core.ping_service import perform_pings
        from unittest.mock import MagicMock
        target={'id':'one','host':'192.0.2.1','port':80,'protocol':'http'}
        for mode,chunks,expected in [('tun',[b'HTTP/1.1 407 ',b'Auth required\r\n'],'alive'),('tun',[b'not http\r\n'],'timeout'),('tun',[TimeoutError()],'timeout'),('direct',[],'alive')]:
            sock=MagicMock();sock.__enter__.return_value=sock;sock.recv.side_effect=chunks
            emitted=[];perform_pings([target],10,emitted.append,lambda *a,**k:sock,lambda:0,mode=mode)
            self.assertEqual(emitted[0][2],expected)
            if mode=='direct':sock.recv.assert_not_called()
    def test_single_edited_result_is_rejected_before_ui_publish(self):
        a=self.bridge()
        def run(*args):
            a.proxies=[ProxyItem('one','replacement.invalid',8080)]
            return {'success':True,'mode':'tun','results':[{'id':'one','latency':1,'status':'alive'}]}
        with patch('gui.app_webview.PingService',create=True) as service:
            service.return_value.run.side_effect=run
            self.assertFalse(a.ping_proxy('one')['success'])
    def test_deadline_kills_worker_and_marks_unchecked_honestly(self):
        from core.ping_service import PingService
        process=Mock(pid=7,sentinel=3);process.is_alive.side_effect=[True,True,False]
        spawn=Mock();spawn.Pipe.return_value=(Mock(),Mock());spawn.Process.return_value=process
        clock=Mock(side_effect=[0,9])
        service=PingService(lambda c:True,lambda:spawn,lambda h:True,clock)
        result=service.run(None,[{'id':'one'}],'tun')
        self.assertTrue(result['success']);self.assertEqual(result['results'][0]['status'],'notchecked')
        process.terminate.assert_called_once();process.kill.assert_called_once();process.close.assert_called_once()

    def test_bridge_does_not_hold_lock_during_service_wait(self):
        a=self.bridge()
        def run(*args):
            locked=[]
            def acquire():
                with a._lock:locked.append(True)
            worker=threading.Thread(target=acquire);worker.start();worker.join(.2)
            self.assertEqual(locked,[True])
            return {'success':True,'mode':'tun','results':[{'id':'one','latency':None,'status':'timeout'}]}
        with patch('gui.app_webview.PingService',create=True) as service:
            service.return_value.run.side_effect=run
            self.assertTrue(a.ping_all()['success'])
        self.assertIsNone(a.proxies[0].latency_ms);self.assertEqual(a.proxies[0].last_status,'dead')
    def test_active_http_uses_https_never_self_socket(self):
        from core.ping_service import perform_pings
        from unittest.mock import MagicMock
        target={'id':'one','host':'192.0.2.1','port':8080,'protocol':'http','active':True}
        session=MagicMock();session.__enter__.return_value=session
        response=MagicMock();response.__enter__.return_value=response;response.status_code=204
        response.iter_content.return_value=iter([]);session.get.return_value=response
        connect=Mock(side_effect=AssertionError('must not self-connect'));rows=[]
        perform_pings([target],10,rows.append,connect,lambda:0,mode='tun',session_factory=lambda:session)
        connect.assert_not_called();self.assertEqual(rows,[('one',0,'alive')])
        self.assertFalse(session.trust_env)
        call=session.get.call_args
        self.assertEqual(call.args[0],'https://cp.cloudflare.com/generate_204')
        self.assertFalse(call.kwargs['allow_redirects']);self.assertTrue(call.kwargs['stream'])
        self.assertGreater(call.kwargs['timeout'],0);self.assertLessEqual(call.kwargs['timeout'],10)

    def test_active_https_failure_is_unavailable(self):
        from core.ping_service import perform_pings
        from unittest.mock import MagicMock
        for status in [200,302,500,None]:
            session=MagicMock();session.__enter__.return_value=session
            response=MagicMock();response.__enter__.return_value=response;response.status_code=status
            session.get.return_value=response
            if status is None:session.get.side_effect=TimeoutError()
            rows=[];connect=Mock()
            perform_pings([{'id':'one','active':True}],10,rows.append,connect,lambda:0,mode='tun',session_factory=lambda:session)
            self.assertEqual(rows,[('one',None,'unavailable')]);connect.assert_not_called();self.assertEqual(session.get.call_count,2)

    def test_actual_active_not_selected_controls_measurement_mode(self):
        a=self.bridge();reserve=ProxyItem('reserve','reserve.invalid',80,'http')
        a.proxies.append(reserve);a.selected_proxy_id='reserve';a._sb.active_proxy=a.proxies[0]
        with patch('gui.app_webview.PingService',create=True) as service:
            service.return_value.run.return_value={'success':True,'mode':'tun','results':[{'id':'one','latency':5,'status':'alive'},{'id':'reserve','latency':None,'status':'timeout'}]}
            result=a.ping_all()
        targets=service.return_value.run.call_args.args[1]
        self.assertTrue(targets[0]['active']);self.assertFalse(targets[1]['active'])
        self.assertEqual(a.proxies[0].latency_mode,'tun_https');self.assertEqual(reserve.latency_mode,'tun')
        self.assertEqual(result['results'][0]['mode'],'tun_https')
        self.assertTrue(a._sb.proxy_reachable)
    def test_active_unavailable_does_not_mark_dead_or_change_health(self):
        a=self.bridge();a._sb.active_proxy=a.proxies[0]
        with patch('gui.app_webview.PingService',create=True) as service:
            service.return_value.run.return_value={'success':True,'mode':'tun','results':[{'id':'one','latency':None,'status':'unavailable'}]}
            result=a.ping_proxy('one')
        self.assertEqual(result['mode'],'tun_https');self.assertEqual(result['status'],'unavailable')
        self.assertEqual(a.proxies[0].last_status,'unknown');self.assertEqual(a.proxies[0].latency_mode,'tun_https')
        self.assertTrue(a._sb.proxy_reachable);a._protection.connect.assert_not_called();a._protection.release.assert_not_called()

    def test_active_https_body_limit_and_no_request_after_deadline(self):
        from core.ping_service import perform_pings
        from unittest.mock import MagicMock
        session=MagicMock();session.__enter__.return_value=session
        response=MagicMock();response.__enter__.return_value=response;response.status_code=204
        response.iter_content.side_effect=lambda *args:iter([b'x'*1025]);session.get.return_value=response
        rows=[];perform_pings([{'id':'one','active':True}],10,rows.append,Mock(),lambda:0,mode='tun',session_factory=lambda:session)
        self.assertEqual(rows,[('one',None,'unavailable')])
        session.reset_mock();rows=[]
        perform_pings([{'id':'one','active':True}],0,rows.append,Mock(),lambda:0,mode='tun',session_factory=lambda:session)
        session.get.assert_not_called();self.assertEqual(rows,[])
    def test_active_identity_or_id_change_invalidates_context(self):
        for change in ['replacement','id']:
            a=self.bridge();a._sb.active_proxy=a.proxies[0]
            context,_=a._ping_context();self.assertTrue(a._ping_valid(context))
            if change=='replacement':a._sb.active_proxy=ProxyItem('one','proxy.invalid',1080)
            else:a._sb.active_proxy.id='changed'
            self.assertFalse(a._ping_valid(context))
    def test_active_https_fallback_same_route_reports_successful_attempt(self):
        from core.ping_service import perform_pings
        from unittest.mock import MagicMock
        session=MagicMock();session.__enter__.return_value=session
        response=MagicMock();response.__enter__.return_value=response;response.status_code=204
        response.iter_content.return_value=iter([])
        now=[0];attempts=[]
        def request(url,**kwargs):
            attempts.append(url)
            if len(attempts)==1:
                now[0]=3
                raise TimeoutError()
            now[0]=3.05
            return response
        session.get.side_effect=request
        rows=[];connect=Mock()
        perform_pings([{'id':'one','active':True}],8,rows.append,connect,lambda:now[0],mode='tun',session_factory=lambda:session)
        self.assertEqual(rows,[('one',50,'alive')]);connect.assert_not_called()
        self.assertEqual([c.args[0] for c in session.get.call_args_list],['https://cp.cloudflare.com/generate_204','https://www.gstatic.com/generate_204'])
        for call in session.get.call_args_list:
            self.assertFalse(call.kwargs['allow_redirects']);self.assertTrue(call.kwargs['stream'])
        self.assertFalse(session.trust_env)
