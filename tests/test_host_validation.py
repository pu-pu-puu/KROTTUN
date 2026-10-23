import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
from unittest.mock import patch
import ctypes as C
import dataclasses
import sys
from core.kill_switch import WindowsWfpBackend, OWNER
from core.wfp_native import EnumTemplate, GUID, KEYS, P, U32

spec = importlib.util.spec_from_file_location('host_preflight',Path(__file__).resolve().parents[1]/'tools/host-validation/preflight.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/host-validation'))
live_spec = importlib.util.spec_from_file_location('host_live_smoke',Path(__file__).resolve().parents[1]/'tools/host-validation/live_smoke.py')
live = importlib.util.module_from_spec(live_spec)
live_spec.loader.exec_module(live)
stage3_spec = importlib.util.spec_from_file_location('host_proxy_failover',Path(__file__).resolve().parents[1]/'tools/host-validation/proxy_failover.py')
stage3 = importlib.util.module_from_spec(stage3_spec)
stage3_spec.loader.exec_module(stage3)


class HostPreflightTests(unittest.TestCase):
    def backend(self):
        backend = Mock()
        backend.app_id.return_value = b'identity'
        backend.dll.FwpmSubLayerAdd0.return_value = 0
        rows = []
        backend._add.side_effect = rows.append
        backend.read.side_effect = lambda: tuple(rows)
        return backend

    def test_success_always_aborts_without_commit(self):
        backend = self.backend()
        report = module.probe(lambda:backend,'engine',lambda:None)
        self.assertTrue(report['ok'])
        self.assertTrue(report['abort_ok'])
        calls = [call.args[0] for call in backend._call.call_args_list]
        self.assertEqual(calls,['FwpmTransactionBegin0','FwpmTransactionAbort0','FwpmEngineClose0'])
        backend.replace.assert_not_called()

    def test_add_failure_aborts_and_closes(self):
        backend = self.backend()
        backend._add.side_effect = RuntimeError('native 0x80320002 secret')
        report = module.probe(lambda:backend,'engine',lambda:None)
        self.assertFalse(report['ok'])
        self.assertTrue(report['abort_ok'])
        self.assertEqual(report['native_codes'],['0x80320002'])
        self.assertNotIn('secret',str(report))
        self.assertTrue(report['close_ok'])


    def test_nonnull_templates_use_all_six_real_layers_and_keep_flags(self):
        backend = WindowsWfpBackend.__new__(WindowsWfpBackend)
        backend.handle = P(1)
        backend.dll = Mock()
        templates = []
        destroyed = []
        def native_call(name,*args):
            if name == 'FwpmFilterCreateEnumHandle0':
                template = C.cast(args[1],C.POINTER(EnumTemplate)).contents
                templates.append((bytes(template.layer),template.flags,template.action_mask))
                self.assertNotEqual(bytes(template.layer),bytes(GUID()))
            elif name == 'FwpmFilterEnum0':
                C.cast(args[4],C.POINTER(U32)).contents.value = 0
            else:
                self.fail('Unexpected API '+name)
        backend._call = native_call
        backend.dll.FwpmFilterDestroyEnumHandle0.side_effect = lambda *args: destroyed.append(args)
        self.assertEqual(backend._owned(),[])
        expected = {bytes(GUID.of(KEYS[layer+str(family)]))
                    for family in (4,6) for layer in ('packet','connect','accept')}
        self.assertEqual({row[0] for row in templates},expected)
        self.assertEqual(len(templates),6)
        self.assertTrue(all(flags == 0x18 and mask == 0xffffffff for _,flags,mask in templates))
        self.assertEqual(len(destroyed),6)

    def test_existing_policy_rejected_before_begin(self):
        backend = self.backend()
        backend.read.side_effect = lambda: ('existing',)
        report = module.probe(lambda:backend,'engine',lambda:None)
        self.assertFalse(report['ok'])
        self.assertFalse(report['abort_attempted'])
        self.assertEqual([c.args[0] for c in backend._call.call_args_list],['FwpmEngineClose0'])

    def test_abort_failure_still_closes(self):
        backend = self.backend()
        def call(name,*args):
            if name == 'FwpmTransactionAbort0':
                raise RuntimeError('failed')
        backend._call.side_effect = call
        report = module.probe(lambda:backend,'engine',lambda:None)
        self.assertFalse(report['ok'])
        self.assertTrue(report['close_ok'])

    def test_running_gui_refuses_open(self):
        factory = Mock()
        report = module.probe(factory,'engine',Mock(side_effect=RuntimeError('running')))
        factory.assert_not_called()
        self.assertFalse(report['ok'])

    def test_begin_failure_closes_without_abort(self):
        backend = self.backend()
        backend._call.side_effect = [RuntimeError('begin failed'),None]
        report = module.probe(lambda:backend,'engine',lambda:None)
        self.assertFalse(report['abort_attempted'])
        self.assertTrue(report['close_ok'])


class LiveSmokeTests(unittest.TestCase):
    def parent_identity(self):
        return {'pid':123,'created':1.25,'executable':sys.executable,'nonce':'test-nonce'}

    def parent_process(self):
        process = Mock()
        process.create_time.return_value = 1.25
        process.exe.return_value = sys.executable
        process.cmdline.return_value = [sys.executable,live.__file__,'--run-nonce','test-nonce']
        return process

    def test_expiry_kills_paused_parent_before_cleanup_so_it_cannot_resume_arm(self):
        identity = self.parent_identity()
        parent = self.parent_process()
        state = {'alive':True,'armed':False}
        events = []
        def kill():
            state['alive'] = False
            events.append('kill-paused-parent')
        parent.kill.side_effect = kill
        parent.wait.side_effect = lambda **kwargs: events.append('exit-confirmed')
        def stop(identity):
            return live.stop_exact_parent(identity,process_factory=lambda pid:parent)
        def recover(backend):
            self.assertFalse(state['alive'])
            events.append('cleanup')
        self.assertTrue(live.expire_and_cleanup(identity,Mock(),stop=stop,recover=recover))
        # Scheduler resumes the pre-arm continuation only if its process exists.
        if state['alive']:
            state['armed'] = True
        self.assertFalse(state['armed'])
        self.assertEqual(events,['kill-paused-parent','exit-confirmed','cleanup'])

    def test_unconfirmed_parent_exit_forbids_cleanup_and_success(self):
        recover = Mock()
        self.assertFalse(live.expire_and_cleanup(self.parent_identity(),Mock(),stop=lambda identity:False,recover=recover))
        recover.assert_not_called()

    def test_nonce_mismatch_never_kills_or_claims_parent_exit(self):
        parent = self.parent_process()
        parent.cmdline.return_value = [sys.executable,live.__file__,'--run-nonce','someone-else']
        self.assertFalse(live.stop_exact_parent(self.parent_identity(),process_factory=lambda pid:parent))
        parent.kill.assert_not_called()

    def test_pid_reuse_confirms_original_exit_without_killing_replacement(self):
        parent = self.parent_process()
        parent.create_time.return_value = 9.5
        self.assertTrue(live.stop_exact_parent(self.parent_identity(),process_factory=lambda pid:parent))
        parent.kill.assert_not_called()

    def test_parent_kill_timeout_forbids_success(self):
        import psutil
        parent = self.parent_process()
        parent.wait.side_effect = psutil.TimeoutExpired(2)
        self.assertFalse(live.stop_exact_parent(self.parent_identity(),process_factory=lambda pid:parent))

    def test_live_arm_requires_ready_watchdog(self):
        backend, guard = Mock(), Mock()
        backend.read.return_value = ()
        guard.require_ready.side_effect = RuntimeError('not ready')
        with patch.object(live,'rehearse'), patch.object(live,'KillSwitch') as switch:
            result = live.run(backend,guard,connect=Mock(return_value='connected'),stopped=lambda:None)
        switch.assert_not_called()
        guard.finish.assert_called_once()
        self.assertFalse(result['ok'])

    def test_existing_policy_refuses_before_watchdog_and_arm(self):
        backend, guard = Mock(), Mock()
        backend.read.return_value = ('existing',)
        with patch.object(live,'rehearse') as rehearsal, patch.object(live,'KillSwitch') as switch:
            result = live.run(backend,guard,stopped=lambda:None)
        rehearsal.assert_not_called()
        switch.assert_not_called()
        guard.start.assert_not_called()
        self.assertFalse(result['ok'])

    def test_arm_failure_always_cleans_up_and_signals_watchdog(self):
        backend, guard = Mock(), Mock()
        backend.read.return_value = ()
        with patch.object(live,'rehearse'), patch.object(live,'cleanup') as clean, patch.object(live,'KillSwitch') as switch:
            switch.return_value.arm.side_effect = RuntimeError('readback failure after commit')
            result = live.run(backend,guard,connect=Mock(return_value='connected'),stopped=lambda:None)
        clean.assert_called_once_with(backend)
        guard.finish.assert_called_once()
        self.assertTrue(result['cleanup_ok'])
        self.assertFalse(result['ok'])

    def test_tcp_timeout_is_inconclusive_and_restores(self):
        backend, guard = Mock(), Mock()
        backend.read.return_value = ()
        guard.success.return_value = True
        connect = Mock(side_effect=['connected','unavailable','timeout-inconclusive','connected'])
        with patch.object(live,'rehearse'), patch.object(live,'cleanup') as clean, patch.object(live,'KillSwitch'):
            result = live.run(backend,guard,connect=connect,stopped=lambda:None)
        self.assertEqual(result['classification'],'inconclusive')
        self.assertFalse(result['ok'])
        self.assertEqual(result['restored_tcp'],'connected')
        clean.assert_called_once()

    def test_cleanup_only_uses_smoke_keys_and_ignores_filter_not_found(self):
        backend = Mock()
        backend.read.return_value = ()
        backend.dll.FwpmFilterDeleteByKey0.return_value = live.FILTER_NOT_FOUND
        live.cleanup(backend)
        actual = {bytes(C.cast(call.args[1],C.POINTER(GUID)).contents)
                  for call in backend.dll.FwpmFilterDeleteByKey0.call_args_list}
        expected = {bytes(GUID.of(live.uuid.uuid5(OWNER,rule.name))) for rule in live.RULES}
        self.assertEqual(actual,expected)
        self.assertEqual(len(actual),14)
        self.assertEqual([c.args[0] for c in backend._call.call_args_list],['FwpmTransactionBegin0','FwpmTransactionCommit0'])


class ProxyFailoverTests(unittest.TestCase):
    def test_timeout_can_continue_functional_checks_but_never_overall_pass(self):
        result={'functional_ok':False,'cleanup_ok':True,'no_tun':True}
        self.assertTrue(stage3.accept_outage_observation(result,'EE','timeout-inconclusive'))
        self.assertTrue(stage3.accept_outage_observation(result,'US','network-failure'))
        # Represents real failover/exhaustion completing, not a negative-test pass.
        result['functional_ok']=True
        stage3.finalize_verdict(result,restored=True,watchdog_ok=True)
        self.assertTrue(result['functional_ok'])
        self.assertFalse(result['ok'])
        self.assertEqual(result['classification'],'inconclusive')

    def test_actual_response_and_invalid_payload_must_abort_not_continue(self):
        for observation in ('http-response','successful-response','invalid-inconclusive'):
            with self.subTest(observation=observation):
                result={'functional_ok':True,'cleanup_ok':True,'no_tun':True}
                self.assertFalse(stage3.accept_outage_observation(result,'EE',observation))
                stage3.finalize_verdict(result,restored=True,watchdog_ok=True)
                self.assertFalse(result['functional_ok'])
                self.assertFalse(result['ok'])

    def test_observation_classifier_distinguishes_timeout_http_and_network_failure(self):
        import requests
        cases=((requests.ReadTimeout(),'timeout-inconclusive'),(requests.HTTPError(),'http-response'),
               (OSError(),'network-failure'),(ValueError(),'invalid-inconclusive'))
        for exception,expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(stage3.observe_exit_check(check=Mock(side_effect=exception)),expected)
        self.assertEqual(stage3.observe_exit_check(check=lambda:'private-IP'),'successful-response')

    def test_proxy_outage_withdraws_endpoints_for_exact_current_luid_without_core_kill(self):
        bridge=Mock()
        manager=bridge._sb
        manager.interface_name='sing-tun-private-current'
        manager.process.poll.return_value=None
        guard=bridge._protection._guard.return_value
        guard.backend.app_id.return_value=b'verified'
        guard.status.return_value={'armed':True}
        lookup=Mock(return_value=123456)
        stage3.inject_proxy_outage(bridge,lookup=lookup)
        lookup.assert_called_once_with('sing-tun-private-current')
        guard.arm.assert_called_once_with((),b'verified',123456)
        manager.process.kill.assert_not_called()
        manager.process.terminate.assert_not_called()
        manager.stop.assert_not_called()
        manager.start.assert_not_called()
        manager._probe_tunnel.assert_not_called()

    def test_proxy_outage_rejects_unverified_luid_before_arm(self):
        bridge=Mock()
        bridge._sb.process.poll.return_value=None
        guard=bridge._protection._guard.return_value
        for invalid in (None,False,0,-1,'prefix'):
            with self.subTest(invalid=invalid),self.assertRaises(RuntimeError):
                stage3.inject_proxy_outage(bridge,lookup=lambda alias:invalid)
        guard.arm.assert_not_called()

    def test_fault_exit_check_requires_completed_network_failure(self):
        self.assertFalse(stage3.blocked_exit_check(check=lambda:'never-export-this-IP'))
        self.assertTrue(stage3.blocked_exit_check(check=Mock(side_effect=OSError('secret error'))))
        self.assertFalse(stage3.blocked_exit_check(check=Mock(side_effect=ValueError('private payload'))))
        stalled=stage3.threading.Event()
        try:
            self.assertFalse(stage3.blocked_exit_check(check=lambda:stalled.wait(1),seconds=.01))
        finally:
            stalled.set()

    def test_fault_exit_timeouts_and_http_errors_are_inconclusive(self):
        import requests
        for exception in (requests.Timeout,requests.ReadTimeout,requests.ConnectTimeout,TimeoutError,requests.HTTPError):
            with self.subTest(exception=exception.__name__):
                self.assertFalse(stage3.blocked_exit_check(check=Mock(side_effect=exception('secret payload'))))

    def test_owned_alias_residual_blocks_watchdog_and_initial_tun_absence(self):
        import psutil
        for name in ('sing-tun','sing-tun-0123456789abcdef'):
            with self.subTest(name=name),patch.object(psutil,'net_if_addrs',return_value={name:[]}):
                self.assertFalse(stage3.tun_absent())
                marker=Mock()
                with patch.object(stage3,'cores_gone',return_value=True),patch.object(stage3,'raw_cleanup') as cleanup:
                    self.assertFalse(stage3.watchdog_cleanup(Mock(),marker))
                marker.unlink.assert_not_called()
                cleanup.assert_not_called()

    def test_adapter_diagnostics_use_current_alias_exactly_without_outputting_it(self):
        import psutil
        alias='sing-tun-private-current'
        address=Mock(address='198.18.0.1')
        with patch.object(psutil,'net_if_addrs',return_value={alias:[address],'sing-tun-old':[]}):
            facts=stage3.adapter_snapshot(alias)
        self.assertTrue(facts['alias_exact_present'])
        self.assertTrue(facts['expected_address_exact_alias'])
        self.assertEqual(facts['tun_alias_count'],2)
        self.assertNotIn(alias,str(facts))

    def test_startup_fatal_facts_identify_file_exists_without_exporting_sensitive_text(self):
        raw = ('FATAL start inbound/tun[tun-in]: WintunCreateAdapter configure tun interface: '
               'Cannot create a file when that file already exists. '
               'https://private-user:private-password@private-host:443/a '
               '192.0.2.9 2001:db8::9 {038538ab-ff8d-4956-9ae6-531ed0cf58a4} '
               'C:\\private-path\\secret private%2Duser private%2Dpassword')
        facts = stage3.startup_error_facts(raw)
        self.assertEqual(facts['reason'],'file-exists')
        self.assertIn('cannot-create-file-already-exists',facts['phrases'])
        self.assertIn('WintunCreateAdapter',facts['operations'])
        self.assertIn('configure-interface',facts['operations'])
        for sensitive in ('private','192.0.2.9','2001:db8','038538ab','https','password'):
            self.assertNotIn(sensitive,str(facts))

    def test_startup_error_facts_stop_after_core_started(self):
        module = Mock()
        module.PIPE = -1
        capture = stage3.MemoryCoreCapture(module,'D:/test/sing-box.exe')
        with patch.object(stage3.threading,'Thread'):
            capture.Popen(['D:/test/sing-box.exe'])
        attempt = capture.attempts[0]
        capture.feed(attempt,'FATAL WintunStartSession invalid handle private-token')
        self.assertEqual(len(attempt['startup_errors']),1)
        self.assertEqual(attempt['startup_errors'][0]['reason'],'invalid-handle')
        capture.feed(attempt,'INFO sing-box started')
        capture.feed(attempt,'ERROR connection private-password device is not ready')
        self.assertEqual(len(attempt['startup_errors']),1)

    def test_memory_core_capture_targets_only_test_executable_and_redacts_logs(self):
        module = Mock()
        module.PIPE = -1
        process = module.Popen.return_value
        capture = stage3.MemoryCoreCapture(module,'D:/test/sing-box.exe')
        with patch.object(stage3.threading,'Thread') as thread:
            returned = capture.Popen(['D:/test/sing-box.exe','run'],stderr='old')
        self.assertIs(returned,process)
        self.assertEqual(module.Popen.call_args.kwargs['stderr'],-1)
        thread.return_value.start.assert_called_once()
        attempt = capture.attempts[0]
        capture.feed(attempt,'DEBUG router: updated default interface secret-interface 203.0.113.1')
        capture.feed(attempt,'INFO inbound/tun[tun-in]: started at secret-alias')
        capture.feed(attempt,'INFO clash-api: restful api listening at secret-host')
        capture.feed(attempt,'INFO sing-box started secret-password')
        capture.feed(attempt,'FATAL ERROR create adapter access denied 0x00000005 secret-user')
        report = capture.snapshot()
        self.assertTrue(report[0]['flags']['default-interface-found'])
        self.assertTrue(report[0]['flags']['tun-start'])
        self.assertTrue(report[0]['flags']['clash-listening'])
        self.assertTrue(report[0]['flags']['core-started'])
        self.assertEqual(report[0]['reason'],'access-denied')
        self.assertEqual(report[0]['native_codes'],['0x00000005'])
        self.assertNotIn('secret',str(report))
        self.assertNotIn('203.0.113.1',str(report))
        capture.Popen(['D:/test/unrelated.exe'],stderr='original')
        self.assertEqual(module.Popen.call_args.kwargs['stderr'],'original')
        self.assertEqual(len(capture.attempts),1)

    def test_debug_config_changes_only_log_copy(self):
        manager = Mock()
        original = {'log':{'level':'warn','output':'private-output','timestamp':True},'other':{'value':'keep'}}
        manager.generate_config.return_value = original
        stage3.enable_debug_config(manager)
        modified = manager.generate_config()
        self.assertEqual(modified['log'],{'level':'debug','timestamp':True})
        self.assertEqual(modified['other'],original['other'])
        self.assertEqual(original['log']['output'],'private-output')
        self.assertEqual(original['log']['level'],'warn')

    def test_adapter_snapshot_reports_renamed_adapter_without_names_or_addresses(self):
        import psutil
        address = Mock(address='198.18.0.1')
        with patch.object(psutil,'net_if_addrs',return_value={'sing-tun 2':[address],'private-adapter':[]}):
            report = stage3.adapter_snapshot()
        self.assertEqual(report,{'alias_exact_present':False,'tun_alias_count':1,'expected_address_anywhere':True,'expected_address_exact_alias':False})
        self.assertNotIn('198.18.0.1',str(report))
        self.assertNotIn('private-adapter',str(report))

    def test_wait_ready_diagnostics_preserve_result_and_capture_poll_and_adapter_facts(self):
        manager = Mock()
        manager._wait_ready.return_value = False
        process = Mock()
        process.poll.return_value = None
        diagnostics = stage3.Diagnostics([])
        diagnostics.wrap(manager,'_wait_ready','wait-ready')
        with patch.object(stage3,'adapter_snapshot',side_effect=[{'alias_exact_present':False},{'alias_exact_present':True}]):
            self.assertFalse(manager._wait_ready(process))
        event = diagnostics.calls[0]
        self.assertFalse(event['returned'])
        self.assertFalse(event['process_exited'])
        self.assertFalse(event['adapters_before']['alias_exact_present'])
        self.assertTrue(event['adapters_after']['alias_exact_present'])

    def test_startup_error_classification_never_exports_arbitrary_message(self):
        classified = stage3.classify_startup_error(RuntimeError('FATAL ERROR address already in use secret-host password'))
        self.assertEqual(classified,{'reason':'address-in-use','fatal_flag':True,'error_flag':True})
        self.assertNotIn('secret',str(classified))

    def test_select_second_us_and_reverse_primary_without_saved_mutation(self):
        from core.proxy_model import ProxyItem
        rows = [ProxyItem('ee','hidden',443,country_code='EE'),ProxyItem('us1','hidden',443,country_code='US'),ProxyItem('us2','hidden',443,country_code='US')]
        pair,counts = stage3.select_pair(rows,primary='US',us_index=2)
        self.assertEqual([p.id for p in pair],['us2','ee'])
        self.assertEqual([p.id for p in rows],['ee','us1','us2'])
        self.assertIsNone(stage3.select_pair(rows,us_index=3)[0])
        self.assertIsNone(stage3.select_pair(rows,us_index=0)[0])

    def test_availability_only_selected_pair_quotes_auth_and_hides_payload(self):
        from core.proxy_model import ProxyItem
        rows = [ProxyItem('secret-id','secret-host',443,username='user@secret',password='pass:secret',country_code='US')]
        import requests
        session,response = Mock(),Mock()
        response.raw.read.return_value = b'203.0.113.1'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        session.get.return_value = response
        context = Mock()
        context.__enter__ = Mock(return_value=session)
        context.__exit__ = Mock(return_value=False)
        with patch.object(requests,'Session',return_value=context):
            report = stage3.availability(rows,us_index=2)
        self.assertEqual(report,[{'country':'US','index':2,'success':True}])
        kwargs = session.get.call_args.kwargs
        self.assertFalse(session.trust_env)
        self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(kwargs['timeout'],3)
        self.assertIn('user%40secret:pass%3Asecret@',kwargs['proxies']['https'])
        self.assertNotIn('secret',str(report))
        self.assertNotIn('203.0.113.1',str(report))

    def test_diagnostic_wrappers_preserve_results_and_sanitize_errors(self):
        manager = Mock()
        expected = object()
        manager.start.return_value = expected
        manager._probe_tunnel.side_effect = RuntimeError('secret-host secret-password 0x80320004')
        diagnostics = stage3.Diagnostics([])
        diagnostics.wrap(manager,'start','start')
        diagnostics.wrap(manager,'_probe_tunnel','probe')
        self.assertIs(manager.start(),expected)
        with self.assertRaises(RuntimeError):
            manager._probe_tunnel()
        self.assertEqual(diagnostics.calls[1]['error']['native_codes'],['0x80320004'])
        self.assertNotIn('secret',str(diagnostics.calls))
        self.assertTrue(all('seconds' in call for call in diagnostics.calls))

    def test_residual_tun_prevents_watchdog_release_marker_removal_and_success(self):
        marker,backend = Mock(),Mock()
        with patch.object(stage3,'cores_gone',return_value=True),patch.object(stage3,'tun_absent',return_value=False),patch.object(stage3,'raw_cleanup') as cleanup:
            self.assertFalse(stage3.watchdog_cleanup(backend,marker))
        cleanup.assert_not_called()
        marker.unlink.assert_not_called()

    def test_watchdog_cleanup_success_requires_tun_absent_after_release(self):
        marker,backend = Mock(),Mock()
        with patch.object(stage3,'cores_gone',return_value=True),patch.object(stage3,'tun_absent',side_effect=[True,False]),patch.object(stage3,'raw_cleanup') as cleanup:
            self.assertFalse(stage3.watchdog_cleanup(backend,marker))
        cleanup.assert_called_once_with(backend)
        marker.unlink.assert_not_called()

    def test_selector_first_saved_per_country_and_clones_without_exposing_secrets(self):
        from core.proxy_model import ProxyItem
        ee = ProxyItem('secret-id','secret-host',443,password='secret-password',country_code='EE')
        us = ProxyItem('secret-id2','secret-host2',443,password='secret-password2',country_code='US')
        pair,counts = stage3.select_pair([us,ee])
        self.assertEqual([p.get_country_code() for p in pair],['EE','US'])
        self.assertIsNot(pair[0],ee)
        self.assertEqual(counts,{'EE':1,'US':1})
        ee_second = dataclasses.replace(ee,id='another-secret',password='different-secret')
        us_second = dataclasses.replace(us,id='another-secret2')
        pair,counts = stage3.select_pair([ee,ee_second,us,us_second])
        self.assertEqual(pair[0],ee)
        self.assertEqual(pair[1],us)
        self.assertEqual(counts,{'EE':2,'US':2})
        pair,counts = stage3.select_pair([ee,ee_second])
        self.assertIsNone(pair)
        self.assertNotIn('secret',str(counts))

    def test_raw_cleanup_refuses_release_while_any_core_unconfirmed(self):
        backend = Mock()
        with patch.object(stage3,'cores_gone',return_value=False):
            with self.assertRaises(RuntimeError):
                stage3.raw_cleanup(backend)
        backend._call.assert_not_called()

    def test_raw_cleanup_uses_raw_keys_without_metadata_decode(self):
        backend = Mock()
        backend.dll.FwpmFilterDeleteByKey0.return_value = 0
        key = GUID.of(OWNER)
        with patch.object(stage3,'cores_gone',return_value=True),patch.object(stage3,'raw_keys',side_effect=[[key],[],[]]):
            stage3.raw_cleanup(backend)
        backend.read.assert_not_called()
        backend._decode.assert_not_called()
        self.assertEqual([c.args[0] for c in backend._call.call_args_list],['FwpmTransactionBegin0','FwpmTransactionCommit0'])

    def test_guard_must_be_ready_before_job_or_manager(self):
        guard,backend = Mock(),Mock()
        guard.require_ready.side_effect = RuntimeError('not ready')
        with patch.object(stage3.smoke,'tcp',return_value='connected'),patch.object(stage3,'exit_ip',return_value='hidden'),patch.object(stage3.smoke,'rehearse'),patch('core.win_job.bind_self_to_job') as bind:
            from core.proxy_model import ProxyItem
            pair = [ProxyItem('hidden1','hidden1',443,country_code='EE'),ProxyItem('hidden2','hidden2',443,country_code='US')]
            result = stage3.exercise(pair,backend,guard,Mock())
        self.assertFalse(result['ok'])
        bind.assert_not_called()
        guard.finish.assert_called_once()

    def test_report_errors_omit_arbitrary_text(self):
        result = stage3.smoke.error(RuntimeError('secret-host password secret 0x80320004'))
        self.assertEqual(result['native_codes'],['0x80320004'])
        self.assertNotIn('secret',str(result))
