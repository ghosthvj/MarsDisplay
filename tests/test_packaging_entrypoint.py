import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


def load_entry():
    spec = importlib.util.spec_from_file_location('portable_entry', Path('packaging/entrypoint.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EntrypointTests(unittest.TestCase):
    def test_custom_runtime_hook_private_exit_precedes_later_hooks(self):
        for error in (False, True):
            with self.subTest(error=error), patch.object(sys, 'argv', ['MarsDisplay.exe', '--usb-worker']), patch.object(sys, 'stdout', None), patch.object(sys, 'stderr', None), patch('mars_display.usb_worker.main', side_effect=RuntimeError('private') if error else None, return_value=0) as worker:
                spec=importlib.util.spec_from_file_location('p3_early_hook', Path('packaging/usb_bootstrap.py'))
                hook=importlib.util.module_from_spec(spec)
                with self.assertRaises(SystemExit) as exit:
                    spec.loader.exec_module(hook)
                self.assertEqual(exit.exception.code, 2 if error else 0)
                worker.assert_called_once_with(['--usb-worker'])
                self.assertIsNone(sys.stdout); self.assertIsNone(sys.stderr)

    def test_custom_runtime_hook_ordinary_arguments_are_noop(self):
        with patch.object(sys, 'argv', ['MarsDisplay.exe', '--ordinary-unknown']), patch('mars_display.usb_worker.main') as worker:
            spec=importlib.util.spec_from_file_location('p3_normal_hook', Path('packaging/usb_bootstrap.py'))
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
            worker.assert_not_called()

    def test_worker_prefix_routes_before_app_reporting_with_none_streams(self):
        entry = load_entry()
        for args in (['--usb-worker'], ['--usb-worker=invalid']):
            main, report = Mock(return_value=7), Mock()
            with self.subTest(args=args), patch.object(sys, 'argv', ['MarsDisplay.exe', *args]), \
                 patch('mars_display.usb_worker.main', return_value=2) as worker, \
                 patch.object(sys, 'stdout', None), patch.object(sys, 'stderr', None):
                self.assertEqual(entry.run(main, report), 2)
                worker.assert_called_once_with(args)
                main.assert_not_called(); report.assert_not_called()
                self.assertIsNone(sys.stdout); self.assertIsNone(sys.stderr)

    def test_worker_failure_is_quiet_without_app_or_native_dialog(self):
        entry = load_entry(); main, report = Mock(), Mock()
        with patch.object(sys, 'argv', ['MarsDisplay.exe', '--usb-worker']), \
             patch('mars_display.usb_worker.main', side_effect=RuntimeError('private token')):
            self.assertEqual(entry.run(main, report), 2)
        main.assert_not_called(); report.assert_not_called()

    def test_ordinary_unknown_option_preserves_app_startup(self):
        entry = load_entry(); report = Mock()
        with patch.object(sys, 'argv', ['MarsDisplay.exe', '--ordinary-unknown']), \
             patch('mars_display.usb_worker.main') as worker:
            self.assertEqual(entry.run(lambda: 7, report), 7)
        worker.assert_not_called(); report.assert_not_called()

    def test_none_streams_sanitized_reports_codes_and_restore(self):
        entry = load_entry()
        for message, code in [('MarsDisplay is already running.', 0),
                              ('Cannot start MarsDisplay; check the interactive system tray and settings directory access.', 1)]:
            with self.subTest(message=message), patch.object(sys, 'stdout', None), patch.object(sys, 'stderr', None):
                report = Mock()
                def main():
                    self.assertIsNotNone(sys.stdout)
                    print(message, file=sys.stderr)
                    return code
                self.assertEqual(entry.run(main, report), code)
                report.assert_called_once_with(message, code != 0)
                self.assertIsNone(sys.stdout)
                self.assertIsNone(sys.stderr)

    def test_unexpected_and_import_errors_are_generic(self):
        entry = load_entry()
        for main in [Mock(side_effect=RuntimeError('https://secret/?token=private')), None]:
            report = Mock()
            before = sys.stdout, sys.stderr
            with patch('builtins.__import__', side_effect=ImportError('private')) if main is None else patch.object(entry, 'SAFE_FAILURE', entry.SAFE_FAILURE):
                self.assertEqual(entry.run(main, report), 1)
            report.assert_called_once_with(entry.SAFE_FAILURE, True)
            self.assertEqual((sys.stdout, sys.stderr), before)

    def test_silent_success_manual_streams_and_native_report(self):
        entry = load_entry()
        before = sys.stdout, sys.stderr
        report = Mock()
        self.assertEqual(entry.run(lambda: 7, report), 7)
        report.assert_not_called()
        self.assertEqual((sys.stdout, sys.stderr), before)
        native = Mock()
        with patch.object(entry.ctypes, 'windll', native, create=True):
            entry.message_box('safe', False)
        native.user32.MessageBoxW.assert_called_once_with(None, 'safe', 'MarsDisplay', 0x40)

    def test_reporter_failure_restores_streams(self):
        entry = load_entry()
        before = sys.stdout, sys.stderr
        def main():
            print('MarsDisplay is already running.', file=sys.stderr)
            return 0
        with self.assertRaises(OSError):
            entry.run(main, Mock(side_effect=OSError('native unavailable')))
        self.assertEqual((sys.stdout, sys.stderr), before)
