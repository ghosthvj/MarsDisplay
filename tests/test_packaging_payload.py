import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import zipfile


def load(name):
    spec = importlib.util.spec_from_file_location('portable_' + name, Path('packaging') / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = load('payload')

    def fixture(self):
        # Deliberately synthetic bytes, never a runnable Windows artifact.
        return {'MarsDisplay.exe': b'synthetic',
                '_internal/PySide6/Qt/plugins/platforms/qwindows.dll': b'qt fixture',
                '_internal/playwright/driver/node.exe': b'node fixture',
                '_internal/playwright/driver/package/browsers.json': b'{}',
                '_internal/playwright/driver/package/.local-browsers/ffmpeg-1013/ffmpeg-win64.exe': b'ffmpeg fixture',
                '_internal/playwright/driver/package/.local-browsers/chromium_headless_shell-1248/chrome-headless-shell-win64/headless_shell.exe': b'browser fixture'}

    def source(self):
        return dict.fromkeys(['src/mars_display/app.py', 'packaging/entrypoint.py', 'tests/test_app.py',
                              'README.md', 'pyproject.toml', 'requirements.txt', 'requirements-build.txt'], b'# source') | {'LICENSE': b'GPL fixture'}

    def inventory(self):
        return {'source_commit': 'a' * 40, 'target': 'Windows-x64',
                'build': {'Python': '3.13.5', 'PyInstaller': '6.22.3', 'Node': 'fixture-version'},
                'dependencies': [{'name': 'fixture', 'version': '1', 'sources': ['https://example.org']}],
                'browsers': [{'name': 'chromium-headless-shell', 'revision': '1248'}, {'name': 'ffmpeg', 'revision': '1013'}]}

    def assemble(self, runtime=None):
        return self.payload.assemble(self.root / 'dist', '0.1.0', self.fixture() if runtime is None else runtime,
                                     self.source(), {'third-party/example/LICENSE': b'actual fixture license'}, self.inventory())

    def test_coherent_folder_zip_source_inventory_checksum(self):
        folder, archive, checksum = self.assemble()
        self.assertEqual(folder.name, 'MarsDisplay')
        self.assertEqual(archive.name, 'MarsDisplay-0.1.0-Windows-x64.zip')
        self.assertEqual(checksum.read_text(), hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(set(zipped.namelist()), {'MarsDisplay/' + p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()})
            self.assertEqual(zipped.read('MarsDisplay/source/src/mars_display/app.py'), b'# source')
            self.assertEqual(zipped.read('MarsDisplay/notices/third-party/example/LICENSE'), b'actual fixture license')
            recorded = json.loads(zipped.read('MarsDisplay/inventory.json'))
            self.assertEqual(recorded['source_commit'], 'a' * 40)
            self.assertEqual(recorded['files']['MarsDisplay.exe'], hashlib.sha256(b'synthetic').hexdigest())
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaises(FileExistsError):
            self.assemble()
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_missing_each_runtime_resource_and_unsafe_paths_leave_no_outputs(self):
        for missing in self.fixture():
            files = self.fixture(); del files[missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                self.assemble(files)
        for bad in ['../escape', '/absolute', 'C:/drive', 'a\\b', 'a/../b', '.env', 'profile/cookies', 'settings.json', '.git/config', 'x/token.txt', 'x:stream', 'Inventory.JSON']:
            with self.subTest(path=bad), self.assertRaises(ValueError):
                self.assemble(self.fixture() | {bad: b'private'})
        with self.assertRaises(ValueError):
            self.assemble(self.fixture() | {'marsdisplay.EXE': b'collision'})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_source_allowlist_and_symlink_rejection(self):
        repo = self.root / 'repo'; repo.mkdir()
        for name in ['src/mars_display/app.py', 'packaging/entrypoint.py', 'tests/fixtures/display.html', 'README.md', 'LICENSE', 'pyproject.toml', 'requirements.txt', 'requirements-build.txt', '.env', 'odd/tasks/private.md', 'src/settings.json', 'tests/__pycache__/test.pyc']:
            path = repo / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'fixture')
        files = self.payload.collect_source(repo)
        self.assertEqual(set(files), {'src/mars_display/app.py', 'packaging/entrypoint.py', 'tests/fixtures/display.html', 'README.md', 'LICENSE', 'pyproject.toml', 'requirements.txt', 'requirements-build.txt'})
        (repo / 'src/link.py').symlink_to(repo / 'README.md')
        with self.assertRaises(ValueError):
            self.payload.collect_source(repo)
        with self.assertRaises(ValueError):
            self.payload.read_tree(repo)

    def test_preexisting_checksum_and_partial_publication_failure_preserved(self):
        dist = self.root / 'dist'; dist.mkdir()
        sidecar = dist / 'MarsDisplay-0.1.0-Windows-x64.zip.sha256'; sidecar.write_bytes(b'old')
        with self.assertRaises(FileExistsError):
            self.assemble()
        self.assertEqual(list(dist.iterdir()), [sidecar])
        self.assertEqual(sidecar.read_bytes(), b'old')
        from unittest.mock import patch
        # A distinct directory exercises failure after staging, before publication.
        other = self.root / 'other'
        with patch.object(self.payload.os, 'link', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.payload.assemble(other, '1.0', self.fixture(), self.source(), {'license': b'notice'}, self.inventory())
        self.assertEqual(list(other.iterdir()), [])

    def test_incomplete_corresponding_source_and_stale_revision_rejected(self):
        for index, missing in enumerate(self.source()):
            source = self.source(); del source[missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                self.payload.assemble(self.root / ('missing-' + str(index)), '1', self.fixture(), source, {'license': b'notice'}, self.inventory())
        inventory = self.inventory(); inventory['browsers'][0]['revision'] = '9999'
        with self.assertRaises(ValueError):
            self.payload.assemble(self.root / 'dist', '1', self.fixture(), self.source(), {'license': b'notice'}, inventory)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_inventory_and_license_requirements(self):
        for source, notices, inventory in [({}, {'license': b'x'}, {}), ({'LICENSE': b'x'}, {}, {}), ({'LICENSE': b'x'}, {'license': b'x'}, {'source_commit': 'unknown'})]:
            with self.assertRaises(ValueError):
                self.payload.assemble(self.root / 'dist', '1', self.fixture(), source, notices, inventory)
        self.assertFalse((self.root / 'dist').exists())


class NoticeTests(unittest.TestCase):
    def missing_wheel(self, name='pyserial', version='3.5'):
        item = Mock()
        item.metadata = {'Name': name, 'Version': version, 'License': 'Original wheel statement',
                         'Home-page': 'https://example.org/project'}
        item.requires = []; item.files = []
        return item

    def legal_fixture(self, root):
        records = []
        for path, packages, coverage in [
            ('pyserial/3.5/LICENSE.txt', [{'name': 'pyserial', 'version': '3.5'}], 'complete pyserial license'),
            ('bindings/LICENSE.txt', [{'name': 'PySide6', 'version': '6.12.0'}, {'name': 'PySide6_WebEngine', 'version': '6.12.0.140'}],
             'Python binding material only; not complete native/WebEngine coverage; commercial reference grants no rights'),
            ('qtbase/LICENSE.txt', [], 'supplementary only; native binary mapping still required')]:
            file = root / path; file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b'Unmodified fixture legal text\n')
            records.append({'path': path, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
                            'source_url': 'https://example.org/source/' + 'a' * 40 + '/' + path,
                            'source_commit': 'a' * 40, 'upstream_version': 'fixture',
                            'packages': packages, 'coverage': coverage})
        registry = {'schema_version': 1, 'materials': records, 'source_archives': [],
                    'qualification': 'Source material only; no native audit or commercial rights.'}
        (root / 'provenance.json').write_text(json.dumps(registry))
        (root / 'README.md').write_bytes(b'Qualification directions; no native binary audit.\n')
        return registry

    def test_exact_fallback_shared_material_and_qualified_binding_inventory(self):
        notices = load('notices')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); registry = self.legal_fixture(root)
            dists = {'pyserial': self.missing_wheel(), 'pyside6': self.missing_wheel('PySide6', '6.12.0'),
                     'pyside6-webengine': self.missing_wheel('PySide6_WebEngine', '6.12.0.140')}
            inventory, material = notices.collect_distributions(list(dists), dists.__getitem__, material_root=root)
            self.assertEqual(len(material), 5)  # three texts, one registry and one README, not per-package copies
            self.assertEqual(material['upstream/provenance.json'], (root / 'provenance.json').read_bytes())
            self.assertEqual(material['upstream/qtbase/LICENSE.txt'], b'Unmodified fixture legal text\n')
            for item in inventory:
                self.assertEqual(item['license'], 'Original wheel statement')
                self.assertEqual(item['sources'], ['https://example.org/project'])
                self.assertEqual(item['license_registry'], 'upstream/provenance.json')
                self.assertEqual(item['license_qualification'], registry['qualification'])
                self.assertEqual(len(item['license_provenance']), 1)
                self.assertNotIn('upstream/qtbase/LICENSE.txt', item['licenses'])
            for item in inventory:
                if item['name'] != 'pyserial':
                    self.assertEqual(item['license_provenance'][0]['coverage'], registry['materials'][1]['coverage'])
                    self.assertEqual(item['licenses'], ['upstream/bindings/LICENSE.txt'])

    def test_unknown_newer_or_unmapped_version_never_uses_fallback(self):
        notices = load('notices')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.legal_fixture(root)
            for name, version in [('pyserial', '3.6'), ('PySide6', '6.12.1'), ('PySide6_WebEngine', '6.12.0'), ('unknown', '3.5')]:
                with self.subTest(name=name, version=version), self.assertRaises(ValueError):
                    notices.collect_distributions([name], lambda _: self.missing_wheel(name, version), material_root=root)

    def test_missing_modified_unsafe_or_unproven_material_is_rejected(self):
        notices = load('notices')
        for change in ['missing', 'modified', 'traversal', 'absolute', 'symlink', 'parent-symlink',
                       'credentials', 'uncommitted-url', 'missing-coverage', 'duplicate', 'registry-symlink']:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); registry = self.legal_fixture(root)
                record = registry['materials'][0]; file = root / record['path']
                if change == 'missing': file.unlink()
                elif change == 'modified': file.write_bytes(b'changed bytes')
                elif change == 'traversal': record['path'] = '../escape.txt'
                elif change == 'absolute': record['path'] = str(file)
                elif change == 'symlink':
                    target = root / 'copy.txt'; target.write_bytes(file.read_bytes()); file.unlink(); file.symlink_to(target)
                elif change == 'parent-symlink':
                    (root / 'alias').symlink_to(file.parent, target_is_directory=True); record['path'] = 'alias/LICENSE.txt'
                elif change == 'credentials': record['source_url'] = 'https://user:password@example.org/' + 'a' * 40
                elif change == 'uncommitted-url': record['source_url'] = 'https://example.org/main/LICENSE.txt'
                elif change == 'missing-coverage': del record['coverage']
                elif change == 'duplicate': registry['materials'].append(dict(record, path=record['path'].upper()))
                (root / 'provenance.json').write_text(json.dumps(registry))
                if change == 'registry-symlink':
                    (root / 'copy.json').write_bytes((root / 'provenance.json').read_bytes())
                    (root / 'provenance.json').unlink(); (root / 'provenance.json').symlink_to(root / 'copy.json')
                with self.assertRaises(ValueError):
                    notices.collect_distributions(['pyserial'], lambda _: self.missing_wheel(), material_root=root)

    def test_source_contains_only_registered_legal_inputs_and_retains_provenance(self):
        payload = load('payload')
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp); root = repo / 'third_party/license-material'; root.mkdir(parents=True)
            registry = self.legal_fixture(root)
            (repo / '.gitattributes').write_bytes(b'fixture attributes\n')
            (root / 'unregistered-private.txt').write_bytes(b'not a source input')
            files = payload.collect_source(repo)
            expected = {'third_party/license-material/' + item['path'] for item in registry['materials']}
            expected.update({'.gitattributes', 'third_party/license-material/provenance.json', 'third_party/license-material/README.md'})
            self.assertEqual(set(files), expected)
            self.assertEqual(json.loads(files['third_party/license-material/provenance.json']), registry)
            for item in registry['materials']:
                self.assertEqual(hashlib.sha256(files['third_party/license-material/' + item['path']]).hexdigest(), item['sha256'])
            (root / registry['materials'][0]['path']).write_bytes(b'tampered')
            with self.assertRaises(ValueError): payload.collect_source(repo)

    def test_committed_default_material_is_independent_of_working_directory(self):
        notices = load('notices')
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp, patch('os.getcwd', return_value=temp):
            inventory, material = notices.collect_distributions(['pyserial'], lambda _: self.missing_wheel())
        self.assertEqual(inventory[0]['license_provenance'][0]['source_commit'], '0e7634747568547b8a7f9fd0c48ed74f16af4b23')
        self.assertEqual(len(material), 58)  # 56 immutable inputs plus registry/README.

    def test_installed_license_precedes_unavailable_fallback(self):
        notices = load('notices')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'LICENSE').write_bytes(b'wheel license')
            dist = self.missing_wheel(); dist.files = [Path('LICENSE')]
            dist.locate_file.side_effect = lambda path: root / path
            inventory, material = notices.collect_distributions(['pyserial'], lambda _: dist, material_root=root / 'absent')
            self.assertEqual(list(material.values()), [b'wheel license'])
            self.assertNotIn('license_provenance', inventory[0])
            dist.locate_file.assert_called_once_with('')

    def test_actual_metadata_closure_raw_licenses_and_no_build_extras(self):
        notices = load('notices')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'LICENSE').write_bytes(b'raw license statement')
            def dist(name, requirements):
                item = Mock()
                item.metadata = {'Name': name, 'Version': '1.2', 'License': 'Raw expression, not SPDX', 'Home-page': 'https://example.org/project'}
                item.requires = requirements; item.files = [Path('LICENSE')]
                item.locate_file.side_effect = lambda path: root / path
                return item
            distributions = {'app': dist('app', ['dep==1.2', 'builder; extra == "build"']), 'dep': dist('dep', [])}
            inventory, material = notices.collect_distributions(['app'], distributions.__getitem__)
            self.assertEqual([i['name'] for i in inventory], ['app', 'dep'])
            self.assertTrue(all(i['version'] == '1.2' and i['license'] == 'Raw expression, not SPDX' and i['sources'] == ['https://example.org/project'] for i in inventory))
            self.assertEqual(list(material.values()), [b'raw license statement'] * 2)
            distributions['dep'].files = []
            with self.assertRaises(ValueError):
                notices.collect_distributions(['app'], distributions.__getitem__)

    def test_vendor_node_browser_ffmpeg_material_and_exact_revision(self):
        notices = load('notices')
        with tempfile.TemporaryDirectory() as temp:
            driver = Path(temp)
            paths = ['LICENSE', 'package/LICENSE', 'package/NOTICE', 'package/ThirdPartyNotices.txt',
                     'package/.local-browsers/chromium_headless_shell-1248/LICENSE',
                     'package/.local-browsers/ffmpeg-1013/COPYING.LGPLv2.1']
            for name in paths:
                path = driver / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'raw vendor material')
            (driver / 'package/browsers.json').write_text(json.dumps({'browsers': [{'name': 'chromium-headless-shell', 'revision': '1248', 'browserVersion': '149.0'}, {'name': 'ffmpeg', 'revision': '1013'}]}))
            inventory, material = notices.collect_vendor(driver)
            self.assertEqual([i['revision'] for i in inventory], ['1248', '1013'])
            self.assertEqual(len(material), 7)
            self.assertEqual(material['vendor/LICENSE'], b'raw vendor material')
            sidecar = driver / 'package/lib/utilsBundle.js.LICENSE'
            sidecar.parent.mkdir(); sidecar.write_bytes(b'actual inlined library license')
            _, expanded = notices.collect_vendor(driver)
            self.assertEqual(expanded['vendor/package/lib/utilsBundle.js.LICENSE'], b'actual inlined library license')
            (driver / paths[-1]).unlink()
            with self.assertRaisesRegex(ValueError, 'ffmpeg'):
                notices.collect_vendor(driver)
