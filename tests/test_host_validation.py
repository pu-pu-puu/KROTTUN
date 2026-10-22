import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
from unittest.mock import patch
import ctypes as C
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

    def test_selector_exact_unique_and_clones_without_exposing_secrets(self):
        from core.proxy_model import ProxyItem
        ee = ProxyItem('secret-id','secret-host',443,password='secret-password',country_code='EE')
        us = ProxyItem('secret-id2','secret-host2',443,password='secret-password2',country_code='US')
        pair,counts = stage3.select_pair([us,ee])
        self.assertEqual([p.get_country_code() for p in pair],['EE','US'])
        self.assertIsNot(pair[0],ee)
        self.assertEqual(counts,{'EE':1,'US':1})
        pair,counts = stage3.select_pair([ee,ee,us])
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
            result = stage3.exercise([],backend,guard,Mock())
        self.assertFalse(result['ok'])
        bind.assert_not_called()
        guard.finish.assert_called_once()

    def test_report_errors_omit_arbitrary_text(self):
        result = stage3.smoke.error(RuntimeError('secret-host password secret 0x80320004'))
        self.assertEqual(result['native_codes'],['0x80320004'])
        self.assertNotIn('secret',str(result))
