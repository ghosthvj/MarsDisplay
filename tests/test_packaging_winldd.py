"""Authenticated source inputs with synthetic Windows SDK/EXEs, not native proof."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from test_packaging_payload import load
import test_packaging_payload as fixtures

CORE = '1.64.0-beta-1791568591000'
COMMIT = '1b2924712024804936dbcfe9fabaa655d52325e5'
ROOT = Path('third_party/license-material')
PREFIX = 'playwright-core/' + CORE + '/winldd/'
FILES = ('LICENSE.txt', 'NOTICE.txt', 'PrintDeps.cpp.txt', 'BUILD_NUMBER.txt')
TOOL = '_internal/playwright/driver/package/.local-browsers/winldd-1007/PrintDeps.exe'


class WinlddTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)
        self.notices, self.payload = load('notices'), load('payload')

    def write(self, root, name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def driver(self, root=None):
        root = self.root / 'driver' if root is None else root
        self.write(root, 'LICENSE', b'synthetic Node license')
        self.write(root, 'package/LICENSE', (ROOT / PREFIX / 'LICENSE.txt').read_bytes())
        self.write(root, 'package/NOTICE', (ROOT / PREFIX / 'NOTICE.txt').read_bytes())
        self.write(root, 'package/ThirdPartyNotices.txt', b'synthetic SDK notice')
        self.write(root, 'package/package.json', json.dumps({'name': 'playwright-core', 'version': CORE}).encode())
        self.write(root, 'package/browsers.json', json.dumps({'browsers': [
            {'name': 'chromium-headless-shell', 'revision': '1248'},
            {'name': 'ffmpeg', 'revision': '1013'},
            {'name': 'winldd', 'revision': '1007', 'installByDefault': False}]}).encode())
        self.write(root, 'package/.local-browsers/chromium_headless_shell-1248/LICENSE', b'browser license fixture')
        self.write(root, 'package/.local-browsers/ffmpeg-1013/COPYING.LGPLv2.1', b'FFmpeg license fixture')
        self.write(root, 'package/.local-browsers/winldd-1007/PrintDeps.exe', b'synthetic executable, not Windows proof')
        return root

    def material(self):
        _, files = self.payload.collect_license_material(ROOT)
        root = self.root / 'material'
        for name, data in files.items():
            self.write(root, name, data)
        return root

    def test_exact_core_winldd_without_local_license_retains_both_headers_and_provenance(self):
        inventory, material = self.notices.collect_vendor(self.driver())
        self.assertEqual([item['name'] for item in inventory], ['chromium-headless-shell', 'ffmpeg', 'winldd'])
        tool = inventory[-1]
        self.assertEqual(tool['revision'], '1007')
        self.assertEqual(tool['core'], {'name': 'playwright-core', 'version': CORE})
        self.assertEqual(tool['source_commit'], COMMIT)
        self.assertEqual(tool['executable'], 'package/.local-browsers/winldd-1007/PrintDeps.exe')
        self.assertEqual(tool['licenses'], ['upstream/' + PREFIX + name for name in FILES[:3]])
        self.assertEqual(tool['provenance_files'], ['upstream/' + PREFIX + name for name in FILES])
        self.assertEqual(len(tool['license_provenance']), 4)
        for name in FILES:
            self.assertEqual(material['upstream/' + PREFIX + name], (ROOT / PREFIX / name).read_bytes())
        cpp = material['upstream/' + PREFIX + 'PrintDeps.cpp.txt']
        self.assertIn(b'Copyright (c) 2020 Julien Waechter', cpp)
        self.assertIn(b'MIT License', cpp)
        self.assertIn(b'Licensed under the Apache License, Version 2.0', cpp)
        self.assertEqual(material['upstream/' + PREFIX + 'BUILD_NUMBER.txt'].strip(), b'1007')
        self.assertNotIn('upstream/' + PREFIX + 'BUILD_NUMBER.txt', tool['licenses'])
        self.assertTrue(all(record['packages'] == [] for record in tool['license_provenance']))

    def test_declared_winldd_stale_readme_revision_rejected_without_output_changes(self):
        prior = self.write(self.root, 'dist/older.zip', b'prior artifact bytes')
        fixture = fixtures.PayloadTests()
        runtime = fixture.fixture() | {TOOL: b'synthetic', TOOL.replace('1007/PrintDeps.exe', '9999/README'): b'not executable'}
        inventory = fixture.inventory()
        inventory['browsers'].append({'name': 'winldd', 'revision': '9999'})
        with self.assertRaises(ValueError):
            self.payload.assemble(prior.parent, '1', runtime, fixture.source(), {'notice': b'license'}, inventory)
        self.assertEqual(list(prior.parent.iterdir()), [prior])
        self.assertEqual(prior.read_bytes(), b'prior artifact bytes')

    def test_unknown_core_revision_metadata_and_executable_never_use_fallback(self):
        for change in ('name', 'version', 'gitHead', 'metadata-missing', 'metadata-invalid', 'revision', 'override', 'root-license', 'root-notice', 'missing-exe', 'wrong-exe'):
            with self.subTest(change=change):
                driver = self.driver(self.root / change)
                metadata = driver / 'package/package.json'
                if change in {'name', 'version', 'gitHead'}:
                    value = json.loads(metadata.read_text()); value[change] = 'unknown'
                    metadata.write_text(json.dumps(value))
                elif change == 'metadata-missing': metadata.unlink()
                elif change == 'metadata-invalid': metadata.write_bytes(b'not JSON')
                elif change in {'revision', 'override'}:
                    path = driver / 'package/browsers.json'; value = json.loads(path.read_text())
                    if change == 'revision':
                        value['browsers'][-1]['revision'] = '9999'
                        self.write(driver, 'package/.local-browsers/winldd-9999/PrintDeps.exe', b'synthetic')
                    else: value['browsers'][-1]['revisionOverrides'] = {'win64': '9999'}
                    path.write_text(json.dumps(value))
                elif change in {'root-license', 'root-notice'}:
                    (driver / ('package/LICENSE' if change == 'root-license' else 'package/NOTICE')).write_bytes(b'different source material')
                else:
                    (driver / 'package/.local-browsers/winldd-1007/PrintDeps.exe').unlink()
                    if change == 'wrong-exe': self.write(driver, 'package/.local-browsers/winldd-1007/winldd.exe', b'synthetic')
                with self.assertRaises((ValueError, OSError)):
                    self.notices.collect_vendor(driver)

    def test_missing_tampered_unsafe_or_rebound_registered_material_fails(self):
        driver = self.driver()
        material = self.material()
        original = (material / 'provenance.json').read_bytes()
        source = material / PREFIX / 'PrintDeps.cpp.txt'
        data = source.read_bytes()
        for change in ('missing', 'tampered', 'symlink', 'unsafe-path', 'source-url', 'commit', 'hash-rebound', 'version', 'packages'):
            with self.subTest(change=change):
                registry = json.loads(original)
                record = next(item for item in registry['materials'] if item['path'] == PREFIX + 'PrintDeps.cpp.txt')
                if change == 'missing': source.unlink()
                elif change == 'tampered': source.write_bytes(b'tampered source')
                elif change == 'symlink':
                    source.unlink(); source.symlink_to(ROOT.absolute() / PREFIX / 'PrintDeps.cpp.txt')
                elif change == 'unsafe-path': record['path'] = '../PrintDeps.cpp.txt'
                elif change == 'source-url': record['source_url'] = 'https://example.org/' + COMMIT + '/PrintDeps.cpp'
                elif change == 'commit':
                    record['source_url'] = record['source_url'].replace(COMMIT, 'a' * 40)
                    record['source_commit'] = 'a' * 40
                elif change == 'hash-rebound':
                    source.write_bytes(b'different source')
                    record['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
                elif change == 'version': record['upstream_version'] = '1.64.0'
                else: record['packages'] = [{'name': 'playwright', 'version': '1.64.0'}]
                (material / 'provenance.json').write_text(json.dumps(registry))
                with self.assertRaises((ValueError, OSError)):
                    self.notices.collect_vendor(driver, material_root=material)
                if source.is_symlink(): source.unlink()
                source.write_bytes(data)
        (material / 'provenance.json').write_bytes(original)

    def test_local_license_precedence_and_empty_or_unsafe_installed_text_rejection(self):
        driver = self.driver()
        license = self.write(driver, 'package/.local-browsers/winldd-1007/LICENSE', b'genuine fixture installed text')
        metadata = driver / 'package/package.json'; original = metadata.read_bytes()
        metadata.write_text(json.dumps({'name': 'playwright-core', 'version': 'unknown'}))
        inventory, material = self.notices.collect_vendor(driver, material_root=self.root / 'absent')
        metadata.write_bytes(original)
        self.assertEqual(inventory[-1]['licenses'], ['vendor/package/.local-browsers/winldd-1007/LICENSE'])
        self.assertNotIn('license_provenance', inventory[-1])
        self.assertEqual(material[inventory[-1]['licenses'][0]], b'genuine fixture installed text')
        license.write_bytes(b'')
        with self.assertRaises(ValueError): self.notices.collect_vendor(driver)
        license.unlink(); license.symlink_to(self.root / 'missing')
        with self.assertRaises(ValueError): self.notices.collect_vendor(driver)

    def test_optional_absence_original_required_browsers_and_unknown_inventory_preserved(self):
        fixture = fixtures.PayloadTests()
        runtime = fixture.fixture() | {TOOL: b'synthetic'}
        inventory = fixture.inventory()
        inventory['browsers'].append({'name': 'winldd', 'revision': '1007'})
        self.assertEqual(self.payload.browser_executable(runtime, 'winldd', '1007'), TOOL)
        folder, _, _ = self.payload.assemble(self.root / 'valid', '1', runtime, fixture.source(), {'notice': b'license'}, inventory)
        self.assertEqual((folder / TOOL).read_bytes(), b'synthetic')
        for change in ('missing', 'wrong-exe', 'duplicate', 'nonnumeric'):
            with self.subTest(change=change):
                files, info = dict(runtime), fixture.inventory()
                info['browsers'].append({'name': 'winldd', 'revision': '1007'})
                if change in {'missing', 'wrong-exe'}:
                    del files[TOOL]
                    if change == 'wrong-exe': files[TOOL.replace('PrintDeps.exe', 'winldd.exe')] = b'synthetic'
                elif change == 'duplicate': info['browsers'].append({'name': 'winldd', 'revision': '1007'})
                else: info['browsers'][-1]['revision'] = 'not-numeric'
                with self.assertRaises(ValueError):
                    self.payload.assemble(self.root / change, '1', files, fixture.source(), {'notice': b'license'}, info)
                self.assertFalse((self.root / change).exists())
        # Unknown optional names remain ignored; no new generic validation.
        info = fixture.inventory(); info['browsers'].append({'name': 'other-tool', 'revision': 'unknown'})
        self.payload.assemble(self.root / 'absent', '1', fixture.fixture(), fixture.source(), {'notice': b'license'}, info)
        driver = self.driver()
        path = driver / 'package/browsers.json'; registry = json.loads(path.read_text())
        registry['browsers'] = registry['browsers'][:2]; path.write_text(json.dumps(registry))
        items, _ = self.notices.collect_vendor(driver)
        self.assertEqual([item['name'] for item in items], ['chromium-headless-shell', 'ffmpeg'])
        registry['browsers'].append({'name': 'other-tool', 'revision': '1007'})
        path.write_text(json.dumps(registry))
        self.write(driver, 'package/.local-browsers/other_tool-1007/PrintDeps.exe', b'synthetic')
        with self.assertRaisesRegex(ValueError, 'Missing browser license material: other-tool'):
            self.notices.collect_vendor(driver)

    def test_supplementary_records_cannot_supply_whole_playwright_fallback(self):
        dist = fixtures.NoticeTests().missing_wheel('playwright', '1.64.0')
        with self.assertRaisesRegex(ValueError, 'Missing version-matched license material'):
            self.notices.collect_distributions(['playwright'], lambda _: dist)
