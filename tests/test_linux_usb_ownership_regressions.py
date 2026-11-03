"""Verifier regressions; fake resources are always recovered, including RED."""
import sys
import threading
import time
import unittest
from unittest import mock

from mars_display import linux_usb_process as process
from mars_display import usb_ipc as ipc
import test_linux_usb_process as existing


class Endpoint:
    def __init__(self, fail=False):
        self.recover = threading.Event()
        if not fail:
            self.recover.set()
        self.attempted = threading.Event()
        self.closed = False

    def fileno(self):
        return 123

    def close(self):
        self.attempted.set()
        if not self.recover.is_set():
            raise OSError('injected endpoint close failure')
        self.closed = True


class Child:
    def __init__(self):
        self.killed = threading.Event()
        self.waited = threading.Event()
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed.set()

    def wait(self, timeout):
        self.returncode = -9
        self.waited.set()
        return self.returncode


class OwnershipRegressions(unittest.TestCase):
    def owner(self, start=2):
        return process.OwnedWorker(123, existing.NONCE, ipc.Budgets(start=start, reap=.05),
                                   launcher=lambda *args: ['test-only'])

    def test_endpoint_failure_never_starves_reap_and_recovery_closes(self):
        for failed in ('control', 'child_endpoint'):
            with self.subTest(failed=failed):
                control = Endpoint(failed == 'control')
                endpoint = Endpoint(failed == 'child_endpoint')
                resource = control if failed == 'control' else endpoint
                child, owner = Child(), self.owner()
                with mock.patch.object(process.socket, 'socketpair', return_value=(control, endpoint)), \
                        mock.patch.object(process.subprocess, 'Popen', return_value=child), \
                        mock.patch.object(process.ipc, 'receive_packet', side_effect=ipc.ProtocolError('reject')):
                    try:
                        owner.start()
                        self.assertTrue(resource.attempted.wait(1))
                        self.assertTrue(child.waited.wait(1), 'endpoint failure starved child reap')
                        self.assertTrue(child.killed.is_set())
                        with self.assertRaises(RuntimeError):
                            owner.stop(time.monotonic() + .02)
                        self.assertTrue(owner.reaped)
                        self.assertFalse(owner.closed)
                        self.assertIs(getattr(owner, failed), resource)
                        self.assertTrue(owner.thread.is_alive())
                    finally:
                        control.recover.set()
                        endpoint.recover.set()
                        owner.stop(time.monotonic() + 2)
                self.assertTrue(owner.closed)
                self.assertTrue(owner.reaped)
                self.assertTrue(control.closed and endpoint.closed)
                self.assertIsNone(owner.control)
                self.assertIsNone(owner.child_endpoint)

    def run_registration_case(self, mode):
        control, endpoint, child = Endpoint(), Endpoint(), Child()
        parsed = threading.Event()
        cancel, owner = threading.Event(), self.owner(start=.3 if mode == 'deadline' else 2)
        if mode == 'pre-cancel':
            cancel.set()

        def receive(*args, **kwargs):
            parsed.set()
            return ipc.HELLO, 0, bytes.fromhex(existing.NONCE)

        with mock.patch.object(process.socket, 'socketpair', return_value=(control, endpoint)), \
                mock.patch.object(process.subprocess, 'Popen', return_value=child), \
                mock.patch.object(process.ipc, 'receive_packet', side_effect=receive), \
                mock.patch.object(process.ipc, 'send_packet') as send:
            try:
                owner.start()
                self.assertTrue(parsed.wait(1))
                if mode == 'deadline':
                    self.assertTrue(owner.ready.wait(1))
                    self.assertIsInstance(owner.fault, TimeoutError)
                else:
                    # Give the old implementation its startup notification: it
                    # incorrectly completes without cancellation registration.
                    self.assertFalse(owner.ready.wait(.1), 'startup released before registration')
                    if mode == 'pre-cancel':
                        with self.assertRaises(ipc.Cancelled):
                            owner.wait_start(time.monotonic() + 1, cancel)
                    elif mode == 'release-first':
                        owner.wait_start(time.monotonic() + 1, cancel)
                        self.assertTrue(owner.released)
                        send.assert_called_once()
                        cancel.set()
                        with self.assertRaises(ipc.Cancelled):
                            owner.wait_start(time.monotonic() + 1, cancel)
                    elif mode == 'caller-deadline':
                        with self.assertRaises(TimeoutError):
                            owner.wait_start(time.monotonic(), cancel)
                if mode != 'release-first':
                    self.assertFalse(owner.released)
                    send.assert_not_called()
            finally:
                owner.stop(time.monotonic() + 2)
            self.assertTrue(owner.closed)
            self.assertTrue(owner.reaped)

    def test_pre_cancelled_delayed_registration_never_releases(self):
        self.run_registration_case('pre-cancel')

    def test_registration_wait_deadline_stop_and_release_first(self):
        for mode in ('deadline', 'stop', 'caller-deadline', 'release-first'):
            with self.subTest(mode=mode):
                self.run_registration_case(mode)


class CollectionRegressions(unittest.TestCase):
    def cases(self, suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                yield from self.cases(item)
            else:
                yield item

    def test_windows_collection_retains_portable_cases_without_linux_skips(self):
        with mock.patch.object(existing.sys, 'platform', 'win32'):
            cases = list(self.cases(unittest.TestLoader().loadTestsFromModule(existing)))
        self.assertTrue(cases)
        self.assertTrue(all(isinstance(case, existing.OwnerTests) for case in cases))
        self.assertEqual(len(cases), len(unittest.TestLoader().getTestCaseNames(existing.OwnerTests)))
        self.assertFalse(any(getattr(case, '__unittest_skip__', False) for case in cases))

    def test_actual_host_collection(self):
        cases = list(self.cases(unittest.TestLoader().loadTestsFromModule(existing)))
        real = [case for case in cases if isinstance(case, existing.RealOwnerTests)]
        self.assertEqual(len(real), 6 if sys.platform == 'linux' else 0)
        self.assertFalse(any(getattr(case, '__unittest_skip__', False) for case in cases))
