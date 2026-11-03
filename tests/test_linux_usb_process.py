"""Owned Linux process tests; every child has bounded unconditional cleanup."""
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

from mars_display import linux_usb_process as process
from mars_display import usb_ipc as ipc

NONCE = 'ab' * 32
FIXTURE = str(Path(__file__).with_name('linux_usb_process_fixture.py'))


class FakeChild:
    def __init__(self):
        self.returncode = None
        self.kills = 0
        self.reap = threading.Event()

    def poll(self):
        return self.returncode

    def kill(self):
        self.kills += 1

    def wait(self, timeout):
        if not self.reap.wait(timeout):
            raise subprocess.TimeoutExpired('fixture', timeout)
        self.returncode = -9
        return -9


class OwnerTests(unittest.TestCase):
    def owner(self, launcher=lambda *args: ['test-only']):
        owner = process.OwnedWorker(123, NONCE, ipc.Budgets(start=1, reap=.05), launcher=launcher)
        self.addCleanup(lambda: owner.stop(time.monotonic() + 3))
        return owner

    def test_required_launcher_and_safe_unstarted_stop(self):
        with self.assertRaises(TypeError):
            process.OwnedWorker(123, NONCE, ipc.Budgets())
        owner = self.owner()
        owner.stop(time.monotonic() + 1)
        self.assertTrue(owner.closed)
        with self.assertRaises(RuntimeError):
            owner.start()

    def test_cancel_before_spawn(self):
        launcher = mock.Mock()
        owner = self.owner(launcher)
        external = threading.Event()
        external.set()
        with self.assertRaises(ipc.Cancelled):
            owner.wait_start(time.monotonic() + 1, external)
        owner.start()
        owner.stop(time.monotonic() + 1)
        launcher.assert_not_called()
        self.assertTrue(owner.closed)

    def test_delayed_spawn_cancel_and_timeout_retain_then_reap(self):
        for cancel in (True, False):
            with self.subTest(cancel=cancel):
                entered, proceed = threading.Event(), threading.Event()
                child = FakeChild()
                owner = self.owner()
                external = threading.Event()

                def popen(*args, **kwargs):
                    self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
                    self.assertEqual(kwargs['stdout'], subprocess.DEVNULL)
                    self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)
                    self.assertTrue(kwargs['close_fds'])
                    self.assertFalse(kwargs['shell'])
                    self.assertEqual(len(kwargs['pass_fds']), 1)
                    entered.set()
                    if not proceed.wait(3):
                        raise RuntimeError('test watchdog')
                    return child

                with mock.patch.object(process.subprocess, 'Popen', side_effect=popen):
                    try:
                        owner.start()
                        self.assertTrue(entered.wait(1))
                        if cancel:
                            external.set()
                        with self.assertRaises(ipc.Cancelled if cancel else TimeoutError):
                            owner.wait_start(time.monotonic() + .03, external)
                        with self.assertRaises(RuntimeError):
                            owner.stop(time.monotonic() + .03)
                        self.assertFalse(owner.closed)
                        self.assertTrue(owner.thread.is_alive())
                        proceed.set()
                        with self.assertRaises(RuntimeError):
                            owner.stop(time.monotonic() + .03)
                        self.assertFalse(owner.released)
                    finally:
                        proceed.set()
                        child.reap.set()
                        owner.stop(time.monotonic() + 2)
                self.assertTrue(owner.closed)
                self.assertTrue(owner.reaped)
                self.assertGreater(child.kills, 0)

    def test_popen_and_thread_start_failure_are_safe(self):
        owner = self.owner()
        with mock.patch.object(process.threading.Thread, 'start', side_effect=RuntimeError('no thread')):
            with self.assertRaises(RuntimeError):
                owner.start()
        owner.stop(time.monotonic() + 1)
        self.assertTrue(owner.closed)
        owner = self.owner()
        with mock.patch.object(process.subprocess, 'Popen', side_effect=OSError('no process')):
            owner.start()
            with self.assertRaises(OSError):
                owner.wait_start(time.monotonic() + 1, threading.Event())
            owner.stop(time.monotonic() + 1)
        self.assertIsNone(owner.control)
        self.assertIsNone(owner.child_endpoint)

    def test_bad_ready_and_unexpected_supervisor_exception_cleanup(self):
        cases = [(ipc.OPEN, 1, bytes.fromhex(NONCE)), (ipc.HELLO, 0, b'x' * 32),
                 ipc.ProtocolError('truncated'), KeyboardInterrupt('unexpected')]
        for response in cases:
            with self.subTest(response=response):
                owner = self.owner()
                child = FakeChild()
                child.reap.set()
                options = {'side_effect': response} if isinstance(response, BaseException) else {'return_value': response}
                with mock.patch.object(process.subprocess, 'Popen', return_value=child), \
                        mock.patch.object(process.ipc, 'receive_packet', **options):
                    owner.start()
                    with self.assertRaises(type(response) if isinstance(response, BaseException) else ipc.ProtocolError):
                        owner.wait_start(time.monotonic() + 1, threading.Event())
                    owner.stop(time.monotonic() + 1)
                self.assertTrue(owner.closed)
                self.assertTrue(owner.reaped)
                self.assertFalse(owner.released)
                self.assertEqual(child.kills, 1)
                self.assertIsNone(owner.control)
                self.assertIsNone(owner.child_endpoint)

    def test_launcher_exception_is_closed_and_start_fails(self):
        owner = self.owner(mock.Mock(side_effect=RuntimeError('creation failed')))
        owner.start()
        with self.assertRaises(RuntimeError):
            owner.wait_start(time.monotonic() + 1, threading.Event())
        owner.stop(time.monotonic() + 1)
        self.assertTrue(owner.closed)


class RealOwnerTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(sys.platform, 'linux', 'Linux process semantics required')
        self.assertNotEqual(os.geteuid(), 0, 'Run real admission tests as non-root')
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen()
        self.listener.settimeout(3)
        self.addCleanup(self.listener.close)
        self.owner = None

    def launch(self, start=2):
        port = self.listener.getsockname()[1]

        def launcher(unused, nonce, fd, parent, deadline):
            return [sys.executable, '-B', FIXTURE, str(fd), nonce, str(parent), str(deadline), str(port)]

        self.owner = process.OwnedWorker(123, NONCE, ipc.Budgets(start=start, reap=.2), launcher=launcher)
        self.addCleanup(lambda: self.owner.stop(time.monotonic() + 3))
        self.owner.start()
        self.report, _ = self.listener.accept()
        self.report.settimeout(3)
        self.addCleanup(self.report.close)
        self.stream = self.report.makefile('rwb', buffering=0)
        self.addCleanup(self.stream.close)
        self.assertTrue(self.stream.readline().startswith(b'START '))

    def arm(self):
        self.stream.write(b'ARM\n')
        self.assertEqual(self.stream.readline(), b'ARMED\n')

    def test_persistent_supervisor_release_first_and_reap(self):
        self.launch()
        self.arm()
        self.assertFalse(self.owner.released)
        self.assertFalse(self.owner.ready.is_set())
        self.stream.write(b'READY\n')
        self.owner.wait_start(time.monotonic() + 2, threading.Event())
        self.assertEqual(self.stream.readline(), b'ADMITTED\n')
        self.assertTrue(self.owner.thread.is_alive())
        self.assertIsNone(self.owner.child.poll())
        for _ in range(2):
            self.stream.write(b'PING\n')
            self.assertEqual(self.stream.readline(), b'PONG\n')
        self.owner.stop(time.monotonic() + 2)
        self.assertTrue(self.owner.reaped)
        self.assertTrue(self.owner.closed)
        self.assertFalse(self.owner.thread.is_alive())
        self.assertEqual(self.stream.readline(), b'')

    def test_cancel_before_ready_prevents_admission(self):
        self.launch()
        self.arm()
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(ipc.Cancelled):
            self.owner.wait_start(time.monotonic() + 1, cancel)
        self.owner.stop(time.monotonic() + 2)
        self.assertFalse(self.owner.released)
        self.assertEqual(self.stream.readline(), b'')
        self.assertTrue(self.owner.closed)

    def test_admission_deadline_and_duplicate_endpoint_closed(self):
        self.launch(start=.3)
        self.arm()
        with self.assertRaises(TimeoutError):
            self.owner.wait_start(time.monotonic() + .05, threading.Event())
        self.owner.stop(time.monotonic() + 2)
        self.assertFalse(self.owner.released)
        self.assertIsNone(self.owner.control)
        self.assertIsNone(self.owner.child_endpoint)
        self.assertEqual(self.stream.readline(), b'')

    def test_cancel_after_ready_parsed_before_release(self):
        # Cleanup closes control before kill. Force each child scheduling order;
        # neither may receive a release or enter the fixture's admitted PING loop.
        for order in ('kill_before_read', 'reject_before_kill'):
            with self.subTest(order=order):
                parsed, proceed = threading.Event(), threading.Event()
                killing, allow_kill = threading.Event(), threading.Event()
                receive = ipc.receive_packet

                def hold(*args, **kwargs):
                    result = receive(*args, **kwargs)
                    parsed.set()
                    if not proceed.wait(3):
                        raise RuntimeError('test receive watchdog')
                    return result

                with mock.patch.object(process.ipc, 'receive_packet', side_effect=hold), \
                        mock.patch.object(process.ipc, 'send_packet', wraps=ipc.send_packet) as release:
                    try:
                        self.launch()
                        self.arm()
                        command = b'READY HOLD_READ\n' if order == 'kill_before_read' else b'READY HOLD_REJECT\n'
                        self.stream.write(command)
                        self.assertTrue(parsed.wait(2))
                        if order == 'kill_before_read':
                            self.assertEqual(self.stream.readline(), b'WAITING\n')
                        kill = self.owner.child.kill

                        def hold_kill():
                            killing.set()
                            if not allow_kill.wait(3):
                                raise RuntimeError('test kill watchdog')
                            kill()

                        with mock.patch.object(self.owner.child, 'kill', side_effect=hold_kill):
                            cancel = threading.Event()
                            cancel.set()
                            with self.assertRaises(ipc.Cancelled):
                                self.owner.wait_start(time.monotonic() + 1, cancel)
                            proceed.set()
                            self.assertTrue(killing.wait(2))
                            self.assertIsNone(self.owner.control)
                            self.assertIsNone(self.owner.child_endpoint)
                            rejection = self.stream.readline() if order == 'reject_before_kill' else b''
                            allow_kill.set()
                            self.owner.stop(time.monotonic() + 2)
                        self.assertFalse(self.owner.released)
                        release.assert_not_called()
                        self.assertTrue(self.owner.reaped)
                        self.assertTrue(self.owner.closed)
                        self.assertFalse(self.owner.thread.is_alive())
                        self.assertEqual(self.owner.child.returncode, -9)
                        self.assertEqual(rejection, b'REJECTED\n' if order == 'reject_before_kill' else b'')
                        # Exact terminal transcript: no ADMITTED or PONG effects.
                        self.assertEqual(self.stream.read(), b'')
                    finally:
                        proceed.set()
                        allow_kill.set()
                        if self.owner is not None:
                            self.owner.stop(time.monotonic() + 2)

    def test_creator_thread_before_after_arm_and_whole_parent_death(self):
        def output_line(child):
            self.assertTrue(select.select([child.stdout], [], [], 4)[0], 'fixture output watchdog')
            return child.stdout.readline()

        for phase in ('before', 'after', 'process'):
            with self.subTest(phase=phase):
                mode = 'death-watch' if phase == 'process' else 'creator'
                outer = subprocess.Popen([sys.executable, '-B', FIXTURE, mode,
                    str(self.listener.getsockname()[1])], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                report = stream = None
                try:
                    report, _ = self.listener.accept()
                    report.settimeout(4)
                    stream = report.makefile('rwb', buffering=0)
                    self.assertTrue(stream.readline().startswith(b'START '))
                    self.assertEqual(output_line(outer), 'CREATED\n')
                    if phase != 'before':
                        stream.write(b'ARM\n')
                        self.assertEqual(stream.readline(), b'ARMED\n')
                    outer.stdin.write('PROCESS\n' if phase == 'process' else 'THREAD\n')
                    outer.stdin.flush()
                    if phase == 'before':
                        self.assertEqual(output_line(outer), 'CREATOR_EXITED\n')
                        # PPID remains unchanged and PDEATHSIG is not retroactive.
                        stream.write(b'ARM\n')
                        self.assertEqual(stream.readline(), b'ARMED\n')
                        stream.write(b'READY\n')
                        self.assertEqual(stream.readline(), b'REJECTED\n')
                    else:
                        self.assertEqual(stream.readline(), b'')
                    output, error = outer.communicate(timeout=8)
                    self.assertEqual(outer.returncode, 0, error)
                    self.assertEqual(error, '')
                    self.assertIn('REAPED 3' if phase == 'before' else
                                  'ADOPTED -9' if phase == 'process' else 'REAPED -9', output)
                finally:
                    if stream is not None:
                        stream.close()
                    if report is not None:
                        report.close()
                    if outer.poll() is None:
                        outer.kill()
                    outer.communicate(timeout=3)

    def test_natural_exit_reaped_by_persistent_creator(self):
        self.launch()
        self.arm()
        self.stream.write(b'READY\n')
        self.owner.wait_start(time.monotonic() + 2, threading.Event())
        self.assertEqual(self.stream.readline(), b'ADMITTED\n')
        self.stream.write(b'EXIT\n')
        self.owner.thread.join(2)
        self.assertFalse(self.owner.thread.is_alive())
        self.assertEqual(self.owner.child.poll(), 0)
        self.assertTrue(self.owner.closed)


def load_tests(loader, tests, pattern):
    """Windows zero-skip CI still runs every portable owner test.

    Linux semantic tests are registered only on Linux; root is an explicit
    test failure there, not a skipped or silently bypassed admission guard.
    """
    suite = loader.loadTestsFromTestCase(OwnerTests)
    if sys.platform == 'linux':
        suite.addTests(loader.loadTestsFromTestCase(RealOwnerTests))
    return suite


if __name__ == '__main__':
    unittest.main()
