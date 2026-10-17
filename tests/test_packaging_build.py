"""Source/synthetic SDK checks only; never evidence of a Windows executable."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_packaging_payload import load
import test_packaging_payload as payload_fixtures


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.builder = load('build_portable')
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.repo = Path(self.temp)
        self.events = []
        self.fixture = payload_fixtures.PayloadTests()
        self.runtime = self.fixture.fixture()
        # Verified Playwright 1.64 registry and Windows PyInstaller hook paths.
        self.runtime['_internal/PySide6/plugins/platforms/qwindows.dll'] = self.runtime.pop(
            '_internal/PySide6/Qt/plugins/platforms/qwindows.dll')
        old = next(p for p in self.runtime if p.endswith('/headless_shell.exe'))
        self.runtime[old.replace('headless_shell.exe', 'chrome-headless-shell.exe')] = self.runtime.pop(old)
        self.info = self.fixture.inventory()
        self.info['version'] = '0.1.0'
        self.info['build']['Qt'] = '6.12.0'
        self.source = self.fixture.source()
        self.source['.github/workflows/windows-portable.yml'] = b'workflow source'
        self.native = Mock(return_value=([{'name': 'native fixture'}], {'native/LICENSE': b'native text'}))

    def process(self, command, **kwargs):
        self.events.append('compile')
        self.assertEqual(command[:3], [sys.executable, '-m', 'PyInstaller'])
        self.assertIn('--distpath', command)
        stage = Path(command[command.index('--distpath') + 1]) / 'MarsDisplay'
        for name, data in self.runtime.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.assertEqual(kwargs['env']['PLAYWRIGHT_BROWSERS_PATH'], '0')
        self.assertNotIn('QT_QPA_PLATFORM', kwargs['env'])
        return subprocess.CompletedProcess(command, 0)

    def execute(self, smoke_failure=False, changed_source=False, default_native=False, compile_failure=False):
        def inspect(repo):
            self.events.append('inspect')
            return dict(self.info), {'SDK/LICENSE': b'SDK text'}
        def qualify(*args):
            self.events.append('native-notices')
            return self.native(*args)
        def smoke(folder, scratch):
            self.events.append('smoke')
            self.assertTrue((folder / 'MarsDisplay.exe').is_file())
            self.assertTrue(scratch.is_relative_to(self.repo / 'build'))
            if smoke_failure:
                raise RuntimeError('synthetic startup failed')
            return {'Node': 'v24.fixture', 'Chromium': 'Chromium fixture', 'FFmpeg': 'ffmpeg fixture'}
        assemble = self.builder.payload.assemble
        def publish(*args):
            self.events.append('publish')
            return assemble(*args)
        snapshots = [self.source, self.source | {'README.md': b'changed'}] if changed_source else [self.source, self.source]
        with patch.object(self.builder, 'require_host'), patch.object(self.builder, 'inspect_environment', inspect), patch.object(self.builder.payload, 'collect_source', side_effect=snapshots), patch.object(self.builder.payload, 'assemble', publish):
            runner = Mock(side_effect=RuntimeError('synthetic compile failed')) if compile_failure else self.process
            return self.builder.build(self.repo, run=runner,
                                      qualify=None if default_native else qualify, smoke_check=smoke)

    def test_missing_native_mapping_retains_only_unqualified_measured_diagnostic(self):
        work = self.repo / 'build'; work.mkdir()
        prior_report = work / 'unqualified-native-prior.json'
        prior_report.write_bytes(b'previous diagnostic bytes')
        private = work / 'private-state/settings.json'
        private.parent.mkdir(); private.write_bytes(b'private profile bytes')
        output = self.repo / 'dist'; output.mkdir()
        prior_artifact = output / 'older-version.zip'; prior_artifact.write_bytes(b'prior artifact bytes')
        before = {path.relative_to(self.repo): path.read_bytes() for path in self.repo.rglob('*') if path.is_file()}
        self.runtime.update({'_internal/python313.dll': b'Python fixture',
                             '_internal/extension.pyd': b'extension fixture',
                             '_internal/tools/helper.exe': b'helper fixture'})
        self.info['dependencies'][0]['sources'] = ['https://private:secret@example.org/private']
        with self.assertRaisesRegex(ValueError, 'Missing reviewed native notices'):
            self.execute(default_native=True)
        reports = [path for path in work.glob('unqualified-native-*.json') if path != prior_report]
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text())
        self.assertEqual(report['schema'], 'marsdisplay-unqualified-native-v1')
        self.assertEqual(report['status'], 'UNQUALIFIED')
        self.assertEqual(report['failure_phase'], 'native_qualification')
        self.assertEqual(report['packaged_smoke'], {'status': 'passed'})
        self.assertEqual(report['source_commit'], 'a' * 40)
        self.assertEqual(report['source_files'], {name: hashlib.sha256(data).hexdigest() for name, data in self.source.items()})
        self.assertEqual(report['versions']['build'], {'Python': '3.13.5', 'PyInstaller': '6.22.3',
                                                     'Node': 'v24.fixture', 'Qt': '6.12.0'})
        self.assertEqual(report['versions']['dependencies'], [{'name': 'fixture', 'version': '1'}])
        self.assertEqual(report['versions']['browsers'], self.info['browsers'])
        expected = {name: hashlib.sha256(data).hexdigest() for name, data in self.runtime.items()
                    if Path(name).suffix.lower() in {'.dll', '.pyd', '.exe'}}
        self.assertEqual(report['native_files'], expected)
        for forbidden in ('private', 'secret', str(self.repo), 'traceback', 'qualification', 'license_sha256'):
            # failure_phase is a fixed category, not invented approval evidence.
            if forbidden == 'qualification':
                self.assertNotIn(forbidden, report)
            else:
                self.assertNotIn(forbidden, reports[0].read_text())
        for path, data in before.items():
            self.assertEqual((self.repo / path).read_bytes(), data)
        self.assertEqual(set(work.iterdir()), {prior_report, private.parent, reports[0]})
        self.assertEqual(set(output.iterdir()), {prior_artifact})
        self.assertEqual(self.events, ['inspect', 'compile', 'smoke'])
        # Diagnostic schema must not become an accepted native-material mapping.
        native = self.repo / 'native-rejection'; native.mkdir()
        (native / 'native.json').write_bytes(reports[0].read_bytes())
        with self.assertRaisesRegex(ValueError, 'Incomplete native qualification'):
            self.builder.collect_native(self.runtime, self.info, native)

    def test_smoke_failure_retains_sanitized_unavailable_status_without_publication(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic startup failed'):
            self.execute(smoke_failure=True)
        reports = list((self.repo / 'build').glob('unqualified-native-*.json'))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text())
        self.assertEqual(report['status'], 'UNQUALIFIED')
        self.assertEqual(report['failure_phase'], 'packaged_smoke')
        self.assertEqual(report['packaged_smoke'], {'status': 'failed_or_unavailable'})
        self.assertNotIn('synthetic startup failed', reports[0].read_text())
        self.assertEqual(self.events, ['inspect', 'compile', 'smoke'])
        self.assertEqual(list((self.repo / 'build').iterdir()), reports)
        self.assertFalse((self.repo / 'dist').exists())

    def test_ordered_native_recipe_smokes_before_only_publication(self):
        folder, archive, checksum = self.execute()
        self.assertEqual(self.events, ['inspect', 'compile', 'smoke', 'native-notices', 'publish'])
        inventory = json.loads((folder / 'inventory.json').read_text())
        self.assertEqual(inventory['build']['Node'], 'v24.fixture')
        self.assertEqual(inventory['native_components'], [{'name': 'native fixture'}])
        self.assertEqual(inventory['source_files']['LICENSE'], hashlib.sha256(b'GPL fixture').hexdigest())
        self.assertTrue(archive.is_file() and checksum.is_file())
        self.assertEqual(list((self.repo / 'build').iterdir()), [])

    def test_smoke_and_native_gaps_never_publish(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic startup failed'):
            self.execute(smoke_failure=True)
        self.assertNotIn('publish', self.events)
        self.assertFalse((self.repo / 'dist').exists())
        self.events.clear()
        self.native.side_effect = ValueError('Unmapped native material')
        with self.assertRaisesRegex(ValueError, 'Unmapped native material'):
            self.execute()
        self.assertEqual(self.events, ['inspect', 'compile', 'smoke', 'native-notices'])
        self.assertFalse((self.repo / 'dist').exists())

    def test_compile_or_sdk_failure_creates_no_fictitious_diagnostic(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic compile failed'):
            self.execute(compile_failure=True)
        self.assertEqual(list((self.repo / 'build').iterdir()), [])
        with patch.object(self.builder, 'require_host'), patch.object(self.builder, 'inspect_environment', side_effect=ValueError('synthetic SDK unavailable')):
            with self.assertRaisesRegex(ValueError, 'synthetic SDK unavailable'):
                self.builder.build(self.repo)
        self.assertEqual(list((self.repo / 'build').iterdir()), [])
        self.assertFalse((self.repo / 'dist').exists())

    def test_existing_outputs_rejected_before_process_and_preserved(self):
        output = self.repo / 'dist'; output.mkdir()
        prior = output / 'MarsDisplay'; prior.mkdir()
        (prior / 'user.txt').write_bytes(b'old user bytes')
        with self.assertRaises(FileExistsError):
            self.execute()
        self.assertEqual((prior / 'user.txt').read_bytes(), b'old user bytes')
        self.assertEqual(self.events, ['inspect'])
        self.assertFalse((self.repo / 'build').exists())

    def test_host_guard_help_invalid_options_no_sdk_or_process_effects(self):
        for host, machine, pointer in [('linux', 'x86_64', 8), ('win32', 'ARM64', 8), ('win32', 'AMD64', 4)]:
            with self.subTest(host=host, machine=machine, pointer=pointer), patch.object(self.builder.sys, 'platform', host), patch.object(self.builder.platform, 'machine', return_value=machine), patch.object(self.builder.struct, 'calcsize', return_value=pointer), patch.object(self.builder, 'inspect_environment', side_effect=AssertionError('SDK read')), patch.object(self.builder.subprocess, 'run', side_effect=AssertionError('process')):
                with self.assertRaisesRegex(RuntimeError, 'Windows x64'):
                    self.builder.build(self.repo)
        self.assertEqual(list(self.repo.iterdir()), [])
        for args, code, message in [(['--help'], 0, 'Windows x64'), (['--output', '../escape'], 2, 'unrecognized arguments')]:
            out, err = StringIO(), StringIO()
            with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as caught:
                self.builder.main(args)
            self.assertEqual(caught.exception.code, code)
            self.assertIn(message, out.getvalue() + err.getvalue())

    def test_sdk_runtime_and_bootloader_licenses_and_native_mapping_fail_closed(self):
        sdk = self.repo / 'sdk'; sdk.mkdir()
        (sdk / 'LICENSE.txt').write_bytes(b'CPython genuine fixture license')
        self.assertEqual(self.builder.python_license(sdk), {'runtime/Python/LICENSE.txt': b'CPython genuine fixture license'})
        with self.assertRaises(ValueError):
            self.builder.python_license(sdk / 'missing')
        native = self.repo / 'material'; native.mkdir()
        with self.assertRaisesRegex(ValueError, 'native'):
            self.builder.collect_native(self.runtime, self.info, native)
        name = '_internal/PySide6/plugins/platforms/qwindows.dll'
        (native / 'LICENSE.txt').write_bytes(b'actual native fixture legal text')
        record = {'path': name, 'sha256': hashlib.sha256(self.runtime[name]).hexdigest(),
                  'component': 'Qt platform fixture', 'version': '6.12.0',
                  'sources': ['https://example.org/qt/source'], 'licenses': ['LICENSE.txt']}
        manifest = {'qualification': 'Manually reviewed fixture, not legal certification', 'components': [record],
                    'license_sha256': {'LICENSE.txt': hashlib.sha256((native / 'LICENSE.txt').read_bytes()).hexdigest()}}
        (native / 'native.json').write_text(json.dumps(manifest))
        items, texts = self.builder.collect_native(self.runtime, self.info, native)
        self.assertEqual(items, [record])
        self.assertEqual(texts['native/LICENSE.txt'], b'actual native fixture legal text')
        for change in ('hash', 'missing', 'source'):
            bad = json.loads(json.dumps(manifest))
            if change == 'hash': bad['components'][0]['sha256'] = '0' * 64
            elif change == 'missing': bad['components'] = []
            else: bad['components'][0]['sources'] = ['https://user:private@example.org/']
            (native / 'native.json').write_text(json.dumps(bad))
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.builder.collect_native(self.runtime, self.info, native)

    def test_invalid_version_and_changed_source_do_not_publish(self):
        self.info['version'] = '../escape'
        with self.assertRaisesRegex(ValueError, 'Invalid artifact version'):
            self.execute()
        self.assertFalse((self.repo / 'build').exists())
        self.assertEqual(list(self.repo.iterdir()), [])
        self.info['version'] = '0.1.0'
        self.events.clear()
        with self.assertRaisesRegex(ValueError, 'Source changed during build'):
            self.execute(changed_source=True)
        self.assertEqual(self.events, ['inspect', 'compile', 'smoke', 'native-notices'])
        self.assertFalse((self.repo / 'dist').exists())
        reports = list((self.repo / 'build').glob('unqualified-native-*.json'))
        self.assertEqual(list((self.repo / 'build').iterdir()), reports)
        self.assertEqual(len(reports), 1)
        self.assertEqual(json.loads(reports[0].read_text())['failure_phase'], 'source_stability')

    def test_spec_workflow_and_corresponding_recipe_source(self):
        spec = Path('packaging/MarsDisplay.spec').read_text()
        for fragment in ('entrypoint.py', 'console=False', 'upx=False', 'COLLECT(', 'mars_display.devices', 'PyQt6', 'PySide6.QtWebEngine'):
            self.assertIn(fragment, spec)
        workflow = Path('.github/workflows/windows-portable.yml').read_text()
        for fragment in ('windows-2025', 'timeout-minutes: 30', 'retention-days: 7', 'persist-credentials: false', 'contents: read', 'feat/simulated-companion', 'workflow_dispatch:', 'architecture: x64', "python-version: '3.13'", 'if-no-files-found: error', '3d3c42e5aac5ba805825da76410c181273ba90b1', '5fda3b95a4ea91299a34e894583c3862153e4b97', 'cf430e030ddbb5b0abf93d22962f4752f3646cd9'):
            self.assertIn(fragment, workflow)
        self.assertIn("if: ${{ failure() && steps.native_build.outcome == 'failure' }}", workflow)
        self.assertIn('name: MarsDisplay-UNQUALIFIED-native-diagnostics', workflow)
        self.assertIn('path: build/unqualified-native-*.json', workflow)
        diagnostic_step = workflow.split('name: Upload unqualified metadata only', 1)[1].split('      - uses:', 1)[0]
        self.assertIn('retention-days: 7', diagnostic_step)
        self.assertIn('if-no-files-found: warn', diagnostic_step)
        self.assertNotIn('continue-on-error', workflow)
        self.assertNotIn('.zip', diagnostic_step)
        self.assertNotIn('.exe', diagnostic_step)
        files = self.builder.payload.collect_source(Path('.'))
        for name in ('packaging/build_portable.py', 'packaging/smoke.py', 'packaging/runtime_files.py', 'packaging/MarsDisplay.spec', '.github/workflows/windows-portable.yml'):
            self.assertIn(name, files)


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.smoke = load('smoke')
        self.enterContext(patch.dict(self.smoke.os.environ, {'SystemRoot': 'C:/Windows'}))

    def test_sanitized_env_isolated_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.smoke.environment(root, {'SystemRoot': 'C:/Windows', 'PATH': 'private tools', 'PYTHONPATH': 'external', 'QT_PLUGIN_PATH': 'external', 'QT_QPA_PLATFORM': 'offscreen', 'PLAYWRIGHT_NODEJS_PATH': 'external', 'LOCALAPPDATA': 'real user'})
            self.assertEqual(env['PATH'], str(Path('C:/Windows') / 'System32'))
            self.assertEqual(env['LOCALAPPDATA'], str(root / 'local'))
            self.assertEqual(env['HOME'], str(root / 'home'))
            self.assertEqual(env['TEMP'], env['TMP'])
            for name in ('PYTHONPATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM', 'PLAYWRIGHT_NODEJS_PATH'):
                self.assertNotIn(name, env)

    def test_readiness_not_just_alive_and_only_owned_process_stopped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            process = Mock(pid=123)
            process.poll.return_value = None
            process.wait.return_value = 0
            launch = Mock(return_value=process)
            probe = Mock(side_effect=[False, True])
            with patch.object(self.smoke, 'require_host'), patch.object(self.smoke, 'native_ready', probe):
                self.smoke.startup(root, root / 'isolated', popen=launch, seconds=1)
            self.assertEqual(probe.call_count, 2)
            process.terminate.assert_called_once()
            process.wait.assert_called_once_with(timeout=5)
            self.assertEqual(launch.call_args.args[0], [str(root / 'MarsDisplay.exe')])
            self.assertNotEqual(launch.call_args.kwargs['env'].get('LOCALAPPDATA'), 'real user')
            self.assertFalse((root / 'isolated/local/MarsDisplay/settings.json').exists())

    def test_packaged_version_commands_use_exact_registry_paths_and_deadlines(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = payload_fixtures.PayloadTests().fixture()
            runtime['_internal/playwright/driver/package/browsers.json'] = json.dumps({'browsers': [
                {'name': 'chromium-headless-shell', 'revision': '1248', 'browserVersion': '156.0.fixture'},
                {'name': 'ffmpeg', 'revision': '1013'}]}).encode()
            for name, data in runtime.items():
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            responses = [subprocess.CompletedProcess([], 0, text, '') for text in ('v24.0.0\n', 'Chromium 156.0.fixture\n', 'ffmpeg version fixture\n')]
            with patch.object(self.smoke, 'require_host'), patch.object(self.smoke.subprocess, 'run', side_effect=responses) as run, patch.object(self.smoke, 'startup') as startup:
                result = self.smoke.check(root, root / 'isolated')
            self.assertEqual(result, {'Node': 'v24.0.0', 'Chromium': 'Chromium 156.0.fixture', 'FFmpeg': 'ffmpeg version fixture'})
            self.assertEqual(run.call_count, 3)
            for call in run.call_args_list:
                self.assertEqual(call.kwargs['timeout'], 10)
                self.assertTrue(call.kwargs['check'])
                self.assertNotIn('--no-sandbox', call.args[0])
                self.assertTrue(Path(call.args[0][0]).is_relative_to(root))
            self.assertTrue(run.call_args_list[1].args[0][0].endswith('headless_shell.exe'))
            startup.assert_called_once_with(root, root / 'isolated')

    def test_native_probe_uses_installed_qt_lock_info_contract(self):
        import os
        from PySide6.QtCore import QLockFile
        process = Mock(pid=os.getpid(), _handle=456)
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = root / 'settings.json'
            settings.write_bytes(b'unchanged existing settings')
            lock_path = root / 'owned.lock'
            owner = QLockFile(str(lock_path))
            self.assertTrue(owner.tryLock(0))
            try:
                info = QLockFile(str(lock_path)).getLockInfo()
                self.assertEqual(len(info), 3)
                self.assertEqual(info[0], process.pid)
                boundary = Mock(side_effect=RuntimeError('controlled Win32 boundary'))
                with patch.object(self.smoke.ctypes, 'WinDLL', boundary, create=True):
                    with self.assertRaisesRegex(RuntimeError, '^controlled Win32 boundary$'):
                        self.smoke.native_ready(process, lock_path)
                    boundary.assert_called_once_with('user32', use_last_error=True)
                    owner.unlock()
                    boundary.reset_mock()
                    self.assertFalse(self.smoke.native_ready(process, lock_path))
                    boundary.assert_not_called()
                self.assertEqual(settings.read_bytes(), b'unchanged existing settings')
                self.assertEqual(list(root.iterdir()), [settings])
            finally:
                owner.unlock()

    def test_native_probe_rejects_dialog_wrong_lock_and_hung_gui(self):
        # Synthetic Win32 API boundary only. No native GUI proof is claimed.
        from PySide6 import QtCore
        process = Mock(pid=123, _handle=456)
        process.poll.return_value = None
        lock = Mock()
        lock.getLockInfo.return_value = (123, 'fixture', 'MarsDisplay')
        lock.tryLock.return_value = False
        user32 = Mock()
        user32.WaitForInputIdle.return_value = 0
        user32.IsWindowVisible.return_value = False
        user32.SendMessageTimeoutW.return_value = 1
        def owner(window, pointer):
            pointer._obj.value = 123
        user32.GetWindowThreadProcessId.side_effect = owner
        user32.EnumWindows.side_effect = lambda callback, _: callback(789, 0)
        with patch.object(QtCore, 'QLockFile', return_value=lock), patch.object(self.smoke.ctypes, 'WinDLL', return_value=user32, create=True), patch.object(self.smoke.ctypes, 'WINFUNCTYPE', self.smoke.ctypes.CFUNCTYPE, create=True):
            self.assertTrue(self.smoke.native_ready(process, Path('fixture.lock')))
            user32.IsWindowVisible.return_value = True
            self.assertFalse(self.smoke.native_ready(process, Path('fixture.lock')))
            user32.IsWindowVisible.return_value = False
            user32.SendMessageTimeoutW.return_value = 0
            self.assertFalse(self.smoke.native_ready(process, Path('fixture.lock')))
            lock.getLockInfo.return_value = (999, 'fixture', 'other')
            self.assertFalse(self.smoke.native_ready(process, Path('fixture.lock')))
        lock.unlock.assert_not_called()

    def test_messagebox_or_no_lock_never_becomes_ready_deadline_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); process = Mock(pid=123)
            process.poll.return_value = None
            with patch.object(self.smoke, 'require_host'), patch.object(self.smoke, 'native_ready', return_value=False):
                with self.assertRaisesRegex(RuntimeError, 'readiness'):
                    self.smoke.startup(root, root / 'isolated', popen=Mock(return_value=process), seconds=0.01)
            process.terminate.assert_called_once()
            process.wait.assert_called_once_with(timeout=5)
