import threading
import unittest
from unittest.mock import Mock

from core.version import APP_VERSION
from gui.app_webview import ProxyTunBridgeApi


class InfoViewTests(unittest.TestCase):
    def test_state_exposes_authoritative_app_version(self):
        api = ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock = threading.RLock()
        api._state = 'idle'
        api._sb = Mock(active_proxy=None, proxy_reachable=False)
        api._get_selected_proxy = Mock(return_value=None)
        api._last_error = api._storage_error = ''
        api._error_seq = 0
        api.connected_since = None
        api.is_admin = True
        api.current_system_ip = {}
        api._network_warning = Mock(return_value='')
        api.current_upload_mbps = api.current_download_mbps = 0
        api.proxies = []
        api._protection = Mock(state='unarmed')
        api.settings = {}
        self.assertEqual(api.get_state()['app_version'], APP_VERSION)
