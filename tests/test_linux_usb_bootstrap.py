"""Early-hook contract tests; source execution is not frozen qualification."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

HOOK = Path('packaging/linux/usb_bootstrap.py').resolve()


def load_hook():
    spec = importlib.util.spec_from_file_location('linux_early_hook', HOOK)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))


class BootstrapTests(unittest.TestCase):
    def test_exact_private_dispatch_and_quiet_failure(self):
        args = ['--linux-usb-worker', '123', 'ab' * 32, '9', '456', '789.0']
        for failure in (None, RuntimeError('private detail')):
            worker = Mock(return_value=7, side_effect=failure)
            module = types.ModuleType('mars_display.linux_usb_worker')
            module.main = worker
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(failure=failure), \
                    patch.object(sys, 'argv', ['MarsDisplay', *args]), \
                    patch.dict(sys.modules, {'mars_display.linux_usb_worker': module}), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    load_hook()
                self.assertEqual(raised.exception.code, 2 if failure else 7)
            worker.assert_called_once_with(args)
            self.assertEqual((stdout.getvalue(), stderr.getvalue()), ('', ''))

    def test_reserved_misuse_never_falls_through_or_imports_worker(self):
        cases = [['--linux-usb-worker=bad'], ['--linux-usb-worker-extra'],
                 ['--usb-worker'], ['--usb-worker=bad'], ['--usb-worker-extra'],
                 ['ordinary', '--linux-usb-worker'], ['--linux-usb-worker'],
                 ['--linux-usb-worker', '1', 'nonce', '3', '4'],
                 ['--linux-usb-worker', '1', 'nonce', '3', '4', '5', 'extra'],
                 ['--linux-usb-worker', '1', '--usb-worker', '3', '4', '5'],
                 ['--linux-usb-worker', '1', '--linux-usb-worker=bad', '3', '4', '5']]
        for args in cases:
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(args=args), patch.object(sys, 'argv', ['MarsDisplay', *args]), \
                    patch('builtins.__import__', wraps=__import__) as imports, \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    load_hook()
                self.assertEqual(raised.exception.code, 2)
                self.assertFalse(any(call.args[0].startswith('mars_display') for call in imports.call_args_list))
            self.assertEqual((stdout.getvalue(), stderr.getvalue()), ('', ''))

    def test_fresh_process_passive_normal_and_rejected_private(self):
        # The observer rejects eager GUI/settings imports and child creation.
        script = '''
import runpy, sys
from pathlib import Path
def audit(event, args):
    if event == 'import' and (args[0].startswith('PySide6') or args[0] in
            ('mars_display.app', 'mars_display.settings')):
        raise AssertionError('eager GUI import')
    if event in ('subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn'):
        raise AssertionError('child effect')
sys.addaudithook(audit)
hook = sys.argv.pop(1)
runpy.run_path(hook)
assert not any(name.startswith(('mars_display', 'PySide6')) for name in sys.modules)
'''
        cases = [([], 0), (['--help'], 0), (['--ordinary-unknown'], 0),
                 (['prefix--linux-usb-worker'], 0), (['--linux-usb'], 0),
                 (['--linux-usb-worker=bad'], 2), (['--usb-worker'], 2),
                 (['--linux-usb-worker', '123', 'ab' * 32, '99', '1', '0'], 2)]
        with tempfile.TemporaryDirectory() as directory:
            for args, code in cases:
                with self.subTest(args=args):
                    result = subprocess.run([sys.executable, '-B', '-c', script, str(HOOK), *args],
                        cwd=directory, env={**os.environ, 'PYTHONPATH': str(Path('src').resolve())},
                        capture_output=True, timeout=3)
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (code, b'', b''))
                    self.assertEqual(os.listdir(directory), [])

    def test_private_failure_with_absent_streams(self):
        with patch.object(sys, 'argv', ['MarsDisplay', '--usb-worker']), \
                patch.object(sys, 'stdout', None), patch.object(sys, 'stderr', None):
            with self.assertRaises(SystemExit) as raised:
                load_hook()
            self.assertEqual(raised.exception.code, 2)
            self.assertIsNone(sys.stdout)
            self.assertIsNone(sys.stderr)
