import multiprocessing
import threading
import time
import unittest
from unittest.mock import Mock,patch
from core.singbox_manager import SingBoxManager
from core.protection_session import ProtectionSession
from core.connection_log import ConnectionJournal
from core.proxy_model import ProxyItem


def stall_probe(pipe,targets,deadline,ready):
    time.sleep(30)


def late_probe(pipe,targets,deadline,ready):
    ready.wait();time.sleep(.4)
    pipe.send(True)


class BoundsTests(unittest.TestCase):
    def test_job_failed_configuration_closes_temporary_handle_and_retries(self):
        from core import win_job
        native=Mock();native.CreateJobObjectW.side_effect=[111,222]
        native.SetInformationJobObject.side_effect=[False,True]
        with patch.object(win_job,'_k32',native),patch.object(win_job,'_job',None):
            self.assertFalse(win_job._ensure_job_created())
            self.assertIsNone(win_job._job)
            native.CloseHandle.assert_called_once_with(111)
            self.assertTrue(win_job._ensure_job_created());self.assertEqual(win_job._job,222)

    def test_release_publishes_intent_before_wait_and_queued_start_cannot_rearm(self):
        from gui.app_webview import ProxyTunBridgeApi,TunState
        api=ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock=threading.RLock();api._op_lock=threading.Lock();api._closing=False
        api._state=TunState.RUNNING;api._ip_gen=0;api._protection=Mock(cancel=threading.Event())
        api._refresh_ip_async=Mock();api._get_selected_proxy=Mock();api.settings={}
        api._op_lock.acquire()
        release=threading.Thread(target=api.release_protection);release.start()
        try:
            self.assertTrue(api._protection.cancel.wait(1))
            with api._lock:
                self.assertEqual(api._state,TunState.STOPPING)
                self.assertTrue(api._release_pending)
                generation=api._op_generation
            self.assertTrue(api.release_protection()['busy'])
            self.assertEqual(api._op_generation,generation)
        finally:
            api._op_lock.release();release.join(timeout=1)
        api._do_toggle('start',generation=0)
        api._protection.connect.assert_not_called()

    def test_watchdog_cannot_retry_or_publish_success_over_explicit_release(self):
        from gui.app_webview import ProxyTunBridgeApi,TunState
        for during in ('probe','connect'):
            with self.subTest(during=during):
                api=ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
                api._lock=threading.RLock();api._op_lock=threading.Lock();api._closing=False
                api._state=TunState.RUNNING;api._ip_gen=0;api._refresh_ip_async=Mock()
                api._protection=Mock(generation=1,cancel=threading.Event())
                api._sb=Mock(process=object());api._sb.active_proxy.id='current'
                api._sb.is_running.return_value=during=='probe'
                api._source=Mock();api.proxies=[]
                releases=[]
                def interrupt(*args,**kwargs):
                    thread=threading.Thread(target=api.release_protection);releases.append(thread);thread.start()
                    self.assertTrue(api._protection.cancel.wait(1))
                    return during=='connect'
                api._sb._probe_tunnel.side_effect=interrupt
                api._protection.connect.side_effect=interrupt
                def release():
                    self.assertEqual(api._state,TunState.STOPPING)
                    self.assertTrue(api._release_pending)
                api._protection.release.side_effect=release
                loops=[0]
                def sleep(_):
                    loops[0]+=1
                    if loops[0]>1: api._closing=True
                try:
                    with patch('gui.app_webview.time.sleep',side_effect=sleep),patch('gui.app_webview.time.monotonic',side_effect=[0,40,40]):
                        api._watchdog_loop()
                finally:
                    for thread in releases:thread.join(timeout=1)
                self.assertTrue(releases)
                self.assertTrue(api._protection.cancel.is_set())
                self.assertEqual(api._state,TunState.IDLE)
                if during=='probe':api._protection.connect.assert_not_called()
    def test_termination_exception_retains_handle_blocks_spawn_and_release_until_confirmed(self):
        manager=SingBoxManager.__new__(SingBoxManager)
        core=Mock();core.poll.return_value=None
        child=Mock(pid=123,sentinel=456);child.is_alive.return_value=True
        child.terminate.side_effect=OSError('cannot terminate')
        context=Mock();context.Process.return_value=child;context.Pipe.return_value=(Mock(),Mock())
        with patch('multiprocessing.get_context',return_value=context),patch('core.singbox_manager.bind_to_lifetime',return_value=False):
            with self.assertRaises(OSError): manager._probe_tunnel(core,time.monotonic()+1)
            self.assertIs(manager._probe_orphan,child)
            self.assertFalse(manager._probe_tunnel(core,time.monotonic()+1))
            self.assertEqual(context.Process.call_count,1)
        child.kill.side_effect=OSError('cannot confirm exit')
        with self.assertRaises(OSError): manager._stop_probe()
        self.assertIs(manager._probe_orphan,child)
        child.is_alive.return_value=False
        manager._stop_probe();self.assertIsNone(manager._probe_orphan)

    def test_numeric_candidate_does_not_inherit_old_domain_binding(self):
        session=ProtectionSession(Mock(bin_dir=None),ConnectionJournal())
        session.guard=Mock();session.guard.status.return_value={'policy_present':True}
        session.cache={'one':'203.0.113.1'};session.cache_hosts={'one':'a.example'}
        session._snapshot([ProxyItem('one','203.0.113.2',443)])
        with patch('socket.getaddrinfo') as dns:
            self.assertEqual(session._snapshot([ProxyItem('one','a.example',443)]),[])
        dns.assert_not_called()
    def test_cancel_and_concurrent_cap_confirm_no_child_survives_stop(self):
        manager=SingBoxManager.__new__(SingBoxManager);manager._probe_worker_target=stall_probe
        core=Mock();core.poll.return_value=None
        manager._probe_state()
        results=[]
        before={child.pid for child in multiprocessing.active_children()}
        with patch('core.singbox_manager.bind_to_lifetime',return_value=True):
            worker=threading.Thread(target=lambda:results.append(manager._probe_tunnel(core,time.monotonic()+4)))
            worker.start()
            until=time.monotonic()+1
            while not manager._probe_gate.locked() and time.monotonic()<until: time.sleep(.005)
            self.assertFalse(manager._probe_tunnel(core,time.monotonic()+1))
            manager._stop_probe()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive());self.assertEqual(results,[False])
        self.assertEqual({child.pid for child in multiprocessing.active_children()},before)

    def test_late_success_is_rejected_and_job_failure_never_opens_request_gate(self):
        manager=SingBoxManager.__new__(SingBoxManager);manager._probe_worker_target=late_probe
        core=Mock();core.poll.return_value=None
        with patch('core.singbox_manager.bind_to_lifetime',return_value=True):
            self.assertFalse(manager._probe_tunnel(core,time.monotonic()+.1))
        with patch('core.singbox_manager.bind_to_lifetime',return_value=False):
            self.assertFalse(manager._probe_tunnel(core,time.monotonic()+1))
        self.assertIsNone(manager._probe_orphan)

    def test_legacy_cache_unbound_is_refused_while_armed(self):
        session=ProtectionSession(Mock(bin_dir=None),ConnectionJournal())
        session.guard=Mock();session.guard.status.return_value={'policy_present':True}
        session.cache={'one':'203.0.113.8'}
        with patch('socket.getaddrinfo') as dns:
            self.assertEqual(session._snapshot([ProxyItem('one','a.example',443)]),[])
        dns.assert_not_called();self.assertEqual(session.cache['one'],'203.0.113.8')

    def test_pending_ip_result_after_release_cannot_republish(self):
        from gui.app_webview import ProxyTunBridgeApi,TunState
        api=ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock=threading.RLock();api._op_lock=threading.Lock();api._closing=False;api._ip_gen=0
        api._state=TunState.RUNNING;api.connected_since=123
        api._protection=Mock(state='protected',generation=1,cancel=threading.Event())
        api._sb=Mock(proxy_reachable=True,process=object());api._sb.is_running.return_value=True
        workers=[]
        def query(**kwargs):
            self.assertTrue(api.release_protection()['success'])
            return {'ip':'203.0.113.99','status':'ready'}
        with patch('gui.app_webview.threading.Timer'),patch('gui.app_webview.threading.Thread',side_effect=lambda **kw:workers.append(kw['target']) or Mock()),patch('gui.app_webview.get_current_system_ip',side_effect=query):
            api._refresh_ip_async();workers[0]()
        self.assertEqual(api.current_system_ip['status'],'unavailable');self.assertIsNone(api.connected_since)

    def test_child_already_in_exact_job_is_not_assigned_again(self):
        import ctypes as C
        from ctypes import wintypes
        from core import win_job
        native=Mock()
        def membership(handle,job,result):
            C.cast(result,C.POINTER(wintypes.BOOL)).contents.value=True
            return True
        native.IsProcessInJob.side_effect=membership
        with patch.object(win_job,'_k32',native),patch.object(win_job,'_ensure_job_created',return_value=True),patch.object(win_job,'_job',123):
            self.assertTrue(win_job.bind_to_lifetime(Mock(_handle=456)))
        native.AssignProcessToJobObject.assert_not_called()
    def test_stalled_isolated_probe_is_terminated_and_never_accumulates(self):
        manager=SingBoxManager.__new__(SingBoxManager)
        manager._probe_worker_target=stall_probe
        core=Mock();core.poll.return_value=None
        before={child.pid for child in multiprocessing.active_children()}
        started=time.monotonic()
        with patch('core.singbox_manager.bind_to_lifetime',return_value=True):
            self.assertFalse(manager._probe_tunnel(core,time.monotonic()+.15))
        self.assertLess(time.monotonic()-started,1.5)
        self.assertEqual({child.pid for child in multiprocessing.active_children()},before)

    def test_unarmed_dns_refresh_and_changed_host_never_reuses_old_cache(self):
        manager=Mock(bin_dir=None)
        session=ProtectionSession(manager,ConnectionJournal())
        session.guard=Mock();session.guard.status.return_value={'policy_present':False}
        proxy=ProxyItem('one','a.example',443)
        with patch('socket.getaddrinfo',side_effect=[[(None,None,None,None,('203.0.113.1',0))],[(None,None,None,None,('203.0.113.2',0))]]) as dns:
            self.assertEqual(session._snapshot([proxy])[0].host,'203.0.113.1')
            self.assertEqual(session._snapshot([proxy])[0].host,'203.0.113.2')
            self.assertEqual(dns.call_count,2)
        session.guard.status.return_value={'policy_present':True}
        with patch('socket.getaddrinfo') as dns:
            self.assertEqual(session._snapshot([proxy])[0].host,'203.0.113.2')
            self.assertEqual(session._snapshot([ProxyItem('one','b.example',443)]),[])
            dns.assert_not_called()

    def test_release_clears_ip_and_invalidates_pending_refresh(self):
        from gui.app_webview import ProxyTunBridgeApi
        api=ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock=threading.RLock();api._op_lock=threading.Lock()
        api._protection=Mock();api._ip_gen=9;api.connected_since=123
        api.current_system_ip={'ip':'203.0.113.9','status':'ready'}
        self.assertTrue(api.release_protection()['success'])
        self.assertGreater(api._ip_gen,9)
        self.assertIsNone(api.connected_since)
        self.assertEqual(api.current_system_ip['status'],'unavailable')
