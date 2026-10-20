import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from mars_display import usb_probe_process as process


class ProcessTests(unittest.TestCase):
    def test_launch_vectors(self):
        self.assertEqual(process.launch_vector(True, 'probe.exe', 'entry.py'), ['probe.exe'])
        self.assertEqual(process.launch_vector(False, 'python.exe', 'entry.py'), ['python.exe', '-B', 'entry.py'])

    def test_owned_hang_is_reaped(self):
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(20)'])
        self.assertEqual(process.wait_owned(child, 0.05), 8)
        self.assertIsNotNone(child.poll())

    def test_normal_exit_is_preserved(self):
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'raise SystemExit(4)'])
        self.assertEqual(process.wait_owned(child, 2), 4)

    def test_marker_is_consumed_and_invalid_entry_rejected(self):
        env = {process.MARKER: 'a'*32}
        self.assertEqual(process.consume_marker(env), 'a'*32)
        self.assertEqual(env, {})
        self.assertIsNone(process.consume_marker({process.MARKER: 'bad'}))

    def test_supervisor_orders_gate_and_reaps_failures(self):
        for failure in (None, 'start', 'assign', 'release'):
            events = []
            class Child:
                def wait(self, timeout):
                    events.append('wait')
                    return 0
                def poll(self):
                    return None
                def kill(self):
                    events.append('kill')
            class Gate:
                def __init__(self, marker):
                    self.marker = marker
                def __enter__(self):
                    events.append('gate')
                    return self
                def assign(self, child):
                    events.append('assign')
                    if failure == 'assign':
                        raise OSError
                def release(self):
                    events.append('release')
                    if failure == 'release':
                        raise OSError
                def __exit__(self, *_):
                    events.append('close')
            def start(vector, **kwargs):
                events.append('start')
                self.assertEqual(vector[-2:], ['--port', 'COM5'])
                self.assertEqual(set(kwargs), {'env', 'stdin', 'stdout', 'stderr'})
                self.assertIs(kwargs['stdin'], sys.stdin)
                self.assertIs(kwargs['stdout'], sys.stdout)
                self.assertIs(kwargs['stderr'], sys.stderr)
                self.assertRegex(kwargs['env'][process.MARKER], '^[0-9a-f]{32}$')
                if failure == 'start':
                    raise OSError
                return Child()
            result = process.supervise(['--port', 'COM5'], popen=start,
                                       gate_factory=Gate, platform='nt')
            self.assertEqual(result, 0 if failure is None else 7)
            expected = {
                None: ['gate', 'start', 'assign', 'release', 'wait', 'close'],
                'start': ['gate', 'start', 'close'],
                'assign': ['gate', 'start', 'assign', 'close', 'kill', 'wait'],
                'release': ['gate', 'start', 'assign', 'release', 'close', 'kill', 'wait'],
            }
            self.assertEqual(events, expected[failure])

    def test_worker_gate_precedes_core_and_consumes_marker(self):
        import io
        from mars_display import usb_probe
        for released in (False, True):
            env = {process.MARKER: 'a'*32}
            with patch.dict(os.environ, env, clear=True), patch.object(process, 'await_gate', return_value=released) as gate, patch.object(usb_probe, 'run', return_value=4) as core, patch('sys.stderr', new_callable=io.StringIO) as error:
                self.assertEqual(usb_probe.main(['--port', 'COM5']), 4 if released else 7)
                gate.assert_called_once_with('a'*32)
                self.assertNotIn(process.MARKER, os.environ)
                self.assertEqual(core.call_count, int(released))
                self.assertEqual(error.getvalue(), '' if released else usb_probe.ERRORS[7]+'\n')

    @unittest.skipUnless(os.name == 'nt', 'native Windows job/event qualification required')
    def test_native_job_owns_and_kills_child(self):
        with process.WindowsJobGate('a'*32) as gate:
            child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(20)'])
            try:
                gate.assign(child)
                gate.release()
            except BaseException:
                child.kill()
                child.wait(timeout=2)
                raise
        self.assertNotEqual(process.wait_owned(child, 2), 8)
        self.assertIsNotNone(child.poll())

    @unittest.skipUnless(os.name == 'nt', 'native Windows job/event qualification required')
    def test_native_worker_waits_for_gate_and_gate_times_out(self):
        for release in (True, False):
            marker = 'c'*32
            with process.WindowsJobGate(marker) as gate:
                script = ('from mars_display.usb_probe_process import await_gate; '
                          f'raise SystemExit(0 if await_gate({marker!r}) else 7)')
                child = subprocess.Popen([sys.executable, '-B', '-c', script])
                try:
                    gate.assign(child)
                    with self.assertRaises(subprocess.TimeoutExpired):
                        child.wait(timeout=0.1)
                    if release:
                        gate.release()
                    self.assertEqual(process.wait_owned(child, 7), 0 if release else 7)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait(timeout=2)

    @unittest.skipUnless(os.name == 'nt', 'native Windows job/event qualification required')
    def test_native_gate_missing_fails_closed(self):
        self.assertFalse(process.await_gate('b'*32))
