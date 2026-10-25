import multiprocessing
import threading
import time
import unittest
from unittest.mock import Mock


def stalled_ip(sender, deadline, gate):
    gate.wait()
    time.sleep(30)


def successful_ip(sender, deadline, gate):
    if gate.wait(1): sender.send({'ip': '203.0.113.7', 'status': 'ready'})
    sender.close()


class IpWorkerTests(unittest.TestCase):
    def test_successful_child_is_reaped_before_return(self):
        from core.ip_worker import IpQueryService
        service = IpQueryService(lambda _: True, binder=lambda _: True, target=successful_ip)
        self.assertEqual(service.run(1)['ip'], '203.0.113.7')
        self.assertTrue(service.stop())

    def test_cancel_kills_stalled_query_and_confirms_exit(self):
        from core.ip_worker import IpQueryService
        bound = threading.Event()
        def binder(_):
            bound.set()
            return True
        service = IpQueryService(lambda _: True, binder=binder, target=stalled_ip)
        result = []
        thread = threading.Thread(target=lambda: result.append(service.run(1)))
        thread.start()
        try:
            self.assertTrue(bound.wait(2))
            self.assertTrue(service.stop())
        finally:
            service.cancel(); thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0]['status'], 'unavailable')

    def test_context_invalidated_during_binding_never_opens_request_gate(self):
        from core.ip_worker import IpQueryService
        context = Mock(); process = Mock(pid=1, sentinel=2)
        process.is_alive.return_value = False
        context.Process.return_value = process
        context.Pipe.return_value = (Mock(), Mock())
        valid = [True]
        def binder(_):
            valid[0] = False
            return True
        service = IpQueryService(lambda _: valid[0], binder=binder, context_factory=lambda: context)
        self.assertEqual(service.run(1)['status'], 'unavailable')
        context.Event.return_value.set.assert_not_called()
        self.assertTrue(service.stop())

    def test_deadline_reaps_stalled_spawn_and_allows_next_refresh(self):
        from core.ip_worker import IpQueryService
        service = IpQueryService(lambda _: True, binder=lambda _: True, target=stalled_ip)
        before = {p.pid for p in multiprocessing.active_children()}
        for _ in range(2):
            started = time.monotonic()
            self.assertEqual(service.run('context', timeout=.15)['status'], 'unavailable')
            self.assertLess(time.monotonic() - started, 1.5)
            self.assertTrue(service.stop())
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)

    def test_failed_job_binding_does_not_open_gate(self):
        from core.ip_worker import IpQueryService
        context = Mock(); process = Mock(pid=1, sentinel=2)
        process.is_alive.return_value = False
        context.Process.return_value = process
        context.Pipe.return_value = (Mock(), Mock())
        service = IpQueryService(lambda _: True, binder=lambda _: False, context_factory=lambda: context)
        self.assertEqual(service.run(1)['status'], 'unavailable')
        context.Event.return_value.set.assert_not_called()
        self.assertTrue(service.stop())

    def test_unconfirmed_exit_blocks_release_and_respawn_until_reaped(self):
        from core.ip_worker import IpQueryService
        context = Mock(); process = Mock(pid=1, sentinel=2)
        process.is_alive.return_value = True
        process.terminate.side_effect = OSError()
        process.kill.side_effect = OSError()
        context.Process.return_value = process
        context.Pipe.return_value = (Mock(), Mock())
        service = IpQueryService(lambda _: True, binder=lambda _: False, context_factory=lambda: context)
        service.run(1)
        self.assertFalse(service.stop(timeout=.01))
        service.run(2)
        self.assertEqual(context.Process.call_count, 1)
        process.is_alive.return_value = False
        self.assertTrue(service.stop())
