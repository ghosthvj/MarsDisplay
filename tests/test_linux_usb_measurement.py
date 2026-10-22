"""Linux measurement commands; all inventory and serial access is fake."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import os
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from mars_display import linux_usb_measurement as probe
from mars_display.devices import USBSerialDescriptor
from mars_display.usb_grouping_profile import fixed_encoder, load_fixture

DEVICE = USBSerialDescriptor('/dev/ttyACM0', 0x1a86, 0x5722, 'USB35INCHIPSV2',
                             None, None, 'Turing', 'UsbMonitor', None)


class FakeSerial:
    def __init__(self, **options):
        self.options, self.events, self.packets = options, [], []
        self.out_waiting = 0
    def open(self):
        self.events.append('open')
    def write(self, packet):
        self.packets.append(packet)
        return len(packet)
    def close(self):
        self.events.append('close')


class Commands(unittest.TestCase):
    def invoke(self, args, answer='', *, snapshots=None, serial=None, supervisor=None):
        serial = serial or FakeSerial()
        snapshots = iter(snapshots or [(DEVICE,)] * 3)
        out, err = io.StringIO(), io.StringIO()
        def construct(**options):
            serial.options = options
            return serial
        with patch.object(probe, 'enumerate_devices', side_effect=lambda: next(snapshots)) as inventory, \
                patch.object(probe, 'serial_factory', side_effect=construct) as factory, \
                patch.object(probe, 'supervise', side_effect=supervisor or probe.measure), \
                patch.object(probe.sys, 'platform', 'linux'), \
                redirect_stdout(out), redirect_stderr(err):
            code = probe.main(args, read=lambda: answer)
        return (code, out.getvalue(), err.getvalue()), serial, inventory.call_count, factory.call_count

    def test_safe_routes_never_inventory_or_construct_serial(self):
        for args, code, message in [([], 0, probe.HELP), (['--help'], 0, probe.HELP),
                (['--self-test'], 0, probe.SELFTEST), (['--run', '--repeat'], 2, probe.INVALID)]:
            result, serial, inventory, factory = self.invoke(args)
            self.assertEqual(result, (code, message + '\n', ''))
            self.assertEqual((inventory, factory, serial.events, serial.packets), (0, 0, [], []))

    def test_cancel_eof_and_wrong_confirmation_never_open(self):
        for answer in ('', 'COM5', 'SEND /dev/ttyACM1'):
            result, serial, _, factory = self.invoke(['--run'], answer)
            self.assertEqual(result, (1, probe.NOTICE + '\n' + probe.prompt(DEVICE.device) + '\n' + probe.CANCELLED + '\n', ''))
            self.assertEqual((factory, serial.events, serial.packets), (0, [], []))
        out = io.StringIO()
        with patch.object(probe, 'enumerate_devices', return_value=(DEVICE,)), \
                patch.object(probe.sys, 'platform', 'linux'), \
                patch.object(probe, 'supervise') as child, redirect_stdout(out):
            self.assertEqual(probe.main(['--run'], read=lambda: (_ for _ in ()).throw(EOFError())), 1)
            child.assert_not_called()
        self.assertTrue(out.getvalue().endswith(probe.CANCELLED + '\n'))

    def test_single_exact_baseline_frame_and_report(self):
        def measured(port):
            with patch.object(probe.time, 'monotonic', return_value=1):
                return probe.measure(port)
        result, serial, inventory, factory = self.invoke(['--run'], 'SEND /dev/ttyACM0', supervisor=measured)
        numbers = {name: 0.0 for name in probe.STAGES}
        self.assertEqual(result, (0, probe.NOTICE + '\n' + probe.prompt(DEVICE.device) + '\n' + probe.report(numbers) + '\n', ''))
        self.assertEqual(serial.packets, list(fixed_encoder('A', load_fixture())(load_fixture())))
        self.assertEqual((len(serial.packets), sum(map(len, serial.packets))), (122, 307222))
        self.assertEqual(serial.events, ['open', 'close'])
        self.assertEqual((inventory, factory), (3, 1))
        self.assertEqual(serial.options, dict(port=None, baudrate=115200, bytesize=8,
            parity='N', stopbits=1, rtscts=True, dsrdtr=False, write_timeout=3, timeout=1, exclusive=True))
        self.assertEqual((serial.port, serial.dtr), (DEVICE.device, True))

    def test_identity_absence_ambiguity_occupancy_and_changes_reject(self):
        invalid = [(), (DEVICE, DEVICE), (replace(DEVICE, serial_number='other'),),
                   (replace(DEVICE, device='COM5'),),
                   (DEVICE, replace(DEVICE, serial_number='other'))]
        for snapshot in invalid:
            result, serial, _, factory = self.invoke(['--run'], 'SEND /dev/ttyACM0', snapshots=[snapshot])
            self.assertEqual(result, (4, probe.NOTICE + '\n' + probe.FAILED + '\n', ''))
            self.assertEqual((factory, serial.events, serial.packets), (0, [], []))
        moved = (replace(DEVICE, device='/dev/ttyACM1'),)
        for snapshots, events in [([(DEVICE,), moved], []),
                                   ([(DEVICE,), (DEVICE,), moved], ['open', 'close'])]:
            result, serial, _, _ = self.invoke(['--run'], 'SEND /dev/ttyACM0', snapshots=snapshots)
            self.assertEqual(result, (4, probe.NOTICE + '\n' + probe.prompt(DEVICE.device) + '\n' + probe.FAILED + '\n', ''))
            self.assertEqual((serial.events, serial.packets), (events, []))

    def test_port_errors_short_write_drain_deadline_and_close_failure_never_retry(self):
        for failure in ('open', 'write', 'short', 'drain', 'close'):
            serial = FakeSerial()
            if failure in ('open', 'write', 'close'):
                setattr(serial, failure, lambda *args: (_ for _ in ()).throw(OSError('private')))
            elif failure == 'short':
                serial.write = lambda packet: 0
            else:
                serial.out_waiting = 1
            with patch.object(probe, 'DRAIN_SECONDS', 0) if failure == 'drain' else patch.object(probe, 'DRAIN_SECONDS', 15):
                result, _, _, factory = self.invoke(['--run'], 'SEND /dev/ttyACM0', serial=serial)
            self.assertEqual(result, (4, probe.NOTICE + '\n' + probe.prompt(DEVICE.device) + '\n' + probe.FAILED + '\n', ''))
            self.assertEqual(factory, 1)
            self.assertLessEqual(len(serial.packets), 122)
            if failure not in ('open', 'close'):
                self.assertEqual(serial.events, ['open', 'close'])

    def test_corrupt_fixture_prevents_inventory_and_child(self):
        with patch.object(probe, 'load_fixture', side_effect=ValueError('private')):
            for args in (['--run'], ['--self-test']):
                result, serial, inventory, factory = self.invoke(args)
                self.assertEqual(result, (4, probe.FAILED + '\n', ''))
                self.assertEqual((inventory, factory, serial.events), (0, 0, []))

    def test_nonlinux_and_interrupt_are_closed(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(probe.sys, 'platform', 'win32'), \
                patch.object(probe, 'enumerate_devices') as inventory, \
                patch.object(probe, 'serial_factory') as factory, \
                redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(probe.main(['--run']), 4)
        self.assertEqual((out.getvalue(), err.getvalue()), (probe.FAILED + '\n', ''))
        inventory.assert_not_called()
        factory.assert_not_called()
        out = io.StringIO()
        with patch.object(probe, 'enumerate_devices', return_value=(DEVICE,)), \
                patch.object(probe.sys, 'platform', 'linux'), \
                patch.object(probe, 'supervise') as child, redirect_stdout(out):
            self.assertEqual(probe.main(['--run'], read=lambda: (_ for _ in ()).throw(KeyboardInterrupt())), 1)
        child.assert_not_called()
        self.assertEqual(out.getvalue(), probe.NOTICE + '\n' + probe.prompt(DEVICE.device) + '\n' + probe.CANCELLED + '\n')

    def test_frame_deadline_stops_before_first_write(self):
        with patch.object(probe, 'FRAME_SECONDS', 0):
            result, serial, _, factory = self.invoke(['--run'], 'SEND /dev/ttyACM0')
        self.assertEqual(result, (4, probe.NOTICE + '\n' + probe.prompt(DEVICE.device) + '\n' + probe.FAILED + '\n', ''))
        self.assertEqual((factory, serial.events, serial.packets), (1, ['open', 'close'], []))

    def test_nonlinux_discovery_has_commands_without_skips(self):
        def flatten(suite):
            for item in suite:
                if isinstance(item, unittest.TestSuite):
                    yield from flatten(item)
                else:
                    yield item
        with patch.object(sys, 'platform', 'win32'):
            suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
        cases = list(flatten(suite))
        self.assertEqual(len(cases), len(unittest.TestLoader().getTestCaseNames(Commands)))
        self.assertTrue(all(type(case) is Commands for case in cases))
        self.assertFalse(any(getattr(case, '__unittest_skip__', False) for case in cases))

    def test_fake_cancellation_cases_are_platform_independent(self):
        result = unittest.TestResult()
        with patch.object(sys, 'platform', 'win32'):
            Commands('test_cancel_eof_and_wrong_confirmation_never_open').run(result)
            Commands('test_nonlinux_and_interrupt_are_closed').run(result)
        self.assertEqual((result.testsRun, result.failures, result.errors, result.skipped),
                         (2, [], [], []))

    def test_public_subprocess_safe_commands(self):
        for args, code, message in [(['--help'], 0, probe.HELP), (['--self-test'], 0, probe.SELFTEST),
                                     (['--port', '/dev/ttyACM0'], 2, probe.INVALID)]:
            result = subprocess.run([sys.executable, '-B', '-m', 'mars_display.linux_usb_measurement', *args],
                                    input='', capture_output=True, text=True, timeout=3)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (code, message + '\n', ''))


class Ownership(unittest.TestCase):
    def test_real_child_success_failure_and_timeout_are_reaped(self):
        real_fork = os.fork
        children = []
        def fork():
            pid = real_fork()
            if pid:
                children.append(pid)
            return pid
        for behavior in ('success', 'error', 'timeout'):
            def measure(port):
                if behavior == 'error':
                    raise RuntimeError('private')
                if behavior == 'timeout':
                    time.sleep(10)
                return {stage: 0.0 for stage in probe.STAGES}
            with patch.object(probe, 'measure', side_effect=measure), \
                    patch.object(probe.os, 'fork', side_effect=fork), \
                    patch.object(probe, 'TOTAL_SECONDS', 0.15):
                result = probe.supervise(DEVICE.device)
            self.assertEqual(result, {stage: 0.0 for stage in probe.STAGES} if behavior == 'success' else None)
            with self.assertRaises(ChildProcessError):
                os.waitpid(children[-1], os.WNOHANG)

    def test_corrupt_child_payload_and_eof_are_rejected_and_reaped(self):
        import json
        good = json.dumps(dict.fromkeys(probe.STAGES, 0.0)).encode()
        payloads = [b'', b'{}', good + b' ', good + good, b'x' * 2049,
                    good.replace(b'0.0', b'NaN', 1), good.replace(b'0.0', b'-1', 1),
                    good.replace(b'0.0', b'true', 1), good.replace(b'"open": 0.0', b'"open": 0.0, "open": 0.0')]
        for payload in payloads:
            children = []
            real_fork = os.fork
            def fork():
                pid = real_fork()
                if pid:
                    children.append(pid)
                return pid
            def child(fd, parent, port):
                os.write(fd, payload)
                os._exit(0)
            with patch.object(probe, 'child_main', side_effect=child), \
                    patch.object(probe.os, 'fork', side_effect=fork):
                self.assertIsNone(probe.supervise(DEVICE.device))
            with self.assertRaises(ChildProcessError):
                os.waitpid(children[0], os.WNOHANG)

    def test_interrupt_reaps_even_when_cleanup_output_breaks(self):
        real_wait = os.waitpid
        children = []
        calls = 0
        def wait(pid, flags):
            nonlocal calls
            children.append(pid)
            calls += 1
            if calls in (1, 2):
                raise KeyboardInterrupt()
            if calls == 3:
                return (0, 0)
            return real_wait(pid, flags)
        with patch.object(probe, 'measure', side_effect=lambda port: time.sleep(10)), \
                patch.object(probe.os, 'waitpid', side_effect=wait), \
                patch('builtins.print', side_effect=BrokenPipeError()):
            self.assertIsNone(probe.supervise(DEVICE.device))
        with self.assertRaises(ChildProcessError):
            real_wait(children[0], os.WNOHANG)

    def test_fork_failure_closes_both_pipe_descriptors(self):
        real_pipe = os.pipe
        fds = []
        def pipe():
            pair = real_pipe()
            fds.extend(pair)
            return pair
        with patch.object(probe.os, 'pipe', side_effect=pipe), \
                patch.object(probe.os, 'fork', side_effect=OSError('private')):
            self.assertIsNone(probe.supervise(DEVICE.device))
        for fd in fds:
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_sigint_after_kernel_reap_never_signals_stale_pid(self):
        real_wait, real_kill = os.waitpid, os.kill
        for cleanup in (False, True):
            with self.subTest(cleanup=cleanup):
                reaped, stale_signals, errors = [], [], []
                def wait(pid, flags):
                    answer = real_wait(pid, flags)
                    if answer[0] == pid:
                        reaped.append(pid)
                        # Real SIGINT arrives before the wrapper returns its result.
                        real_kill(os.getpid(), signal.SIGINT)
                    return answer
                def kill(pid, sig):
                    if pid in reaped:
                        stale_signals.append((pid, sig))
                        return  # Never actually signal a potentially reused PID.
                    return real_kill(pid, sig)
                with patch.object(probe.os, 'waitpid', side_effect=wait), \
                        patch.object(probe.os, 'kill', side_effect=kill), \
                        patch.object(probe, 'measure', return_value=dict.fromkeys(probe.STAGES, 0.0)), \
                        patch.object(probe, 'TOTAL_SECONDS', 0 if cleanup else 2), \
                        redirect_stdout(io.StringIO()):
                    try:
                        result = probe.supervise(DEVICE.device)
                    except BaseException as error:
                        errors.append(type(error).__name__)
                self.assertEqual(stale_signals, [])
                self.assertEqual(errors, [])
                self.assertIsNone(result)
                self.assertEqual(len(reaped), 1)
                with self.assertRaises(ChildProcessError):
                    real_wait(reaped[0], os.WNOHANG)

    def test_wrong_parent_fails_before_measurement(self):
        self.assertRaises(RuntimeError, probe.arm_parent_death, -1)


def load_tests(loader, tests, pattern):
    """Windows runs portable command contracts without adding skipped tests."""
    suite = loader.loadTestsFromTestCase(Commands)
    if sys.platform == 'linux':
        suite.addTests(loader.loadTestsFromTestCase(Ownership))
    return suite


if __name__ == '__main__':
    unittest.main()
