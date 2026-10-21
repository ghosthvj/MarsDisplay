"""Synthetic profile checks; these do not qualify Windows binaries."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_packaging_payload import load

ROOT = Path(__file__).resolve().parents[1]
from test_grouping_profile import PROFILE, REQUIRED


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.module = load('grouping_payload')
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.source = self.module.collect_source(ROOT)
        self.runtime = {name: b'SYNTHETIC ' + name.encode() for name in REQUIRED}
        self.runtime.update({'MarsDisplayGroupingExperiment.exe': b'SYNTHETIC EXE',
                             '_internal/python313.dll': b'SYNTHETIC PYTHON',
                             '_internal/grouping-pattern.rgb888': self.source['tools/windows-usb-probe/pattern.rgb888'],
                             'README.txt': b'instructions'})
        self.notices = {'license.txt': b'SYNTHETIC license'}
        record = dict(name='fixture', version='1', sources=['https://example.org/source'], licenses=['license.txt'])
        native = [dict(record, path=name, sha256=hashlib.sha256(self.runtime[name]).hexdigest()) for name in REQUIRED]
        self.inventory = dict(schema='marsdisplay-grouping-v1', profile=PROFILE, target='Windows-x64',
            source_commit='a'*40, source_files=self.module.hashes(self.source),
            build={'Python': '3.13.16', 'PyInstaller': '6.22.3', 'Qt': '6.12.0'},
            dependencies=[dict(record, name=name) for name in ('PySide6_Essentials', 'shiboken6', 'pyserial')],
            build_dependencies=[dict(record, name='PyInstaller')], runtime_components=[dict(record, name='CPython')],
            browsers=[], native_components=native, packaged_smoke={'status': 'passed'})

    def assemble(self):
        return self.module.assemble(self.root / 'dist', '0.1.4', self.runtime,
                                    self.source, self.notices, self.inventory)

    def test_exact_zip_manifest_and_exclusive_outputs_preserve_normal_artifact(self):
        import zipfile
        prior = self.root / 'dist/MarsDisplay-old.zip'
        prior.parent.mkdir()
        prior.write_bytes(b'prior normal binary')
        folder, archive, checksum = self.assemble()
        self.assertEqual(folder.name, 'MarsDisplayGroupingExperiment')
        self.assertEqual(checksum.read_text(), hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
        with zipfile.ZipFile(archive) as zipped:
            files = {n.removeprefix(folder.name + '/'): zipped.read(n) for n in zipped.namelist()}
        inventory = json.loads(files.pop('inventory.json'))
        self.assertEqual(inventory['files'], self.module.hashes(files))
        self.assertEqual(inventory['source_files'], self.module.hashes(self.source))
        self.assertEqual(prior.read_bytes(), b'prior normal binary')
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaises(FileExistsError):
            self.assemble()
        self.assertEqual({p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)

    def test_malformed_runtime_source_hash_license_inventory_reject_without_outputs(self):
        original = copy.deepcopy((self.runtime, self.source, self.notices, self.inventory))
        for change in ('fixture', 'exe', 'qt', 'browser', 'unsafe', 'source', 'hash', 'license', 'native', 'smoke', 'metadata'):
            self.runtime, self.source, self.notices, self.inventory = copy.deepcopy(original)
            if change == 'fixture': self.runtime['_internal/grouping-pattern.rgb888'] = b'bad'
            elif change == 'exe': del self.runtime['MarsDisplayGroupingExperiment.exe']
            elif change == 'qt': del self.runtime['_internal/PySide6/QtGui.pyd']
            elif change == 'browser': self.runtime['_internal/playwright/driver/node.exe'] = b'not allowed'
            elif change == 'unsafe': self.runtime['../escape'] = b'unsafe'
            elif change == 'source': del self.source['src/mars_display/usb_grouping_worker.py']
            elif change == 'hash': self.inventory['source_files']['LICENSE'] = '0'*64
            elif change == 'license': self.inventory['dependencies'][0]['licenses'] = ['missing.txt']
            elif change == 'native': self.inventory['native_components'][0]['sha256'] = '0'*64
            elif change == 'smoke': self.inventory['packaged_smoke'] = {'status': 'failed'}
            else: del self.inventory['build']['Python']
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.assemble()
            self.assertEqual(list(self.root.iterdir()), [])

    def test_source_closure_is_explicit_and_excludes_private_workspace(self):
        for name in ('packaging/grouping_entrypoint.py', 'packaging/grouping_bootstrap.py',
                     'packaging/grouping_payload.py', '.github/workflows/windows-usb-grouping.yml',
                     'docs/usb-grouping-experiment.md', 'docs/usb-grouping-protocol.md'):
            self.assertIn(name, self.source)
        self.assertFalse(any(name.startswith(('odd/', 'build/', '.herdr-web-ui/')) for name in self.source))


class BuilderTests(unittest.TestCase):
    def test_synthetic_windows_build_orders_checks_and_never_publishes_on_failure(self):
        fixture = PayloadTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        module = load('build_grouping_experiment')
        events = []
        info = copy.deepcopy(fixture.inventory)
        info['version'] = '0.1.4'
        native = [dict(item, licenses=['license.txt'], version_evidence=['evidence.txt'])
                  for item in info['native_components']]
        texts = {'native/license.txt': b'SYNTHETIC license', 'native/evidence.txt': b'SYNTHETIC evidence',
                 'native/supplemental.json': b'{"components": []}'}
        def compile(command, **kwargs):
            events.append('compile')
            self.assertEqual(Path(command[-1]).name, 'MarsDisplayGroupingExperiment.spec')
            destination = Path(command[command.index('--distpath') + 1]) / 'MarsDisplayGroupingExperiment'
            for name, data in fixture.runtime.items():
                if name == 'README.txt':
                    continue
                path = destination / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        def smoke(folder, scratch):
            events.append('smoke')
            self.assertEqual((folder / 'README.txt').read_bytes(), fixture.source['packaging/GROUPING-README.txt'])
            return {'status': 'passed'}
        def prepare(*args, **kwargs):
            events.append('native')
            self.assertEqual(kwargs, {'profile': PROFILE})
            return fixture.root / 'unused-synthetic-native'
        with patch.object(module.base, 'require_host'), patch.object(module.base, 'inspect_environment', side_effect=lambda *a, **k: (copy.deepcopy(info), dict(fixture.notices))), patch.object(module.payload, 'collect_source', return_value=fixture.source), patch.object(module.base.native_material, 'prepare', side_effect=prepare), patch.object(module.base, 'collect_native', return_value=(native, texts)):
            folder, archive, checksum = module.build(fixture.root, run=compile, smoke_check=smoke)
            self.assertEqual(events, ['compile', 'smoke', 'native'])
            self.assertTrue(folder.is_dir() and archive.is_file() and checksum.is_file())
            before = archive.read_bytes()
            with self.assertRaises(FileExistsError):
                module.build(fixture.root, run=compile, smoke_check=smoke)
            self.assertEqual(archive.read_bytes(), before)
            events.clear()
            failed = fixture.root / 'failure'
            failed.mkdir()
            with self.assertRaisesRegex(RuntimeError, 'qualification failed'):
                module.build(failed, run=compile, smoke_check=Mock(side_effect=RuntimeError('qualification failed')))
            self.assertEqual(events, ['compile'])
            self.assertFalse((failed / 'dist').exists())
            self.assertEqual(list((failed / 'build').iterdir()), [])

    def test_host_guard_and_help_before_sdk_or_output(self):
        import contextlib
        from io import StringIO
        module = load('build_grouping_experiment')
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(module.base, 'require_host', side_effect=RuntimeError('native rejection')), patch.object(module.base, 'inspect_environment', side_effect=AssertionError('SDK')):
                with self.assertRaisesRegex(RuntimeError, 'native rejection'):
                    module.build(Path(temp))
                self.assertEqual(list(Path(temp).iterdir()), [])
            out, err = StringIO(), StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as caught:
                module.main(['--help'])
            self.assertEqual(caught.exception.code, 0)
            self.assertIn('native Windows x64', out.getvalue())
            self.assertEqual(err.getvalue(), '')
            out, err = StringIO(), StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch.object(module.base.sys, 'platform', 'linux'), patch.object(module.base, 'inspect_environment', side_effect=AssertionError('SDK')):
                code = module.main([])
            self.assertEqual((code, out.getvalue(), err.getvalue()), (1, '',
                'Experimental build failed: Portable builds require native Windows x64; no cross-compilation is supported.\n'))
