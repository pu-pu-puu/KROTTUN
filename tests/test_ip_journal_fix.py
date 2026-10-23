import json
import threading
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch, MagicMock
from core.connection_log import ConnectionJournal, ConnectionSource


class IpRefreshTests(unittest.TestCase):
    def test_readonly_system_proxy_warning_reads_enable_flag_only(self):
        api=self.bridge()
        registry=MagicMock()
        registry.QueryValueEx.return_value=(1,4)
        with patch.dict(sys.modules,{'winreg':registry}):
            warning=api._network_warning()
        self.assertIn('может мешать',warning)
        registry.QueryValueEx.assert_called_once()
        self.assertEqual(registry.QueryValueEx.call_args.args[1],'ProxyEnable')
        registry.SetValueEx.assert_not_called()

    def test_ui_flow_checks_real_refresh_result_and_observed_tls_hostname_privately(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/host-validation'))
        import proxy_failover as harness
        api=Mock()
        api.current_system_ip={'ip':'203.0.113.8','status':'ready'}
        api._network_warning.return_value='warning'
        api._journal.read.return_value={'source':'snapshot','rows':[{'kind':'connection','destination':'example.com'}]}
        events=[]
        with patch.object(harness.socket,'create_connection',return_value=MagicMock()),patch('ssl.create_default_context') as tls:
            tls.return_value.wrap_socket.return_value=MagicMock()
            harness.validate_ui_flow(api,'203.0.113.1',lambda phase,value:events.append((phase,value)))
        api._refresh_ip_async.assert_called_once()
        self.assertIn(('ui-ip-differs-baseline',True),events)
        self.assertIn(('ui-tls-domain-observed',True),events)
        self.assertNotIn('203.0.113',str(events))
        tls.return_value.wrap_socket.assert_called_once()
        self.assertEqual(tls.return_value.wrap_socket.call_args.kwargs['server_hostname'],'example.com')

    def test_wall_deadline_stalled_query_bounds_workers_and_rejects_late_result(self):
        api=self.bridge(); workers=[]; deadlines=[]
        def timer(seconds,callback):
            deadlines.append(callback)
            return Mock()
        with patch('gui.app_webview.threading.Thread',side_effect=lambda **kw:workers.append(kw['target']) or Mock()),patch('gui.app_webview.threading.Timer',side_effect=timer):
            api._refresh_ip_async()
            def delayed(**kwargs):
                deadlines[0]()
                self.assertEqual(api.current_system_ip['status'],'unavailable')
                for _ in range(10): api._refresh_ip_async()
                self.assertEqual(len(workers),1)
                return {'ip':'203.0.113.88','status':'ready'}
            with patch('gui.app_webview.get_current_system_ip',side_effect=delayed): workers[0]()
        self.assertEqual(api.current_system_ip['status'],'unavailable')
        self.assertNotEqual(api.current_system_ip.get('ip'),'203.0.113.88')

    def bridge(self):
        from gui.app_webview import ProxyTunBridgeApi, TunState
        api=ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock=threading.RLock(); api._closing=False; api._ip_gen=0
        api._state=TunState.RUNNING
        api._protection=Mock(state='protected',generation=1,cancel=threading.Event())
        api._sb=Mock(proxy_reachable=True,process=object())
        api._sb.is_running.return_value=True
        api.current_system_ip={}
        return api

    def run_refresh(self,api,request):
        workers=[]
        with patch('gui.app_webview.threading.Timer'),patch('gui.app_webview.threading.Thread',side_effect=lambda **kw:workers.append(kw['target']) or Mock()),patch('gui.app_webview.get_current_system_ip',side_effect=request) as query:
            api._refresh_ip_async()
            for worker in workers: worker()
        return query

    def test_protected_tun_refresh_publishes_and_blocked_never_queries(self):
        api=self.bridge()
        self.assertEqual(self.run_refresh(api,lambda **kw:{'ip':'203.0.113.5','status':'ready'}).call_count,1)
        self.assertEqual(api.current_system_ip['status'],'ready')
        api._protection.state='blocked'
        self.assertFalse(self.run_refresh(api,lambda **kw:None).called)
        self.assertEqual(api.current_system_ip['status'],'blocked')

    def test_stale_delayed_generation_process_cancel_or_close_cannot_publish(self):
        for change in ('generation','process','cancel','close'):
            api=self.bridge()
            def query(**kwargs):
                if change=='generation': api._protection.generation+=1
                if change=='process': api._sb.process=object()
                if change=='cancel': api._protection.cancel.set()
                if change=='close': api._closing=True
                return {'ip':'203.0.113.9','status':'ready'}
            self.run_refresh(api,query)
            self.assertNotEqual(api.current_system_ip.get('status'),'ready')

    def test_single_request_ignores_environment_and_windows_proxies(self):
        from core.ip_service import get_current_system_ip
        session=MagicMock(); response=session.get.return_value.__enter__.return_value
        response.status_code=200; response.json.return_value={'ip':'203.0.113.5'}
        with patch('core.ip_service.requests.Session') as factory:
            factory.return_value.__enter__.return_value=session
            self.assertEqual(get_current_system_ip()['status'],'ready')
        self.assertFalse(session.trust_env)
        self.assertEqual(session.get.call_count,1)
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])

    def test_failure_has_final_status_and_coalesces_duplicate_requests(self):
        from core.ip_service import get_current_system_ip
        with patch('core.ip_service.requests.Session',side_effect=OSError()):
            self.assertEqual(get_current_system_ip()['status'],'unavailable')
        api=self.bridge(); workers=[]
        with patch('gui.app_webview.threading.Timer'),patch('gui.app_webview.threading.Thread',side_effect=lambda **kw:workers.append(kw['target']) or Mock()):
            api._refresh_ip_async(); api._refresh_ip_async()
        self.assertEqual(len(workers),1)


class JournalLateHostTests(unittest.TestCase):
    def test_late_host_updates_same_connection_privately_and_resets_session(self):
        journal=ConnectionJournal(); source=ConnectionSource(journal)
        manager=Mock(controller_port=1234,controller_secret='secret')
        manager.active_proxy=None
        row={'id':'raw-private-id','metadata':{'destinationIP':'203.0.113.7','destinationPort':443}}
        def poll(session):
            response=MagicMock()
            response.__enter__.return_value.read.return_value=json.dumps({'connections':[row]}).encode()
            opener=Mock(); opener.open.return_value=response
            with patch('urllib.request.build_opener',return_value=opener): source.poll(manager,session)
        poll(1); first=journal.read()['rows'][0]
        row['metadata']['host']='https://user:password@example.com/private?token=secret'
        poll(1); rows=journal.read()['rows']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['destination'],'example.com')
        self.assertEqual(rows[0]['address'],'203.0.113.7')
        self.assertEqual(rows[0]['connection_key'],first['connection_key'])
        self.assertNotIn('password',str(rows)); self.assertNotIn('raw-private-id',str(rows))
        poll(2)
        self.assertEqual(len(journal.read()['rows']),2)
        self.assertEqual(len(source._seen),1)

