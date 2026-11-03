"""Portable recipe/CLI checks, not evidence of a working frozen artifact."""
import contextlib
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'packaging/linux/MarsDisplay.spec'
SMOKE = ROOT / 'packaging/linux/smoke.py'


class FrozenPackagingTests(unittest.TestCase):
    def test_wrong_host_and_arch_stop_before_analysis(self):
        for host, arch in [('win32', 'AMD64'), ('linux', 'aarch64')]:
            analysis = Mock()
            with patch.object(sys, 'platform', host), patch('platform.machine', return_value=arch):
                with self.assertRaisesRegex(SystemExit, 'Linux x86_64 builder required'):
                    runpy.run_path(str(SPEC), init_globals={'Analysis': analysis})
            analysis.assert_not_called()

    def test_recipe_uses_early_hook_and_standard_collection(self):
        calls = {}
        analysis = Mock(pure=[], scripts=[], binaries=[], datas=[])
        def analyze(*args, **kwargs):
            calls.update(kwargs)
            return analysis
        collect = Mock()
        with patch.object(sys, 'platform', 'linux'), patch('platform.machine', return_value='x86_64'):
            runpy.run_path(str(SPEC), init_globals={
                'SPECPATH': str(SPEC.parent), 'Analysis': analyze,
                'PYZ': Mock(), 'EXE': Mock(), 'COLLECT': collect})
        self.assertEqual(calls['runtime_hooks'], [str(SPEC.parent / 'usb_bootstrap.py')])
        self.assertIn('mars_display.linux_usb_worker', calls['hiddenimports'])
        self.assertEqual(collect.call_args.kwargs['upx'], False)
        self.assertNotIn('collect_all', SPEC.read_text())

    def test_normal_entry_calls_app_main(self):
        import types
        app = types.ModuleType('mars_display.app')
        app.main = Mock(return_value=0)
        with patch.dict(sys.modules, {'mars_display.app': app}):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(str(SPEC.parent / 'entrypoint.py'), run_name='__main__')
        self.assertEqual(raised.exception.code, 0)
        app.main.assert_called_once_with()

    def test_smoke_import_and_help_are_passive(self):
        with patch('subprocess.Popen', side_effect=AssertionError('spawn')):
            runpy.run_path(str(SMOKE), run_name='passive_import')
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', str(SMOKE), '--help'],
                                    cwd=directory, capture_output=True, timeout=3)
            self.assertEqual((result.returncode, result.stderr), (0, b''))
            self.assertIn(b'production onedir directory', result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_smoke_requires_explicit_target(self):
        with contextlib.redirect_stderr(io.StringIO()), patch.object(sys, 'argv', [str(SMOKE)]):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(str(SMOKE), run_name='__main__')
        self.assertEqual(raised.exception.code, 2)


class LinuxSmokeTests(unittest.TestCase):
    def test_source_hook_exercises_runner_without_devices(self):
        # Qualifies the runner against the real source admission/IPC only.
        # The parent must repeat it with the actual frozen production binary.
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'MarsDisplay'
            executable.write_text(f'#!{sys.executable}\nimport runpy\n'
                f'runpy.run_path({str(SPEC.parent / "usb_bootstrap.py")!r})\n'
                'raise SystemExit(99)\n')
            executable.chmod(0o700)
            result = subprocess.run([sys.executable, '-B', str(SMOKE),
                                     '--appdir', directory], capture_output=True, timeout=50,
                env={**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'})
            self.assertEqual((result.returncode, result.stderr), (0, b''))
            self.assertEqual(result.stdout,
                b'PASS: private CLI, admission, no-USB protocol, rejection and reap\n')
            self.assertEqual(list(Path(directory).iterdir()), [executable])


def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromTestCase(FrozenPackagingTests)
    if sys.platform == 'linux':
        suite.addTests(loader.loadTestsFromTestCase(LinuxSmokeTests))
    return suite
