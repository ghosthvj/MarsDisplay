"""Pinned prebuilt OpenSSL intake, without executing downloaded code."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import urllib.request
import zipfile

from test_packaging_payload import load


class PrebuiltOpenSSLTests(unittest.TestCase):
    def setUp(self):
        self.module = load('openssl_prebuilt')
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.archive = self.root / 'provider.zip'
        self.destination = self.root / 'selected'
        self.data = {name: b'MZ fixture ' + name.encode() for name in self.module.DLLS}
        self.enterContext(patch.dict(self.module.DLLS, {
            name: {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
            for name, data in self.data.items()}, clear=True))

    def fixture(self, *, missing=False, duplicate=False):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for index, (name, data) in enumerate(self.data.items()):
                if missing and index == 0:
                    continue
                archive.writestr('x64/bin/' + name, data)
                if duplicate and index == 0:
                    archive.writestr('x64/bin/' + name, data)
            archive.writestr('../never-extract', b'ignored nonselected member')
        raw = self.archive.read_bytes()
        self.enterContext(patch.object(self.module, 'ARCHIVE_SIZE', len(raw)))
        self.enterContext(patch.object(self.module, 'ARCHIVE_SHA256', hashlib.sha256(raw).hexdigest()))
        return raw

    def test_prepare_selects_only_pinned_pair_and_preserves_archive(self):
        raw = self.fixture()
        result = self.module.prepare(self.archive, self.destination)
        self.assertEqual(result, self.destination)
        self.assertEqual({p.name for p in result.iterdir()}, set(self.data))
        self.assertEqual({p.name: p.read_bytes() for p in result.iterdir()}, self.data)
        self.assertEqual(self.archive.read_bytes(), raw)
        self.assertFalse((self.root / 'never-extract').exists())
        self.assertEqual(self.module.collect(result),
                         [(str(result / name), '.') for name in self.data])

    def test_rejected_inputs_never_create_output(self):
        for case in ('hash', 'missing', 'duplicate', 'dll-hash', 'linked'):
            with self.subTest(case=case):
                raw = self.fixture(missing=case == 'missing', duplicate=case == 'duplicate')
                if case == 'hash':
                    self.archive.write_bytes(raw + b'changed')
                before = self.archive.read_bytes()
                with contextlib.ExitStack() as stack:
                    if case == 'dll-hash':
                        stack.enter_context(patch.dict(self.module.DLLS, {
                            name: dict(record, sha256='0' * 64) for name, record in self.module.DLLS.items()}))
                    if case == 'linked':
                        stack.enter_context(patch.object(Path, 'is_symlink', return_value=True))
                    with self.assertRaises(ValueError):
                        self.module.prepare(self.archive, self.destination)
                self.assertFalse(self.destination.exists())
                self.assertEqual(self.archive.read_bytes(), before)

    def test_existing_output_and_modified_selection_fail_closed(self):
        self.fixture()
        self.module.prepare(self.archive, self.destination)
        before = {p.name: p.read_bytes() for p in self.destination.iterdir()}
        with self.assertRaises(FileExistsError):
            self.module.prepare(self.archive, self.destination)
        self.assertEqual({p.name: p.read_bytes() for p in self.destination.iterdir()}, before)
        name = next(iter(self.data))
        (self.destination / name).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, '^Pinned OpenSSL DLL mismatch$'):
            self.module.collect(self.destination)
        self.assertEqual((self.destination / name).read_bytes(), b'changed')

    def test_download_verifies_pin_and_refuses_overwrite_or_http_redirect(self):
        raw = self.fixture()
        target = self.root / 'download.zip'
        opener = Mock()
        opener.open.return_value = io.BytesIO(raw)
        with patch.object(self.module.urllib.request, 'build_opener', return_value=opener):
            self.module.fetch(target)
            self.assertEqual(target.read_bytes(), raw)
            request = opener.open.call_args.args[0]
            self.assertIsInstance(request, urllib.request.Request)
            self.assertEqual(request.full_url, self.module.URL)
            self.assertEqual(request.get_header('User-agent'), 'MarsDisplay-build/1.0')
            opener.reset_mock()
            with self.assertRaises(FileExistsError):
                self.module.fetch(target)
            opener.open.assert_not_called()
            self.assertEqual(target.read_bytes(), raw)
            opener.open.return_value = io.BytesIO(raw[:-1])
            with self.assertRaisesRegex(ValueError, '^Pinned OpenSSL archive mismatch$'):
                self.module.fetch(self.root / 'bad.zip')
        request = urllib.request.Request(self.module.URL)
        with self.assertRaisesRegex(ValueError, '^Non-HTTPS OpenSSL redirect$'):
            self.module.HTTPSRedirect().redirect_request(request, None, 302, 'Found', {}, 'http://example.invalid/file')

    def test_cli_requires_windows_and_reports_signature_failure_without_success(self):
        raw = self.fixture()
        for index, (platform, signature_ok) in enumerate((('linux', True), ('win32', False), ('win32', True))):
            destination = self.root / ('cli-' + str(index))
            stdout, stderr = io.StringIO(), io.StringIO()
            with (patch.object(self.module.sys, 'platform', platform),
                  patch.object(self.module, 'verify_signatures', side_effect=None if signature_ok else ValueError('Invalid signer')) as signatures,
                  contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr)):
                result = self.module.main(['--archive', str(self.archive), '--output', str(destination)])
            success = platform == 'win32' and signature_ok
            self.assertEqual(result, 0 if success else 1)
            self.assertEqual(stdout.getvalue(), 'Prepared verified FireDaemon OpenSSL 3.5.9 (x64).\n' if success else '')
            self.assertEqual(stderr.getvalue(), '' if success else
                             ('OpenSSL preparation requires Windows.\n' if platform == 'linux'
                              else 'OpenSSL preparation failed (signatures; ValueError).\n'))
            self.assertEqual(signatures.call_count, 0 if platform == 'linux' else 1)
            self.assertEqual(self.archive.read_bytes(), raw)
            if platform == 'linux':
                self.assertFalse(destination.exists())
            else:
                self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir()}, self.data)

    def test_default_cli_failure_identifies_phase_without_private_error_text(self):
        raw = self.fixture()
        for phase in ('output', 'download', 'archive', 'signatures'):
            destination = self.root / ('failed-' + phase)
            calls = []
            def operation(name, result=None):
                def invoke(*args):
                    calls.append(name)
                    if phase == name:
                        if name == 'download':
                            raise self.module.urllib.error.HTTPError('https://private.invalid/secret', 403, 'PRIVATE', {}, None)
                        raise ValueError('PRIVATE C:/private/settings.json')
                    return result
                return invoke
            out, err = io.StringIO(), io.StringIO()
            with (patch.object(self.module.sys, 'platform', 'win32'),
                  patch.object(self.module, '_plain', side_effect=operation('output', destination)),
                  patch.object(self.module, 'fetch', side_effect=operation('download', self.archive)),
                  patch.object(self.module, 'prepare', side_effect=operation('archive')),
                  patch.object(self.module, 'verify_signatures', side_effect=operation('signatures')),
                  contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
                result = self.module.main(['--output', str(destination)])
            self.assertEqual(result, 1)
            self.assertEqual(out.getvalue(), '')
            detail = 'HTTPError; HTTP 403' if phase == 'download' else 'ValueError'
            self.assertEqual(err.getvalue(), 'OpenSSL preparation failed (' + phase + '; ' + detail + ').\n')
            self.assertEqual(calls, list(('output', 'download', 'archive', 'signatures'))[:list(('output', 'download', 'archive', 'signatures')).index(phase) + 1])
            self.assertFalse(destination.exists())
            self.assertEqual(self.archive.read_bytes(), raw)

    def test_hook_preserves_qt_traversal_without_ambient_collection(self):
        hook = Path('packaging/hooks/hook-PySide6.QtNetwork.py').resolve()
        events = []
        pairs = [('controlled/crypto.dll', '.'), ('controlled/ssl.dll', '.')]
        helper = types.SimpleNamespace(collect=Mock(side_effect=lambda root: events.append('collect') or pairs))
        qt = types.ModuleType('PyInstaller.utils.hooks.qt')
        qt.add_qt6_dependencies = Mock(side_effect=lambda name: events.append('qt') or
                                      (['PySide6.QtCore'], [('Qt6Network.dll', '.')], [('qt-data', '.')]))
        qt.pyside6_library_info = Mock()
        qt.pyside6_library_info.collect_qtnetwork_files.side_effect = AssertionError('Ambient lookup')
        spec = types.SimpleNamespace(loader=Mock())
        scope = {'__file__': str(hook)}
        with (patch.dict(sys.modules, {'PyInstaller.utils.hooks.qt': qt}),
              patch('importlib.util.spec_from_file_location', return_value=spec),
              patch('importlib.util.module_from_spec', return_value=helper)):
            exec(compile(hook.read_text(), str(hook), 'exec'), scope)
        self.assertEqual(events, ['collect', 'qt'])
        helper.collect.assert_called_once_with(hook.parents[2] / 'build/openssl-prebuilt')
        qt.add_qt6_dependencies.assert_called_once_with(str(hook))
        qt.pyside6_library_info.collect_qtnetwork_files.assert_not_called()
        self.assertEqual(scope['hiddenimports'], ['PySide6.QtCore'])
        self.assertEqual(scope['binaries'], [('Qt6Network.dll', '.'), *pairs])
        self.assertEqual(scope['datas'], [('qt-data', '.')])

    def test_workflow_prepares_prebuilt_without_source_compilation(self):
        workflow = Path('.github/workflows/windows-portable.yml').read_text()
        self.assertIn('python -B packaging/openssl_prebuilt.py', workflow)
        self.assertLess(workflow.index('python -B packaging/openssl_prebuilt.py'),
                        workflow.index('python packaging/build_portable.py'))
        self.assertIn('timeout-minutes: 30', workflow)
        self.assertIn('and not r.skipped', workflow)
        self.assertIn("failure() && steps.native_build.outcome == 'failure'", workflow)
        self.assertNotIn('openssl_candidate', workflow)
        self.assertNotIn('build_openssl_candidate.py', workflow)
        grouping = Path('.github/workflows/windows-usb-grouping.yml').read_text()
        self.assertIn('python -B packaging/openssl_prebuilt.py', grouping)
        self.assertLess(grouping.index('python -B packaging/openssl_prebuilt.py'),
                        grouping.index('python -B packaging/build_grouping_experiment.py'))

    def test_reviewed_policy_binds_provider_pair_and_preserves_python_pair(self):
        policy = load('native_material').read_inputs(Path('.').resolve())['policy']
        entries = {item['path']: item for item in policy['supplemental']}
        provider = load('openssl_prebuilt')
        for name, record in provider.DLLS.items():
            item = entries['_internal/' + name]
            self.assertEqual(item['sha256'], record['sha256'])
            self.assertEqual(item['module'], 'openssl-3.5.9')
            self.assertIsNone(item['owner'])
            self.assertEqual(item['pe'], {'status': 'measured', 'file_version': '3.5.9.0', 'product_version': '3.5.9.0'})
        self.assertEqual(entries['_internal/libcrypto-3.dll']['sha256'],
                         '75495fe0e079ab00d49be740d3c710a0b94e3f74f9648cb7cc9f768fc7f52319')
        self.assertEqual(entries['_internal/libssl-3.dll']['sha256'],
                         '8957182a9c385bfd9f3f790921de2ddc614cf91f99edbed4e9e5446a46504e32')

    def test_provider_snapshots_travel_with_source_and_source_access(self):
        root = Path('.').resolve()
        source = load('payload').collect_source(root)
        folder = root / 'third_party/firedaemon-openssl'
        provenance = json.loads((folder / 'provenance.json').read_text())
        for name, record in provenance['files'].items():
            data = (folder / name).read_bytes()
            self.assertEqual(len(data), record['size'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), record['sha256'])
            self.assertEqual(source['third_party/firedaemon-openssl/' + name], data)
        self.assertEqual((folder / 'version.txt').read_bytes(), b'openssl-3.5.9-0-g45e844fa2a\n')
        material = load('native_material')
        bundle = material.read_inputs(root)
        for profile in ('portable', 'usb-grouping-v1'):
            self.assertIn(b'source/third_party/firedaemon-openssl/', material.source_access(bundle, profile=profile))

    def test_signature_child_rebuilds_legacy_module_path_without_mutating_parent(self):
        self.fixture()
        self.module.prepare(self.archive, self.destination)
        overrides = {'PSModulePath': 'PRIVATE/CoreModules', 'PSMODULEPATH': 'PRIVATE/OtherCore',
                     'PsModulePath': 'PRIVATE/MixedCase', 'MARSDISPLAY_TEST_KEEP': 'unchanged'}
        with (patch.dict(self.module.os.environ, overrides),
              patch.object(self.module.subprocess, 'run', return_value=Mock(returncode=0)) as run):
            before = dict(self.module.os.environ)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.module.verify_signatures(self.destination)
            child = run.call_args.kwargs['env']
            expected = {key: value for key, value in before.items() if key.upper() != 'PSMODULEPATH'}
            expected['MARSDISPLAY_OPENSSL_VERIFY_ROOT'] = str(self.destination)
            self.assertEqual(child, expected)
            self.assertEqual(dict(self.module.os.environ), before)
            self.assertEqual((out.getvalue(), err.getvalue()), ('', ''))
            self.assertEqual({p.name: p.read_bytes() for p in self.destination.iterdir()}, self.data)

    def test_signature_check_requires_valid_expected_signer(self):
        self.fixture()
        self.module.prepare(self.archive, self.destination)
        for code in (0, 1):
            stderr = io.StringIO()
            with (patch.object(self.module.subprocess, 'run', return_value=Mock(returncode=code,
                    stdout=b'libcrypto-3-x64.dll:NotTrusted\nPRIVATE C:/private/settings.json\n')) as run,
                  contextlib.redirect_stderr(stderr)):
                if code:
                    with self.assertRaisesRegex(ValueError, '^OpenSSL Authenticode verification failed$'):
                        self.module.verify_signatures(self.destination)
                else:
                    self.module.verify_signatures(self.destination)
                command = run.call_args.args[0]
                self.assertIn("$signature.Status -ne 'Valid'", command[-1])
                self.assertIn('FireDaemon Technologies Limited', command[-1])
                self.assertEqual(stderr.getvalue(), 'OpenSSL signature libcrypto-3-x64.dll:NotTrusted\n' if code else '')
                self.assertEqual(run.call_args.kwargs['env']['MARSDISPLAY_OPENSSL_VERIFY_ROOT'], str(self.destination))
