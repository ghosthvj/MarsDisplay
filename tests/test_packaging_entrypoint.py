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
