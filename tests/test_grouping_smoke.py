"""Source bootstrap checks; real Windows checks run in the native build."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

from mars_display.usb_grouping_experiment import HELP, INVALID, SELFTEST

ROOT = Path(__file__).resolve().parents[1]


class EntryTests(unittest.TestCase):
    def test_console_public_routes_have_exact_streams_and_exits(self):
        for args, code, text in (([], 0, HELP), (['--help'], 0, HELP),
                                 (['--self-test'], 0, SELFTEST), (['--invalid'], 2, INVALID)):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, '-B', str(ROOT / 'packaging/grouping_entrypoint.py'), *args],
                    capture_output=True, timeout=5, env=os.environ.copy())
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (code, (text + '\n').replace('\n', '\r\n' if os.name == 'nt' else '\n').encode(), b''))

    def test_both_private_names_are_silently_rejected_before_qt_or_settings(self):
        script = '''import runpy, sys
class Deny:
    def find_spec(self, fullname, *args):
        if fullname.startswith(('PySide6', 'mars_display.settings', 'mars_display.app')):
            raise AssertionError('forbidden import: ' + fullname)
sys.meta_path.insert(0, Deny())
sys.argv = ['entry', *sys.argv[1:]]
sys.path.insert(0, 'packaging')
runpy.run_path('packaging/grouping_entrypoint.py', run_name='__main__')
'''
        for args in (['--usb-worker'], ['--usb-worker=bad'], ['--grouping-worker'],
                     ['--grouping-worker=bad'], ['--grouping-worker', 'A', 'COM5', '0', 'a'*64]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, '-B', '-c', script, *args],
                    cwd=ROOT, capture_output=True, timeout=5)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (2, b'', b''))


class QualificationTests(unittest.TestCase):
    def test_no_device_check_routes_both_arms_and_rejects_bad_stdout(self):
        import tempfile
        from unittest.mock import Mock, patch
        from test_packaging_payload import load
        module = load('grouping_smoke')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'MarsDisplayGroupingExperiment.exe').write_bytes(b'SYNTHETIC')
            def reply(command, **kwargs):
                self.assertNotIn('--run', command)
                args = command[1:]
                text = HELP if args in ([], ['--help']) else SELFTEST if args == ['--self-test'] else INVALID if args == ['--invalid'] else None
                return subprocess.CompletedProcess(command, 0 if args in ([], ['--help'], ['--self-test']) else 2,
                    b'' if text is None else (text + '\n').replace('\n', '\r\n').encode(), b'')
            exchange, held, death = Mock(), Mock(), Mock()
            with patch.object(module.shared, 'require_host'), patch.object(module.shared, '_environment', return_value={}), patch.object(module.subprocess, 'run', side_effect=reply) as run, patch.object(module, 'exchange', exchange), patch.object(module, 'held_gate', held), patch.object(module, 'parent_death', death):
                result = module.check(root, root / 'scratch')
                self.assertEqual(result['status'], 'passed')
                self.assertEqual(exchange.call_count, 4)
                self.assertEqual([call.args[2] for call in exchange.call_args_list], ['A', 'A', 'B', 'B'])
                held.assert_called_once()
                death.assert_called_once()
                self.assertEqual(run.call_count, 10)  # Includes a valid invocation without an admission event.
                def wrong_endings(*args, **kwargs):
                    response = reply(*args, **kwargs)
                    response.stdout = response.stdout.replace(b'\r\n', b'\n')
                    return response
                run.side_effect = wrong_endings
                with self.assertRaisesRegex(RuntimeError, 'streams/exit'):
                    module.check(root, root / 'wrong-line-endings')
                run.side_effect = lambda *a, **k: subprocess.CompletedProcess([], 0, b'wrong', b'')
                with self.assertRaisesRegex(RuntimeError, 'streams/exit'):
                    module.check(root, root / 'other')

    def test_native_host_rejection_precedes_output(self):
        from unittest.mock import patch
        from test_packaging_payload import load
        module = load('grouping_smoke')
        with patch.object(module.shared, 'require_host', side_effect=RuntimeError('native required')), patch.object(module.shared, '_environment', side_effect=AssertionError('output')):
            with self.assertRaisesRegex(RuntimeError, 'native required'):
                module.check(Path('missing'), Path('missing-scratch'))
