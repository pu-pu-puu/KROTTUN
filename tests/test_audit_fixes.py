import subprocess
import threading
import time
import unittest
import os
from unittest.mock import Mock, MagicMock, patch


class AuditFixTests(unittest.TestCase):
    def test_core_job_failure_stops_before_config_or_readiness(self):
        from core.singbox_manager import SingBoxManager
        from core.proxy_model import ProxyItem
        manager = SingBoxManager.__new__(SingBoxManager)
        manager.process = None; manager.exe_path = 'fake-core'; manager.bin_dir = '.'
        manager.log_path = manager.stderr_path = os.devnull
        manager.is_adapter_present = Mock(return_value=False)
        manager.generate_config = Mock(return_value={})
        manager._verify_or_raise = Mock(); manager._wait_ready = Mock()
        process = Mock()
        def stop():
            manager.process = None
            if getattr(manager, 'err_file', None): manager.err_file.close()
        manager.stop = Mock(side_effect=stop)
        with patch('core.singbox_manager.is_admin', return_value=True), \
                patch('core.singbox_manager.subprocess.Popen', return_value=process), \
                patch('core.singbox_manager.bind_to_lifetime', return_value=False):
            with self.assertRaises(RuntimeError): manager.start(ProxyItem('id', '192.0.2.1', 1080))
        self.assertEqual(manager.stop.call_count, 2)
        process.stdin.write.assert_not_called()
        manager._wait_ready.assert_not_called()
        self.assertIsNone(manager.process)

    def test_job_failure_aborts_before_bridge_construction(self):
        from gui import app_webview as gui
        with patch.object(gui, 'check_single_instance', return_value=True), \
                patch.object(gui, 'bind_self_to_job', return_value=False), \
                patch.object(gui, 'ProxyTunBridgeApi') as bridge, \
                patch.object(gui.webview, 'create_window'), \
                patch.object(gui.webview, 'start'), \
                patch.object(gui, 'get_html_content', return_value=''), \
                patch('logging.critical'), \
                patch('ctypes.windll.user32.MessageBoxW'):
            with self.assertRaises(SystemExit) as error:
                gui.start_app()
        self.assertEqual(error.exception.code, 1)
        bridge.assert_not_called()

    def test_dns_timeout_kills_and_confirms_exit(self):
        from core.singbox_manager import SingBoxManager
        manager = SingBoxManager.__new__(SingBoxManager)
        process = Mock()
        process.wait.side_effect = [subprocess.TimeoutExpired('ipconfig', 2), 0]
        process.poll.side_effect = [None, 0]
        with patch('core.singbox_manager.subprocess.Popen', return_value=process):
            manager.flush_dns()
        process.kill.assert_called_once()
        self.assertTrue(all(c.kwargs.get('timeout', 999) <= 2 for c in process.wait.call_args_list))
        self.assertIsNone(manager._dns_process)

    def test_dns_unconfirmed_exit_retains_ownership_and_blocks_respawn(self):
        from core.singbox_manager import SingBoxManager
        manager = SingBoxManager.__new__(SingBoxManager)
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired('ipconfig', 2)
        with patch('core.singbox_manager.subprocess.Popen', return_value=process) as spawn:
            with self.assertRaises(RuntimeError): manager.flush_dns()
            self.assertIs(manager._dns_process, process)
            with self.assertRaises(RuntimeError): manager.flush_dns()
        self.assertEqual(spawn.call_count, 1)

    def test_ip_body_limit_and_streaming(self):
        from core.ip_service import get_current_system_ip
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        response.status_code = 200
        response.iter_content.return_value = iter([b'x' * 1025])
        with patch('core.ip_service.requests.Session') as factory:
            factory.return_value.__enter__.return_value = session
            self.assertEqual(get_current_system_ip()['status'], 'unavailable')
        self.assertTrue(session.get.call_args.kwargs['stream'])
        response.json.assert_not_called()

    def test_release_refuses_unconfirmed_ip_exit(self):
        from gui.app_webview import ProxyTunBridgeApi
        api = ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock = threading.RLock(); api._op_lock = threading.Lock()
        api._ip_gen = 0; api._protection = Mock(cancel=threading.Event())
        api._ip_service = Mock(); api._ip_service.stop.return_value = False
        self.assertFalse(api.release_protection()['success'])
        api._protection.release.assert_not_called()
        api._ip_service.stop.assert_called_once()

    def test_shutdown_retains_tunnel_until_ip_exit_confirmed(self):
        from gui.app_webview import ProxyTunBridgeApi
        api = ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock = threading.RLock(); api._op_lock = threading.Lock()
        api._protection = Mock(cancel=threading.Event()); api._journal = Mock()
        api._ip_service = Mock(); api._ip_service.stop.return_value = False
        with self.assertRaises(RuntimeError): api.shutdown()
        api._protection.stop.assert_not_called()


if __name__ == '__main__': unittest.main()
