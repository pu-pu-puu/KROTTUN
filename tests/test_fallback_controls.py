import json
import re
import shutil
import subprocess
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.proxy_model import ProxyItem
from gui.app_webview import ProxyTunBridgeApi, TunState


class FallbackControlsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for isolated DOM verification')
    def test_production_reserve_dialog_order_empty_errors_and_safe_labels(self):
        html = (Path(__file__).resolve().parents[1] / 'gui/web/index.html').read_text(encoding='utf-8')
        script = re.findall(r'<script>(.*?)</script>', html, re.S)[-1]
        harness = r'''
const assert=require('assert'); const elements=new Map();
function el(){return {children:[],value:'',checked:false,disabled:false,textContent:'',style:{},
 classList:{add(){},remove(){}},appendChild(c){this.children.push(c)},
 replaceChildren(){this.children=[]},setAttribute(){},addEventListener(){},querySelector(){return el()}}}
global.document={getElementById(id){if(!elements.has(id))elements.set(id,el());return elements.get(id)},
createElement:el,addEventListener(){},querySelectorAll(){return []},querySelector:el};
global.window={addEventListener(){}};global.setInterval=()=>0;
'''
        checks = r'''
(async()=>{
selectedProxy={id:'b',tag:'Primary'};isConnected=true;
const proxies=[{id:'a',tag:'<img src=x onerror=boom>'},{id:'b',tag:'Primary'},{id:'c',tag:'Third'}];
window.pywebview={api:{get_fallbacks:async()=>({success:true,proxies,fallback_proxy_ids:['c','b','a'],applies_next_connection:true})}};
await openFallbackModal();
assert(document.getElementById('fallbackPrimary').textContent.includes('Primary'));
assert(document.getElementById('fallbackNotice').textContent.includes('следующем подключении'));
let rows=document.getElementById('fallbackRows').children;
assert.equal(rows.length,2);assert(rows[1].children[0].children[1].textContent.includes('<img'));
rows[1].children[1].children[0].onclick();
assert.deepEqual(fallbackDraft,['a','c']);
let sent;window.pywebview.api.set_fallbacks=async(ids)=>{sent=ids;return {success:false}};
await saveFallbacks();assert.deepEqual(sent,['a','c']);assert.deepEqual(fallbackDraft,['a','c']);
rows=document.getElementById('fallbackRows').children;
rows[0].children[0].children[0].checked=false;rows[0].children[0].children[0].onchange();
rows=document.getElementById('fallbackRows').children;
rows[0].children[0].children[0].checked=false;rows[0].children[0].children[0].onchange();
assert.deepEqual(fallbackDraft,[]);assert(document.getElementById('fallbackEmpty').textContent.includes('Без резервов'));
window.pywebview.api.set_fallbacks=async(ids)=>{sent=ids;return {success:true}};
await saveFallbacks();assert.deepEqual(sent,[]);assert.equal(selectedProxy.id,'b');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result = subprocess.run([shutil.which('node'), '-'], input=harness + script + checks,
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)

    def bridge(self):
        api = ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._lock = threading.RLock()
        api._op_lock = threading.Lock()
        api._closing = False
        api._state = TunState.IDLE
        api._ip_gen = 0
        api._error_seq = 0
        api.is_admin = True
        api.proxies = [ProxyItem(name, '192.0.2.' + str(i), 1080)
                       for i, name in enumerate(('a', 'b', 'c'), 1)]
        api.selected_proxy_id = 'b'
        api.settings = {}
        api._sb = Mock(active_proxy=None)
        api._source = Mock()
        api._protection = Mock(cancel=threading.Event(), generation=0, state='unarmed',
                               cache={}, cache_hosts={})
        api._refresh_ip_async = Mock()
        api._save = Mock()
        api._geo_pool = Mock()
        api._window = None
        return api

    def test_settings_legacy_explicit_empty_validation_and_rollback(self):
        api = self.bridge()
        self.assertEqual(api.get_fallbacks()['fallback_proxy_ids'], ['a', 'b', 'c'])
        with patch('gui.app_webview.save_setting') as save:
            self.assertTrue(api.set_fallbacks([])['success'])
            save.assert_called_once_with('fallback_proxy_ids', [])
        api.proxies.append(ProxyItem('d', '192.0.2.4', 80))
        self.assertEqual(api.get_fallbacks()['fallback_proxy_ids'], [])
        with patch('gui.app_webview.save_setting') as save:
            for invalid in (None, 'a', [1], ['missing'], ['a', 'a']):
                self.assertFalse(api.set_fallbacks(invalid)['success'])
            save.assert_not_called()
        with patch('gui.app_webview.save_setting', side_effect=OSError('private detail')):
            result = api.set_fallbacks(['c', 'a'])
        self.assertFalse(result['success'])
        self.assertNotIn('private detail', json.dumps(result))
        self.assertEqual(api.get_fallbacks()['fallback_proxy_ids'], [])
        api.settings['fallback_proxy_ids'] = ['c', 'missing', 'c', 'a', None]
        self.assertEqual(api.get_fallbacks()['fallback_proxy_ids'], ['c', 'a'])
        self.assertEqual(api.selected_proxy_id, 'b')
        self.assertNotIn('password', json.dumps(api.get_fallbacks()))

    def test_manual_start_primary_first_exclusions_and_fresh_copies(self):
        api = self.bridge()
        api.settings['fallback_proxy_ids'] = ['c', 'b']
        received = []

        def connect(candidates):
            received.append(tuple(candidates))
            api._sb.active_proxy = candidates[0]
            return True

        api._protection.connect.side_effect = connect
        with patch('gui.app_webview.threading.Thread') as thread:
            api.toggle_tun()
            args = thread.call_args.kwargs['args']
        original = list(api.proxies)
        api.proxies.clear()  # Store changes after the manual request cannot replace its queue.
        api.settings['fallback_proxy_ids'] = []
        api._do_toggle(*args)
        self.assertEqual([p.id for p in received[0]], ['b', 'c'])
        self.assertIsNot(received[0][0], original[1])
        self.assertIsNot(received[0][1], original[2])
        api.proxies = original
        api._state = TunState.IDLE
        api.settings['fallback_proxy_ids'] = []
        with patch('gui.app_webview.threading.Thread') as thread:
            api.toggle_tun()
            args = thread.call_args.kwargs['args']
        api._do_toggle(*args)
        self.assertEqual([p.id for p in received[1]], ['b'])

    def test_running_edit_and_store_changes_cannot_change_watchdog_queue_or_cycle(self):
        api = self.bridge()
        api.settings['fallback_proxy_ids'] = ['c', 'a']
        api.proxies[2].username = 'original-user'
        api.proxies[2].password = 'test-only-original'
        calls = []

        def connect(candidates):
            calls.append(tuple(candidates))
            # Primary succeeds, then c fails and a succeeds; finally exhaustion.
            active = candidates[0] if len(calls) == 1 else (candidates[-1] if candidates else None)
            api._sb.active_proxy = active
            api._protection.state = 'protected' if active else 'blocked'
            return active is not None

        api._protection.connect.side_effect = connect
        with patch('gui.app_webview.threading.Thread') as thread:
            api.toggle_tun()
            args = thread.call_args.kwargs['args']
        api._do_toggle(*args)
        self.assertTrue(api.edit_proxy('c', '192.0.2.99', 8080, 'http', 'new-user', 'test-only-new')['success'])
        with patch('gui.app_webview.save_setting'):
            self.assertTrue(api.set_fallbacks([])['success'])
        api.delete_proxy('a')
        api.proxies.append(ProxyItem('new', '192.0.2.88', 80))
        api._sb.is_running.return_value = False
        ticks = 0

        def tick(_):
            nonlocal ticks
            ticks += 1
            if ticks == 3:
                api._closing = True

        with patch('gui.app_webview.time.sleep', side_effect=tick):
            api._watchdog_loop()
        self.assertEqual([[p.id for p in batch] for batch in calls], [['b', 'c', 'a'], ['c', 'a'], []])
        reserve = calls[1][0]
        self.assertEqual((reserve.host, reserve.port, reserve.protocol, reserve.username, reserve.password),
                         ('192.0.2.3', 1080, 'socks5', 'original-user', 'test-only-original'))
        self.assertEqual(api.selected_proxy_id, 'b')
        self.assertEqual(api._state, TunState.ERROR)
        self.assertEqual(api._protection.state, 'blocked')
        api._protection.release.assert_not_called()

    def test_hostname_reserve_keeps_resolved_endpoint_after_running_edit_without_dns(self):
        from core.protection_session import ProtectionSession
        api = self.bridge()
        api.settings['fallback_proxy_ids'] = ['c']
        api.proxies[2].host = 'original.example'
        api.proxies[2].username = 'original-user'
        api._sb.bin_dir = None
        session = ProtectionSession(api._sb, Mock())
        session.guard = Mock()
        policy = False

        def arm(*_):
            nonlocal policy
            policy = True

        session.guard.arm.side_effect = arm
        session.guard.status.side_effect = lambda: {'policy_present': policy}
        api._protection = session
        started = []

        def start(proxy, **_):
            started.append(proxy)
            api._sb.active_proxy = proxy
            api._sb.proxy_reachable = True

        api._sb.start.side_effect = start
        with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('192.0.2.33', 0))]) as dns:
            api._do_toggle('start')
        self.assertEqual(dns.call_count, 1)
        self.assertTrue(api.edit_proxy('c', 'new.example', 8080, 'http', 'changed-user')['success'])
        api._sb.is_running.return_value = False
        ticks = 0

        def tick(_):
            nonlocal ticks
            ticks += 1
            if ticks == 2:
                api._closing = True

        with patch('gui.app_webview.time.sleep', side_effect=tick), patch('socket.getaddrinfo') as dns:
            api._watchdog_loop()
        dns.assert_not_called()
        self.assertEqual([(p.id, p.host, p.port, p.username) for p in started],
                         [('b', '192.0.2.2', 1080, None), ('c', '192.0.2.33', 1080, 'original-user')])
        self.assertEqual(session.state, 'protected')


if __name__ == '__main__':
    unittest.main()
