"""Exercise Linux CI scripts without loading profiles or launching a real browser."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).parents[1]
PROFILE_STEP = 'Configure scoped Chromium sandbox admission'
SMOKE_STEP = 'Verify sandboxed Chromium startup'


def script_for(name):
    text = (ROOT / '.github/workflows/linux-appimage.yml').read_text()
    marker = f'      - name: {name}\n'
    if marker not in text:
        raise AssertionError(f'Missing workflow step: {name}')
    step = text.split(marker, 1)[1].split('      - name:', 1)[0]
    block = '\n'.join(line[10:] for line in step.split('        run: |\n', 1)[1].splitlines())
    prefix = "python - <<'PY'\n"
    assert block.startswith(prefix) and block.endswith('\nPY')
    return block[len(prefix):-3]


def profile_namespace():
    namespace = {'__name__': 'workflow_profile_test'}
    exec(compile(script_for(PROFILE_STEP), '<workflow-profile>', 'exec'), namespace)
    return namespace


class LinuxCISandboxTests(unittest.TestCase):
    def browsers(self, root):
        paths = [root / 'chromium-1248/chrome-linux64/chrome',
                 root / 'chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell']
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
            path.chmod(0o755)
        return paths

    def test_workflow_orders_admission_and_preflight_before_tests(self):
        text = (ROOT / '.github/workflows/linux-appimage.yml').read_text()
        stages = ['Install source test runtime', PROFILE_STEP, SMOKE_STEP,
                  'Source tests (offscreen, not desktop acceptance)',
                  'Build and validate versioned AppImage assets']
        for stage in stages:
            self.assertIn(f'      - name: {stage}\n', text)
        self.assertEqual([text.index(stage) for stage in stages],
                         sorted(text.index(stage) for stage in stages))
        for name in (PROFILE_STEP, SMOKE_STEP):
            step = text.split(f'      - name: {name}\n', 1)[1].split('      - name:', 1)[0]
            self.assertIn("          PLAYWRIGHT_BROWSERS_PATH: '0'", step)
        for forbidden in ('--no-sandbox', 'chromium_sandbox=False', 'sysctl -w',
                          'continue-on-error', 'service apparmor', 'systemctl stop'):
            self.assertNotIn(forbidden, text)

    def test_profiles_attach_only_exact_installed_executables(self):
        ns = profile_namespace()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'browsers'
            paths = self.browsers(root)
            destination = Path(folder) / 'profile'
            with mock.patch.object(subprocess, 'run') as run, redirect_stdout(io.StringIO()):
                ns['configure'](root, destination, '1')
            expected = 'abi <abi/4.0>,\n'
            for index, path in enumerate(paths):
                expected += f'profile marsdisplay-ci-{index} "{path}" flags=(unconfined) {{\n  userns,\n}}\n'
            self.assertEqual(destination.read_text(), expected)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            run.assert_called_once_with(
                ['sudo', 'apparmor_parser', '--replace', str(destination)], check=True)

    def test_unrestricted_runner_never_loads_or_writes_profiles(self):
        ns = profile_namespace()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'browsers'
            self.browsers(root)
            destination = Path(folder) / 'profile'
            for restriction in ('0', 'absent'):
                with self.subTest(restriction=restriction), mock.patch.object(subprocess, 'run') as run, redirect_stdout(io.StringIO()):
                    ns['configure'](root, destination, restriction)
                    run.assert_not_called()
                    self.assertFalse(destination.exists())

    def test_unsafe_discovery_fails_before_policy_write_or_load(self):
        ns = profile_namespace()
        for case in ('missing', 'ambiguous', 'escape', 'unsafe', 'nonexecutable', 'unknown-policy'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                root = Path(folder) / ('unsafe*root' if case == 'unsafe' else 'browsers')
                paths = self.browsers(root)
                if case == 'missing':
                    paths[1].unlink()
                elif case == 'ambiguous':
                    extra = root / 'chromium-9999/chrome-linux64/chrome'
                    extra.parent.mkdir(parents=True)
                    extra.write_bytes(b'other')
                    extra.chmod(0o755)
                elif case == 'escape':
                    outside = Path(folder) / 'chrome'
                    outside.write_bytes(b'outside')
                    outside.chmod(0o755)
                    paths[0].unlink()
                    paths[0].symlink_to(outside)
                elif case == 'nonexecutable':
                    paths[0].chmod(0o600)
                destination = Path(folder) / 'profile'
                with mock.patch.object(subprocess, 'run') as run, redirect_stdout(io.StringIO()):
                    with self.assertRaises((RuntimeError, FileNotFoundError)):
                        ns['configure'](root, destination, 'unexpected' if case == 'unknown-policy' else '1')
                    run.assert_not_called()
                    self.assertFalse(destination.exists())

    def test_profile_loader_failure_propagates(self):
        ns = profile_namespace()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'browsers'
            self.browsers(root)
            with mock.patch.object(subprocess, 'run', side_effect=subprocess.CalledProcessError(7, 'parser')) as run, redirect_stdout(io.StringIO()):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    ns['configure'](root, Path(folder) / 'profile', '1')
                self.assertEqual(error.exception.returncode, 7)
                self.assertEqual(run.call_count, 1)

    def smoke(self, driver):
        module = types.ModuleType('playwright.sync_api')
        module.sync_playwright = mock.MagicMock()
        module.sync_playwright.return_value.__enter__.return_value = driver
        with mock.patch.dict(sys.modules, {'playwright.sync_api': module}), mock.patch.object(os, 'geteuid', return_value=1000), mock.patch.dict(os.environ, {'PLAYWRIGHT_BROWSERS_PATH': '0'}), redirect_stdout(io.StringIO()):
            exec(compile(script_for(SMOKE_STEP), '<workflow-smoke>', 'exec'), {})

    def test_preflight_launches_both_browsers_with_sandbox_and_closes(self):
        driver = mock.MagicMock()
        browsers = [mock.MagicMock(), mock.MagicMock()]
        for browser in browsers:
            browser.new_page.return_value.screenshot.return_value = b'\x89PNG\r\n\x1a\nfixture'
        driver.chromium.launch.side_effect = browsers
        self.smoke(driver)
        self.assertEqual(driver.chromium.launch.call_args_list, [
            mock.call(headless=True, chromium_sandbox=True, timeout=15000),
            mock.call(headless=True, chromium_sandbox=True, timeout=15000, channel='chromium')])
        for browser in browsers:
            browser.new_page.return_value.set_content.assert_called_once()
            browser.new_page.return_value.screenshot.assert_called_once_with()
            browser.close.assert_called_once_with()

    def test_preflight_failure_has_no_unsandboxed_fallback(self):
        driver = mock.MagicMock()
        driver.chromium.launch.side_effect = RuntimeError('sandbox denied')
        with self.assertRaisesRegex(RuntimeError, 'sandbox denied'):
            self.smoke(driver)
        driver.chromium.launch.assert_called_once_with(
            headless=True, chromium_sandbox=True, timeout=15000)
        driver = mock.MagicMock()
        browser = driver.chromium.launch.return_value
        browser.new_page.return_value.screenshot.side_effect = RuntimeError('capture failed')
        with self.assertRaisesRegex(RuntimeError, 'capture failed'):
            self.smoke(driver)
        browser.close.assert_called_once_with()
        self.assertEqual(driver.chromium.launch.call_count, 1)

    def test_entrypoint_guards(self):
        for step, label in ((PROFILE_STEP, 'preparation'), (SMOKE_STEP, 'preflight')):
            for uid, value in ((0, '0'), (1000, '1'), (1000, '')):
                with self.subTest(step=step, uid=uid, value=value):
                    with mock.patch.object(os, 'geteuid', return_value=uid), \
                         mock.patch.dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=value), \
                         mock.patch.object(subprocess, 'run') as run:
                        with self.assertRaises(RuntimeError) as error:
                            exec(script_for(step), {'__name__': '__main__'})
                        self.assertEqual(str(error.exception),
                                         f'Sandbox {label} requires the unprivileged runner '
                                         'and package-local browsers.')
                        run.assert_not_called()

    def test_existing_policy_and_nonregular_browser_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder, \
             mock.patch.object(subprocess, 'run') as run, redirect_stdout(io.StringIO()):
            root = Path(folder) / 'browsers'
            paths = self.browsers(root)
            destination = Path(folder) / 'profile'
            destination.write_bytes(b'preexisting policy\n')
            before = hashlib.sha256(destination.read_bytes()).digest()
            with self.assertRaises(FileExistsError):
                profile_namespace()['configure'](root, destination, '1')
            self.assertEqual(hashlib.sha256(destination.read_bytes()).digest(), before)
            paths[1].unlink()
            paths[1].mkdir()
            with self.assertRaises(RuntimeError) as error:
                profile_namespace()['configure'](root, destination, '1')
            self.assertEqual(str(error.exception), 'Unsafe or non-executable browser attachment path.')
            self.assertEqual(hashlib.sha256(destination.read_bytes()).digest(), before)
            run.assert_not_called()

    def test_invalid_png_closes_and_stops(self):
        driver = mock.MagicMock()
        browser = driver.chromium.launch.return_value
        browser.new_page.return_value.screenshot.return_value = b'not PNG'
        with self.assertRaises(RuntimeError) as error:
            self.smoke(driver)
        self.assertEqual(str(error.exception), 'Sandbox preflight did not produce a PNG capture.')
        browser.close.assert_called_once_with()
        self.assertEqual(driver.chromium.launch.call_count, 1)

    def test_second_launch_failure_propagates(self):
        driver, browser = mock.MagicMock(), mock.MagicMock()
        browser.new_page.return_value.screenshot.return_value = b'\x89PNG\r\n\x1a\n'
        driver.chromium.launch.side_effect = [browser, RuntimeError('second sandbox denied')]
        with self.assertRaisesRegex(RuntimeError, '^second sandbox denied$'):
            self.smoke(driver)
        browser.close.assert_called_once_with()
        self.assertEqual(driver.chromium.launch.call_args_list, [
            mock.call(headless=True, chromium_sandbox=True, timeout=15000),
            mock.call(headless=True, chromium_sandbox=True, timeout=15000, channel='chromium')])


def load_tests(loader, standard_tests, pattern):
    return standard_tests if sys.platform == 'linux' else unittest.TestSuite()
