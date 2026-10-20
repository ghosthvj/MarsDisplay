"""Portable tests for the probe's native-origin gate; no native execution."""
from importlib import util
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch
import io
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from types import SimpleNamespace
import json
import subprocess
import sys
import os
import zipfile


def load_tool(name):
    spec = util.spec_from_file_location('probe_test_' + name,
                                      ROOT / 'tools/windows-python-usb-probe' / (name + '.py'))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / 'tools/windows-python-usb-probe/qualification.py'


def load_recipe():
    spec = util.spec_from_file_location('probe_qualification_test', RECIPE)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeOriginTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='probe-origin-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sdk = self.root / 'sdk'
        self.sdk.mkdir()
        (self.sdk / 'DLLs').mkdir()
        (self.sdk / 'python313.dll').write_bytes(b'MZ-core')
        (self.sdk / 'DLLs/_socket.pyd').write_bytes(b'MZ-socket')
        (self.sdk / 'LICENSE.txt').write_bytes(b'Python license fixture')
        self.runtime = {
            'PythonUsbProbe.exe': b'MZ-project-executable',
            '_internal/python313.dll': b'MZ-core',
            '_internal/_socket.pyd': b'MZ-socket',
            '_internal/probe-assets/pattern.rgb888': b'raw fixture',
        }
        self.origins = {
            '_internal/python313.dll': self.sdk / 'python313.dll',
            '_internal/_socket.pyd': self.sdk / 'DLLs/_socket.pyd',
        }

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def reject(self, message):
        before = self.snapshot()
        runtime, origins = dict(self.runtime), dict(self.origins)
        with self.assertRaisesRegex(ValueError, message):
            load_recipe().sdk_origin_facts(self.runtime, self.origins, self.sdk)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.runtime, runtime)
        self.assertEqual(self.origins, origins)

    def test_actual_sdk_bytes_are_facts_not_legal_approval(self):
        before = self.snapshot()
        result = load_recipe().sdk_origin_facts(self.runtime, self.origins, self.sdk)
        self.assertEqual(result, {
            'status': 'UNQUALIFIED',
            'project_executable': {
                'path': 'PythonUsbProbe.exe',
                'sha256': hashlib.sha256(b'MZ-project-executable').hexdigest(),
                'qualification': 'PyInstaller build and bootloader evidence required',
            },
            'sdk_files': {
                '_internal/_socket.pyd': {
                    'sdk_path': 'DLLs/_socket.pyd',
                    'sha256': hashlib.sha256(b'MZ-socket').hexdigest(),
                    'qualification': 'Component source and license coverage required',
                },
                '_internal/python313.dll': {
                    'sdk_path': 'python313.dll',
                    'sha256': hashlib.sha256(b'MZ-core').hexdigest(),
                    'qualification': 'Component source and license coverage required',
                },
            },
        })
        self.assertEqual(self.snapshot(), before)

    def test_hash_mismatch_rejects_without_writes(self):
        self.runtime['_internal/_socket.pyd'] = b'MZ-different'
        self.reject('SDK bytes differ from delivered native file')

    def test_missing_origin_rejects_without_writes(self):
        del self.origins['_internal/_socket.pyd']
        self.reject('Native Analysis origins do not match payload')

    def test_extra_origin_rejects_without_writes(self):
        self.origins['_internal/unused.dll'] = self.sdk / 'python313.dll'
        self.reject('Native Analysis origins do not match payload')

    def test_same_bytes_outside_sdk_are_not_sdk_provenance(self):
        outside = self.root / '_socket.pyd'
        outside.write_bytes(b'MZ-socket')
        self.origins['_internal/_socket.pyd'] = outside
        self.reject('Native origin is outside approved SDK locations')

    def test_site_packages_is_not_a_core_sdk_origin(self):
        directory = self.sdk / 'Lib/site-packages'
        directory.mkdir(parents=True)
        origin = directory / '_socket.pyd'
        origin.write_bytes(b'MZ-socket')
        self.origins['_internal/_socket.pyd'] = origin
        self.reject('Native origin is outside approved SDK locations')

    def test_renamed_sdk_file_is_not_accepted(self):
        self.origins['_internal/_socket.pyd'] = self.sdk / 'python313.dll'
        self.reject('Native destination differs from SDK basename')

    def test_symlink_origin_is_rejected(self):
        # Inject filesystem metadata, not Windows link-creation privileges.
        origin = self.origins['_internal/_socket.pyd']
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda path: path == origin or original(path)):
            self.reject('Symlink native origin')

    def test_unknown_executable_rejects(self):
        self.runtime['_internal/other.exe'] = b'MZ-other'
        self.reject('Unexpected native executable')

    def test_microsoft_and_optional_mesa_are_never_delivered(self):
        for name in ('vcruntime140.dll', 'MSVCP140.dll', 'ucrtbase.dll',
                     'api-ms-win-crt-runtime-l1-1-0.dll', 'opengl32sw.dll'):
            with self.subTest(name=name):
                self.runtime['_internal/' + name] = b'MZ-external'
                self.reject('External-runtime profile')
                del self.runtime['_internal/' + name]

    def test_gui_browser_and_imaging_payloads_reject(self):
        for name in ('_internal/PySide6/QtCore.pyd', '_internal/PIL/Image.pyc',
                     '_internal/playwright/driver/node.exe', '_internal/Qt6Core.dll',
                     '_internal/chromium/resources.pak'):
            with self.subTest(name=name):
                self.runtime[name] = b'unwanted'
                self.reject('Forbidden diagnostic dependency')
                del self.runtime[name]

    def test_unsafe_or_colliding_payload_names_reject(self):
        for name in ('../escape.dll', '_internal/PYTHON313.DLL',
                     '_internal/python313.dll/child'):
            with self.subTest(name=name):
                self.runtime[name] = b'bad'
                self.reject('Unsafe payload path|Duplicate path|File/directory collision')
                del self.runtime[name]

    def test_missing_console_executable_rejects(self):
        del self.runtime['PythonUsbProbe.exe']
        self.reject('Missing diagnostic executable')

    def test_embedded_components_remain_explicitly_unqualified(self):
        for name in ('libcrypto-3.dll', 'libffi-8.dll', '_ssl.pyd'):
            with self.subTest(name=name):
                origin = self.sdk / 'DLLs' / name
                origin.write_bytes(b'MZ-component')
                self.runtime['_internal/' + name] = b'MZ-component'
                self.origins['_internal/' + name] = origin
                report = load_recipe().sdk_origin_facts(self.runtime, self.origins, self.sdk)
                self.assertEqual(report['status'], 'UNQUALIFIED')
                self.assertEqual(report['sdk_files']['_internal/' + name]['qualification'],
                                 'Component source and license coverage required')


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='probe-publish-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'published'
        self.files = {'PythonUsbProbe.exe': b'exe', 'source.zip': b'source', 'README.md': b'readme'}
        self.hashes = {k: hashlib.sha256(v).hexdigest() for k, v in self.files.items()}

    def test_exclusive_publish_readback_and_checksums(self):
        builder = load_tool('build_probe')
        archive, sidecar = builder.publish(self.output, self.files, self.hashes)
        self.assertEqual(archive.parent, self.output)
        self.assertEqual(sidecar.read_text(), hashlib.sha256(archive.read_bytes()).hexdigest()
                         + '  ' + archive.name + '\n')
        with zipfile.ZipFile(archive) as z:
            for name, data in self.files.items():
                self.assertEqual(z.read('PythonUsbProbe/' + name), data)
        self.assertEqual((self.output / 'PythonUsbProbe/README.md').read_bytes(), b'readme')
        before = archive.read_bytes()
        with self.assertRaises(FileExistsError):
            builder.publish(self.output, self.files, self.hashes)
        self.assertEqual(archive.read_bytes(), before)

    def test_existing_empty_output_is_not_owned(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            load_tool('build_probe').publish(self.output, self.files, self.hashes)
        self.assertTrue(self.output.is_dir())
        self.assertEqual(list(self.output.iterdir()), [])

    def test_collision_and_hash_mismatch_create_nothing(self):
        for extra, hashes in [({'readme.MD': b'collision'}, self.hashes),
                              ({}, {**self.hashes, 'README.md': '0' * 64}),
                              ({'README.md/child': b'collision'}, self.hashes)]:
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    load_tool('build_probe').publish(self.output, {**self.files, **extra}, hashes)
                self.assertFalse(self.output.exists())

    def test_failed_write_rolls_back_only_owned_directory(self):
        sentinel = self.root / 'existing'
        sentinel.write_bytes(b'keep')
        original = Path.open
        def fail(path, *args, **kwargs):
            if path.name.endswith('.sha256'):
                raise OSError('injected sidecar failure')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', fail), self.assertRaises(OSError):
            load_tool('build_probe').publish(self.output, self.files, self.hashes)
        self.assertFalse(self.output.exists())
        self.assertEqual(sentinel.read_bytes(), b'keep')

    def test_reproducible_zip_and_unsafe_archive_paths(self):
        builder = load_tool('build_probe')
        self.assertEqual(builder.zip_bytes(self.files), builder.zip_bytes(dict(reversed(list(self.files.items())))))
        with self.assertRaises(ValueError):
            builder.zip_bytes({'../bad': b'bad'})

    def test_source_allowlist_and_stability(self):
        builder = load_tool('build_probe')
        source = builder.collect_source(ROOT)
        self.assertIn('src/mars_display/usb_probe_process.py', source)
        self.assertIn('tools/windows-usb-probe/pattern.rgb888', source)
        self.assertIn('.github/workflows/windows-python-usb-probe.yml', source)
        self.assertNotIn('src/mars_display/app.py', source)
        self.assertNotIn('odd/tasks/native-python-usb-probe.md', source)
        self.assertFalse(any('direct_url' in name for name in source))
        builder.assert_source_stable(source, dict(source))
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            builder.assert_source_stable(source, {**source, 'README.md': b'changed'})


class ProfileTests(unittest.TestCase):
    def test_import_graph_and_pyz_fail_closed(self):
        q = load_recipe()
        modules = ['mars_display.usb_probe', 'mars_display.usb_probe_process',
                   'mars_display.usb_protocol', 'serial', 'ctypes', 'hashlib']
        q.audit_modules(modules, modules)
        for bad in ('PIL.Image', 'PySide6.QtCore', 'playwright.sync_api', 'mars_display.app'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                q.audit_modules(modules, modules + [bad])
        with self.assertRaises(ValueError):
            q.audit_modules(modules, [])

    def test_profile_missing_terms_cannot_qualify(self):
        with tempfile.TemporaryDirectory(prefix='probe-profile-') as temporary:
            q = load_recipe()
            sdk = Path(temporary)
            (sdk / 'python313.dll').write_bytes(b'core')
            runtime = {'PythonUsbProbe.exe': b'exe', '_internal/python313.dll': b'core'}
            origins = {'_internal/python313.dll': sdk / 'python313.dll'}
            with self.assertRaisesRegex(ValueError, 'Missing Python Windows SDK license'):
                q.qualify(runtime, origins, sdk, {}, {}, {}, ROOT)
            self.assertEqual(sorted(p.name for p in sdk.iterdir()), ['python313.dll'])

    def test_missing_bootloader_or_native_pe_never_qualifies(self):
        with tempfile.TemporaryDirectory(prefix='probe-profile-') as temporary:
            q = load_recipe()
            sdk = Path(temporary)
            (sdk / 'python313.dll').write_bytes(b'core')
            runtime = {'PythonUsbProbe.exe': b'exe', '_internal/python313.dll': b'core'}
            material = {'runtime/Python/LICENSE.txt': b'PSF LICENSE AGREEMENT FOR PYTHON'}
            with self.assertRaisesRegex(ValueError, 'Missing pinned build evidence'):
                q.qualify(runtime, {'_internal/python313.dll': sdk / 'python313.dll'},
                          sdk, {}, material, {}, ROOT)


class ComposedProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='probe-composed-')
        self.addCleanup(self.temp.cleanup)
        self.sdk = Path(self.temp.name)
        (self.sdk / 'python313.dll').write_bytes(b'core')
        self.runtime = {'PythonUsbProbe.exe': b'exe', '_internal/python313.dll': b'core'}
        self.origins = {'_internal/python313.dll': self.sdk / 'python313.dll'}
        self.material = {'runtime/Python/LICENSE.txt': b'PSF LICENSE AGREEMENT; zlib; expat',
                         'serial-license': b'BSD license', 'installer-license': b'GPL bootloader exception'}
        self.inventory = {
            'build': {'Python': '3.13.9', 'PyInstaller': '6.22.3', 'pyserial': '3.5',
                      'sys_version': '3.13.9 test SDK', 'compiler': 'test compiler'},
            'bootloader': {'sha256': 'a'*64, 'record_sha256': 'a'*64, 'distribution_metadata_sha256': 'b'*64,
                          'source': 'https://github.com/pyinstaller/pyinstaller/tree/v6.22.3/bootloader'},
            'dependencies': [{'name': 'pyserial', 'version': '3.5',
                              'licenses': ['serial-license'], 'sources': ['https://github.com/pyserial/pyserial']}],
            'build_dependencies': [{'name': 'PyInstaller', 'version': '6.22.3',
                                    'licenses': ['installer-license'], 'sources': ['https://github.com/pyinstaller/pyinstaller']}],
        }
        modules = ['mars_display.usb_probe', 'mars_display.usb_probe_process', 'mars_display.usb_protocol', 'serial']
        self.analysis = {'modules': modules, 'pyz_modules': modules,
                         'bootloader_sha256': 'a'*64, 'exe_sha256': hashlib.sha256(b'exe').hexdigest()}

    def measure(self, runtime, inventory):
        return {name: {'sha256': hashlib.sha256(data).hexdigest(), 'machine': 'AMD64/PE32+',
                       'pe': {'status': 'absent'}} for name, data in runtime.items()}

    def qualify(self, **kwargs):
        return load_recipe().qualify(self.runtime, self.origins, self.sdk, self.inventory,
                                     self.material, self.analysis, ROOT, measure=kwargs.get('measure', self.measure))

    def test_composition_qualifies_only_bound_core_and_executable(self):
        result = self.qualify()
        self.assertEqual(result['status'], 'QUALIFIED')
        self.assertEqual({item['path'] for item in result['components']}, set(self.runtime))
        self.assertEqual(result['origin_facts']['status'], 'UNQUALIFIED')

    def test_unknown_native_and_libffi_without_version_terms_reject(self):
        for name in ('unknown.dll', 'libffi-8.dll'):
            with self.subTest(name=name):
                (self.sdk / name).write_bytes(b'unknown')
                self.runtime['_internal/' + name] = b'unknown'
                self.origins['_internal/' + name] = self.sdk / name
                with self.assertRaises(ValueError):
                    self.qualify()
                del self.runtime['_internal/' + name]
                del self.origins['_internal/' + name]

    def test_legal_missing_or_bootstrap_hash_mismatch_reject(self):
        for key in ('serial-license', 'installer-license', 'runtime/Python/LICENSE.txt'):
            saved = self.material.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.qualify()
            self.material[key] = saved
        self.analysis['bootloader_sha256'] = 'b'*64
        with self.assertRaisesRegex(ValueError, 'Missing pinned build evidence'):
            self.qualify()

    def test_native_machine_hash_and_unknown_version_reject(self):
        for mutation in ({'machine': 'x86'}, {'sha256': '0'*64}, {'pe': {'status': 'unknown'}}):
            def measure(runtime, inventory):
                facts = self.measure(runtime, inventory)
                facts['PythonUsbProbe.exe'].update(mutation)
                return facts
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'PE/hash'):
                self.qualify(measure=measure)


    def test_core_extension_cannot_hide_an_unqualified_dependency(self):
        for name, marker in (('_ctypes.pyd', b'libffi'), ('_hashlib.pyd', b'openssl'), ('_ssl.pyd', b'openssl')):
            with self.subTest(name=name):
                (self.sdk / name).write_bytes(b'extension')
                self.runtime['_internal/' + name] = b'extension'
                self.origins['_internal/' + name] = self.sdk / name
                self.material['runtime/Python/LICENSE.txt'] += b' ' + marker
                before = dict(self.material)
                with self.assertRaisesRegex(ValueError, 'Missing qualified'):
                    self.qualify()
                self.assertEqual(self.material, before)
                del self.runtime['_internal/' + name]
                del self.origins['_internal/' + name]

    def test_reviewed_openssl_bytes_terms_and_source_are_bound(self):
        q = load_recipe()
        name = '_internal/libcrypto-3.dll'
        (self.sdk / 'libcrypto-3.dll').write_bytes(b'crypto')
        self.runtime[name] = b'crypto'
        self.origins[name] = self.sdk / 'libcrypto-3.dll'
        bundle = {'policy': {'supplemental': [{'module': 'openssl-3.5.9', 'path': name,
                   'sha256': hashlib.sha256(b'crypto').hexdigest(), 'pe': {'status': 'absent'}}]},
                  'registry': {'openssl': {'3.5.9': {'source_archive': 'https://example.org/openssl.tar.gz'}},
                               'files': [{'module': 'openssl-3.5.9', 'kind': 'license', 'path': 'raw/license.txt'}]},
                  'files': {'raw/license.txt': b'OpenSSL terms'}}
        original = q._helper
        with patch.object(q, '_helper', side_effect=lambda name: SimpleNamespace(read_inputs=lambda repo: bundle)
                          if name == 'native_material' else original(name)):
            result = q.qualify(self.runtime, self.origins, self.sdk, self.inventory,
                               self.material, self.analysis, ROOT, measure=self.measure)
            self.assertEqual(result['status'], 'QUALIFIED')
            self.assertEqual(self.material['native-inputs/raw/license.txt'], b'OpenSSL terms')
            bundle['policy']['supplemental'][0]['sha256'] = '0'*64
            before = dict(self.material)
            with self.assertRaisesRegex(ValueError, 'Unmapped actual OpenSSL'):
                q.qualify(self.runtime, self.origins, self.sdk, self.inventory,
                          self.material, self.analysis, ROOT, measure=self.measure)
            self.assertEqual(self.material, before)

    def test_libffi_needs_matching_explicit_generated_version_reference(self):
        name = '_internal/libffi-8.dll'
        (self.sdk / 'libffi-8.dll').write_bytes(b'ffi')
        self.runtime[name] = b'ffi'
        self.origins[name] = self.sdk / 'libffi-8.dll'
        self.material['runtime/Python/LICENSE.txt'] += b'\nlibffi 3.4.4\nPermission is hereby granted'
        def measure(runtime, inventory):
            facts = self.measure(runtime, inventory)
            facts[name]['pe'] = {'status': 'measured', 'product_version': '3.4.4.0'}
            return facts
        self.assertEqual(self.qualify(measure=measure)['status'], 'QUALIFIED')
        self.material['runtime/Python/LICENSE.txt'] = self.material['runtime/Python/LICENSE.txt'].replace(b'3.4.4', b'3.4.5')
        with self.assertRaisesRegex(ValueError, 'Missing libffi source-version'):
            self.qualify(measure=measure)


class BuildPipelineTests(unittest.TestCase):
    def test_no_publish_until_qualification_smoke_and_stable_source(self):
        for failure in (None, 'qualification', 'smoke', 'source', 'unqualified'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(prefix='probe-build-') as temporary:
                root = Path(temporary)
                builder = load_tool('build_probe')
                source = {name: b'source' for name in builder.SOURCE_PATHS}
                source['README.md'] = b'source'
                original_load = builder.load
                def load(path):
                    return SimpleNamespace(require_host=lambda: None) if path.name == 'build_portable.py' else original_load(path)
                def run(vector, **kwargs):
                    dist = Path(vector[vector.index('--distpath') + 1]) / 'PythonUsbProbe'
                    dist.mkdir(parents=True)
                    (dist / 'PythonUsbProbe.exe').write_bytes(b'exe')
                    Path(kwargs['env']['PROBE_ANALYSIS_REPORT']).write_text(json.dumps({
                        'origins': {}, 'modules': [], 'pyz_modules': [], 'exe_sha256': 'a'*64,
                        'bootloader_sha256': 'b'*64, 'entrypoint': {
                            'path': 'tools/windows-python-usb-probe/entrypoint.py',
                            'sha256': hashlib.sha256(b'source').hexdigest()}}))
                with ExitStack() as stack:
                    stack.enter_context(patch.object(builder, 'load', side_effect=load))
                    stack.enter_context(patch.object(builder, 'collect_source', side_effect=[source,
                        {**source, 'README.md': b'changed'} if failure == 'source' else source]))
                    stack.enter_context(patch.object(builder, 'source_revision', return_value='c'*40))
                    stack.enter_context(patch.object(builder, 'installed_environment', return_value=({'build': {'Python': '3.13.9'}}, {'license': b'terms'})))
                    stack.enter_context(patch.object(builder.smoke, 'source_tests', return_value={'tests': 40, 'skips': 0}))
                    stack.enter_context(patch.object(builder.smoke, 'check_vector',
                        side_effect=ValueError('smoke rejected') if failure == 'smoke' else None,
                        return_value={'status': 'passed'}))
                    stack.enter_context(patch.object(builder.smoke, 'parent_death', return_value={'status': 'passed'}))
                    stack.enter_context(patch.object(builder.smoke, 'frozen_lifetime', return_value={'status': 'passed'}))
                    stack.enter_context(patch.object(builder.qualification, 'qualify',
                        side_effect=ValueError('qualification rejected') if failure == 'qualification' else None,
                        return_value={'status': 'UNQUALIFIED' if failure == 'unqualified' else 'QUALIFIED'}))
                    if failure is None:
                        archive, sidecar = builder.build(root, run=run)
                        self.assertTrue(archive.is_file())
                        self.assertTrue(sidecar.is_file())
                        self.assertFalse((root / 'build/python-usb-probe-work/unqualified.json').exists())
                    else:
                        with self.assertRaises(ValueError):
                            builder.build(root, run=run)
                        self.assertFalse((root / 'build/python-usb-probe').exists())
                        report = json.loads((root / 'build/python-usb-probe-work/unqualified.json').read_text())
                        self.assertEqual(report['status'], 'UNQUALIFIED')
                        self.assertNotIn(str(root), json.dumps(report))
                        self.assertEqual(list((root / 'build/python-usb-probe-work').iterdir()),
                                         [root / 'build/python-usb-probe-work/unqualified.json'])

    def test_cli_failure_and_success_streams(self):
        builder = load_tool('build_probe')
        for error in (False, True):
            out, err = io.StringIO(), io.StringIO()
            with patch.object(builder, 'build', side_effect=RuntimeError('native required') if error else None,
                              return_value=(Path('probe.zip'), Path('probe.zip.sha256'))), redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(builder.main([]), 1 if error else 0)
            self.assertEqual(out.getvalue(), '' if error else 'probe.zip\nprobe.zip.sha256\n')
            self.assertEqual(err.getvalue(), 'Probe build failed: native required\n' if error else '')
        out, err = io.StringIO(), io.StringIO()
        with patch.object(builder, 'build') as build, patch.object(sys, 'argv', ['build_probe.py']), redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as raised:
                builder.main(['--badflag'])
            self.assertEqual(raised.exception.code, 2)
            build.assert_not_called()
        self.assertEqual(out.getvalue(), '')
        self.assertEqual(err.getvalue(), 'usage: build_probe.py [-h]\nbuild_probe.py: error: unrecognized arguments: --badflag\n')


class SmokeTests(unittest.TestCase):
    def test_safe_commands_exact_streams_and_isolated_environment(self):
        smoke = load_tool('smoke')
        from mars_display import usb_probe
        calls = []
        def run(vector, **kwargs):
            calls.append((vector, kwargs))
            args = vector[1:]
            values = {('--help',): (0, usb_probe.HELP, ''),
                      ('--self-test',): (0, usb_probe.SELF_TEST_OK, ''),
                      ('--list',): (0, '', ''),
                      (): (0, usb_probe.PORT_PROMPT + usb_probe.CANCELLED, '')}
            code, out, err = values.get(tuple(args), (2, '', usb_probe.ERRORS[2] + '\n'))
            return subprocess.CompletedProcess(vector, code, out, err)
        with tempfile.TemporaryDirectory(prefix='probe-smoke-') as temporary:
            root = Path(temporary)
            report = smoke.check_vector(['probe.exe'], root / 'state', run=run,
                                        system_root=root / 'Windows')
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(len(calls), 7)
            for vector, kwargs in calls:
                self.assertEqual(kwargs['input'], '')
                self.assertLessEqual(kwargs['timeout'], 100)
                self.assertNotIn('SEND', vector)
                self.assertNotIn('PYTHONPATH', kwargs['env'])
                self.assertEqual(kwargs['env']['HOME'], str(root / 'state'))
                self.assertEqual(kwargs['env']['PATH'], str(root / 'Windows/System32'))

    def test_native_source_runner_rejects_every_skip(self):
        smoke = load_tool('smoke')
        with tempfile.TemporaryDirectory(prefix='probe-source-tests-') as temporary:
            root = Path(temporary)
            for skipped in (0, 1):
                with self.subTest(skipped=skipped), patch.dict(os.environ, {'SystemRoot': str(root / 'Windows')}):
                    def run(vector, **kwargs):
                        self.assertEqual(kwargs['env']['TEMP'], str(root / ('state' + str(skipped))))
                        return subprocess.CompletedProcess(vector, 0,
                            json.dumps({'tests': 40, 'skips': skipped, 'failures': 0, 'errors': 0}), '')
                    if skipped:
                        with self.assertRaisesRegex(ValueError, 'Incomplete native source test evidence'):
                            smoke.source_tests(ROOT, root / 'state1', run=run)
                    else:
                        self.assertEqual(smoke.source_tests(ROOT, root / 'state0', run=run)['skips'], 0)

    def test_smoke_rejects_stdout_stderr_exit_and_timeout(self):
        smoke = load_tool('smoke')
        for result in (subprocess.CompletedProcess([], 1, '', ''),
                       subprocess.CompletedProcess([], 0, 'wrong', ''),
                       subprocess.CompletedProcess([], 0, '', 'error'),
                       subprocess.TimeoutExpired([], 1)):
            with tempfile.TemporaryDirectory(prefix='probe-smoke-') as temporary:
                def run(*args, **kwargs):
                    if isinstance(result, Exception):
                        raise result
                    return result
                with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                    smoke.check_vector(['probe.exe'], Path(temporary) / 'state', run=run,
                                       system_root=Path(temporary) / 'Windows')


if __name__ == '__main__':
    unittest.main()
