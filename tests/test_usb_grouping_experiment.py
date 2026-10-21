"""Console policy through the public entry point; never real USB."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mars_display import usb_grouping_experiment as experiment
from mars_display import usb_grouping_profile as profile
import test_usb_worker as session


class Guard:
    def __init__(self, events, acquired=True):
        self.events, self.acquired = events, acquired
    def acquire(self):
        self.events.append('lock')
        return self.acquired
    def release(self):
        self.events.append('unlock')


class ConsoleTests(unittest.TestCase):
    def invoke(self, args, answers=(), *, failure=None, acquired=True, snapshots=None):
        events, transports = [], []
        answers = iter(answers)
        snapshots = iter(snapshots or [(session.DEVICE,)] * 4)
        def inventory():
            events.append('inventory')
            return next(snapshots)
        def read():
            events.append('input')
            try:
                return next(answers)
            except StopIteration:
                raise EOFError
        class Transport:
            owned = False
            last_send_timing = None
            def open(self):
                self.owned = True
                events.append('open')
                if failure == 'open':
                    raise RuntimeError('private detail')
            def send(self, frame):
                self.frame = frame
                events.append('send')
                if failure == 'send':
                    raise RuntimeError('private detail')
            def close(self):
                events.append('close')
                if failure == 'uncertain' and events.count('close') == 1:
                    raise RuntimeError('private detail')
                self.owned = False
                if failure == 'close':
                    raise RuntimeError('private detail')
        def transport(arm, com):
            events.append((arm, com))
            obj = Transport()
            transports.append(obj)
            return obj
        out, err = io.StringIO(), io.StringIO()
        with patch.object(experiment, 'make_guard', return_value=Guard(events, acquired)), \
                patch.object(experiment, 'enumerate_devices', inventory), \
                patch.object(experiment, 'make_transport', transport), \
                patch.object(experiment.time, 'sleep', lambda _: events.append('wait')), \
                redirect_stdout(out), redirect_stderr(err):
            code = experiment.main(args, read=read)
        return code, out.getvalue(), err.getvalue(), events, transports

    def test_help_invalid_and_selftest_are_device_and_guard_free(self):
        for args, code, text in [([], 0, experiment.HELP), (['--help'], 0, experiment.HELP),
                (['--chunk-size', '5120'], 2, experiment.INVALID),
                (['--run', '--run'], 2, experiment.INVALID),
                (['--self-test'], 0, experiment.SELFTEST)]:
            with self.subTest(args=args):
                result = self.invoke(args)
                self.assertEqual(result[:4], (code, text + '\n', '', []))

    def test_default_cancel_eof_wrong_com_and_guard_collision_never_open(self):
        for answers in ((), ('',), ('COM5',), ('A COM6',)):
            result = self.invoke(['--run'], answers)
            self.assertEqual(result[:3], (1, experiment.NOTICE + '\n' +
                experiment.prompt('A', 'COM5') + '\n' + experiment.CANCELLED + '\n', ''))
            self.assertEqual(result[3], ['lock', 'inventory', 'input', 'unlock'])
            self.assertEqual(result[4], [])
        result = self.invoke(['--run'], acquired=False)
        self.assertEqual(result[:4], (3, experiment.BUSY + '\n', '', ['lock']))

    def test_two_arms_are_once_only_and_lock_spans_visual_inspection(self):
        result = self.invoke(['--run'], ['A COM5', 'A VALID', 'B COM5'])
        self.assertEqual(result[:3], (0, experiment.NOTICE + '\n' +
            experiment.prompt('A', 'COM5') + '\n' + experiment.report('A', None) + '\n' +
            experiment.VISUAL + '\n' + experiment.prompt('B', 'COM5') + '\n' +
            experiment.report('B', None) + '\n' + experiment.DONE + '\n', ''))
        self.assertEqual(result[3], ['lock', 'inventory', 'input', ('A', 'COM5'),
            'open', 'send', 'close', 'input', 'inventory', 'input', ('B', 'COM5'),
            'open', 'send', 'close', 'unlock'])
        self.assertEqual([t.frame.rgb for t in result[4]], [session.FRAME.rgb]*2)

    def test_invalid_visual_eof_and_cancel_b_never_send_b(self):
        for answers in (['A COM5'], ['A COM5', 'no'], ['A COM5', 'A VALID'],
                        ['A COM5', 'A VALID', 'B COM6']):
            result = self.invoke(['--run'], answers)
            expected = experiment.NOTICE + '\n' + experiment.prompt('A', 'COM5') + '\n'
            expected += experiment.report('A', None) + '\n' + experiment.VISUAL + '\n'
            if len(answers) > 1 and answers[1] == 'A VALID':
                expected += experiment.prompt('B', 'COM5') + '\n'
            self.assertEqual(result[:3], (1, expected + experiment.CANCELLED + '\n', ''))
            self.assertEqual(result[3].count('send'), 1)
            self.assertEqual(len(result[4]), 1)
            self.assertEqual(result[3][-1], 'unlock')

    def test_any_arm_a_error_or_uncertainty_latches_no_b(self):
        for failure in ('open', 'send', 'close', 'uncertain'):
            result = self.invoke(['--run'], ['A COM5', 'A VALID', 'B COM5'], failure=failure)
            text = experiment.NOTICE + '\n' + experiment.prompt('A', 'COM5') + '\n'
            text += experiment.FAILED + '\n'
            if failure == 'uncertain':
                text += experiment.CLEANUP + '\n'
            self.assertEqual(result[:3], (4, text, ''))
            self.assertEqual(len(result[4]), 1)
            self.assertEqual(result[3].count('input'), 1)
            self.assertEqual(result[3][-1], 'unlock')
            self.assertFalse(result[4][0].owned)
            if failure == 'uncertain':
                self.assertEqual(result[3][-4:], ['close', 'wait', 'close', 'unlock'])

    def test_inventory_failure_and_duplicate_reject_and_b_resolves_fresh_com(self):
        for snapshot in ((), (session.DEVICE, session.DEVICE),
                (session.DEVICE, replace(session.DEVICE, serial_number='other'))):
            result = self.invoke(['--run'], ['A COM5'], snapshots=[snapshot])
            self.assertEqual(result[:3], (4, experiment.NOTICE + '\n' + experiment.FAILED + '\n', ''))
            self.assertEqual(result[3], ['lock', 'inventory', 'unlock'])
            self.assertEqual(result[4], [])
        result = self.invoke(['--run'], ['A COM5', 'A VALID', 'B COM6'],
            snapshots=[(session.DEVICE,), (replace(session.DEVICE, device='COM6'),)])
        self.assertEqual(result[0], 0)
        self.assertIn(('B', 'COM6'), result[3])

    def test_corrupt_fixture_rejects_before_guard_inventory_and_open(self):
        with patch.object(profile.Path, 'read_bytes', return_value=b'private'):
            for args in (['--run'], ['--self-test']):
                result = self.invoke(args)
                self.assertEqual(result[:4], (4, experiment.FAILED + '\n', '', []))

    def test_real_app_guard_collision_and_eof_release_without_settings_io(self):
        from mars_display.settings import SettingsStore
        from mars_display.tray import SingleInstanceGuard
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'LOCALAPPDATA': root}), \
                patch.object(SettingsStore, 'load', side_effect=AssertionError('settings read')), \
                patch.object(SettingsStore, 'save', side_effect=AssertionError('settings write')):
            app_guard = SingleInstanceGuard(SettingsStore())
            self.assertTrue(app_guard.acquire())
            try:
                out = io.StringIO()
                with redirect_stdout(out), patch.object(experiment, 'enumerate_devices') as inventory:
                    self.assertEqual(experiment.main(['--run']), 3)
                    inventory.assert_not_called()
                self.assertEqual(out.getvalue(), experiment.BUSY + '\n')
            finally:
                app_guard.release()
            def eof():
                competitor = SingleInstanceGuard(SettingsStore())
                self.assertFalse(competitor.acquire())
                raise EOFError
            with redirect_stdout(io.StringIO()), patch.object(experiment, 'enumerate_devices',
                    return_value=(session.DEVICE,)):
                self.assertEqual(experiment.main(['--run'], read=eof), 1)
            self.assertTrue(app_guard.acquire())
            app_guard.release()
            self.assertEqual(list(Path(root).rglob('*')), [Path(root) / 'MarsDisplay'])

    def test_source_cli_no_device_routes_start_without_gui_or_settings(self):
        script = '''import sys
from mars_display.usb_grouping_experiment import main
code = main(sys.argv[1:])
assert not any(n in sys.modules for n in ('mars_display.settings', 'mars_display.app', 'PySide6.QtCore', 'PySide6.QtWidgets'))
raise SystemExit(code)
'''
        for args, code, text in [([], 0, experiment.HELP), (['--self-test'], 0, experiment.SELFTEST),
                                 (['--profile', 'B'], 2, experiment.INVALID)]:
            result = subprocess.run([sys.executable, '-B', '-c', script, *args],
                input='', capture_output=True, text=True, timeout=3)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (code, text+'\n', ''))

    def test_broken_console_cannot_abandon_owned_cleanup(self):
        real_print = print
        def failing_notice(*args, **kwargs):
            if args == (experiment.CLEANUP,):
                raise BrokenPipeError('private console detail')
            return real_print(*args, **kwargs)
        with patch('builtins.print', failing_notice):
            result = self.invoke(['--run'], ['A COM5', 'A VALID', 'B COM5'], failure='uncertain')
        text = experiment.NOTICE + '\n' + experiment.prompt('A', 'COM5') + '\n' + experiment.FAILED + '\n'
        self.assertEqual(result[:3], (4, text, ''))
        self.assertEqual(result[3][-4:], ['close', 'wait', 'close', 'unlock'])
        self.assertEqual(len(result[4]), 1)
        self.assertFalse(result[4][0].owned)

    def test_source_and_frozen_private_vectors_and_no_normal_route(self):
        args = ['--grouping-worker', 'B', 'COM5', '12345', 'a'*64]
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(experiment.worker_command('B', 'COM5', 12345, 'a'*64),
                [sys.executable, '-m', 'mars_display.usb_grouping_worker', *args])
        with patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(experiment.worker_command('B', 'COM5', 12345, 'a'*64),
                [sys.executable, *args])
        with patch.object(experiment.subprocess, 'Popen') as spawn, \
                patch.object(experiment, 'UsbTransport') as transport:
            experiment.make_transport('B', 'COM5')
            self.assertEqual(transport.call_args.args, (session.worker.IDENTITY,))
            transport.call_args.kwargs['launcher'](12345, 'a'*64)
            self.assertEqual(spawn.call_args.args[0][-5:], args)
            self.assertFalse(spawn.call_args.kwargs['shell'])
            self.assertTrue(spawn.call_args.kwargs['close_fds'])
            for stream in ('stdin', 'stdout', 'stderr'):
                self.assertEqual(spawn.call_args.kwargs[stream], subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()
