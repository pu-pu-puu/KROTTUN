import json
import threading
import re
import shutil
import subprocess
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from core.proxy_model import ProxyItem
from gui.app_webview import ProxyTunBridgeApi, TunState


class ProxyEditTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for isolated DOM verification')
    def test_modal_keeps_failed_values_redacts_password_and_coalesces_submit(self):
        html = (Path(__file__).resolve().parents[1] / 'gui/web/index.html').read_text(encoding='utf-8')
        script = re.findall(r'<script>(.*?)</script>', html, re.S)[-1]
        harness = r'''
const assert = require('assert');
const elements = new Map();
function element() { return { value:'', checked:false, hidden:false, disabled:false,
  textContent:'', style:{}, classList:{add(){},remove(){}},
  querySelector(){return element();}, setAttribute(){}, appendChild(){}, addEventListener(){} }; }
global.document = { getElementById(id){if(!elements.has(id)) elements.set(id,element()); return elements.get(id);},
  addEventListener(){},querySelectorAll(){return []},querySelector(){return element();},createElement:element };
global.window = {addEventListener(){}};
global.alert = ()=>{};
global.setInterval = ()=>0;
'''
        checks = r'''
(async()=>{
proxyList = [{id:'sample',host:'old.example',port:1080,protocol:'socks5',username:'user',tag:'<Name>'}];
isConnected = true;
openEditModal('sample');
assert.equal(document.getElementById('addTag').value,'<Name>');
assert.equal(document.getElementById('addPass').value,'');
assert(document.getElementById('editNotice').textContent.includes('следующем подключении'));
document.getElementById('addPass').value = '  fixture  ';
let calls = 0, finish;
window.pywebview = {api:{edit_proxy(...args){calls++;assert.equal(args[5],'  fixture  ');return new Promise(r=>finish=r);}}};
const first = submitAddProxy(); await submitAddProxy(); assert.equal(calls,1);
finish({success:false,error:'Не удалось сохранить'}); await first;
assert.equal(document.getElementById('addPass').value,'  fixture  ');
window.pywebview.api.edit_proxy = async()=>{throw Error('raw detail')};
await submitAddProxy();
assert.equal(document.getElementById('addPass').value,'  fixture  ');
closeModals();assert.equal(document.getElementById('addPass').value,'');
openAddModal();assert.equal(document.getElementById('addHost').value,'');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        result = subprocess.run([shutil.which('node'), '-'], input=harness + script + checks, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)

    def bridge(self):
        api = ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock = threading.RLock()
        api._closing = False
        api._state = TunState.RUNNING
        api.proxies = [ProxyItem('sample', 'old.example', 1080, username='user',
                                 password='fixture-password', tag='Original',
                                 country='Old country', city='Old city', latency_ms=42,
                                 last_status='alive')]
        api.selected_proxy_id = 'sample'
        api._sb = Mock(active_proxy=api.proxies[0])
        api._protection = Mock(state='protected', cache={'sample': '192.0.2.1'},
                               cache_hosts={'sample': 'old.example'})
        api._save = Mock()
        api._geo_pool = Mock()
        api._window = None
        return api

    def test_edit_preserves_identity_password_and_running_runtime(self):
        api = self.bridge()
        old = api.proxies[0]
        result = api.edit_proxy('sample', 'new.example', 8080, 'http', 'new-user', '', '<New name>')
        self.assertTrue(result['success'])
        self.assertEqual(api.proxies[0].id, 'sample')
        self.assertEqual(api.proxies[0].password, old.password)
        self.assertIs(api._sb.active_proxy, old)
        self.assertEqual(old.host, 'old.example')
        self.assertEqual(result['selected_proxy']['tag'], '<New name>')
        self.assertNotIn('password', result['selected_proxy'])
        self.assertNotIn(old.password, json.dumps(result))
        api._sb.start.assert_not_called()
        api._protection.connect.assert_not_called()

    def test_invalid_busy_and_storage_failure_are_safe_and_atomic(self):
        invalid = [('bad host', 80, 'http'), ('<script>', 80, 'http'),
                   ('ok.example', True, 'http'), ('ok.example', 1.5, 'http'),
                   ('ok.example', 0, 'http'), ('ok.example', 80, 'auto')]
        for host, port, proto in invalid:
            api = self.bridge(); old = api.proxies[0]
            self.assertFalse(api.edit_proxy('sample', host, port, proto)['success'])
            self.assertIs(api.proxies[0], old)
            api._save.assert_not_called()
        for state, release in [(TunState.STARTING, False), (TunState.STOPPING, False),
                               (TunState.IDLE, True)]:
            api = self.bridge(); api._state = state; api._release_pending = release
            self.assertTrue(api.edit_proxy('sample', 'ok.example', 80, 'http')['busy'])
            api._save.assert_not_called()
        api = self.bridge(); old = api.proxies[0]
        self.assertFalse(api.edit_proxy('missing', 'ok.example', 80, 'http')['success'])
        api._save.side_effect = OSError('fixture-password old.example user')
        result = api.edit_proxy('sample', 'ok.example', 80, 'http')
        self.assertFalse(result['success'])
        self.assertIs(api.proxies[0], old)
        self.assertNotIn('fixture-password', json.dumps(result))
        self.assertEqual(api._protection.cache_hosts, {'sample': 'old.example'})

    def test_password_changes_reset_metadata_and_hostname_cache(self):
        api = self.bridge()
        api._state = TunState.ERROR
        api._protection.state = 'blocked'
        result = api.edit_proxy('sample', 'new.example', 3128, 'http', 'new-user', '  new fixture  ')
        self.assertTrue(result['success'])
        self.assertEqual(api.proxies[0].password, '  new fixture  ')
        self.assertEqual((api.proxies[0].country, api.proxies[0].city, api.proxies[0].country_code), ('', '', ''))
        self.assertIsNone(api.proxies[0].latency_ms)
        self.assertEqual(api.proxies[0].last_status, 'unknown')
        self.assertNotIn('sample', api._protection.cache)
        self.assertNotIn('sample', api._protection.cache_hosts)
        self.assertTrue(api.edit_proxy('sample', 'new.example', 3128, 'http', clear_password=True)['success'])
        self.assertIsNone(api.proxies[0].password)
        api._protection.release.assert_not_called()

    def test_late_single_and_batch_geo_cannot_overwrite_replacement(self):
        for batch in (False, True):
            for change_host in (False, True):
                with self.subTest(batch=batch, change_host=change_host):
                    api = self.bridge(); api._state = TunState.IDLE
                    api._protection.state = 'unarmed'
                    def delayed(*args, **kwargs):
                        self.assertTrue(api.edit_proxy('sample', 'new.example' if change_host else 'old.example',
                                                       1080, 'socks5', tag='Edited')['success'])
                        return 'Stale country', 'US', 'Stale city'
                    with patch('gui.app_webview.resolve_host_geo', side_effect=delayed):
                        if batch:
                            api._resolve_proxies_batch_async(['sample'])
                        else:
                            api._resolve_single_proxy_async('sample')
                    self.assertNotEqual(api.proxies[0].country, 'Stale country')


if __name__ == '__main__':
    unittest.main()
