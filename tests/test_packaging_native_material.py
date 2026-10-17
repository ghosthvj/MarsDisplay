"""Synthetic material/fact fixtures only; no native qualification or genuine manifest."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_packaging_payload import load

PREFIX = '_internal/PySide6/'
SCHEMA = 'marsdisplay-native-material-v2'


def material_fixture(root, runtime, versions=None):
    """Explicitly synthetic source texts; semantic/legal review is NOT simulated."""
    versions = versions or {}
    root.mkdir(exist_ok=True)
    texts = {'LICENSE.txt': b'SYNTHETIC license text fixture, not distribution evidence'}
    components, facts = [], {}
    for index, path in enumerate(sorted(name for name in runtime if name.startswith(PREFIX) and Path(name).suffix in {'.dll', '.pyd'})):
        version = versions.get(path, '6.12.0')
        proof = f'source-{index}.txt'
        texts[proof] = ('SYNTHETIC upstream release document fixture: ' + version).encode()
        digest = hashlib.sha256(runtime[path]).hexdigest()
        facts[path] = {'sha256': digest, 'pe': {'status': 'measured', 'file_version': version + '.0', 'product_version': version + '.0'},
                       'origins': {'status': 'unknown', 'record_status': 'available', 'matches': []}}
        components.append({'path': path, 'sha256': digest, 'component': 'Synthetic component', 'version': version,
                           'sources': ['https://example.org/upstream/source/' + version], 'licenses': ['LICENSE.txt'],
                           'version_evidence': [proof], 'binary_evidence': copy.deepcopy(facts[path])})
    for name, data in texts.items(): (root / name).write_bytes(data)
    manifest = {'schema': SCHEMA, 'qt_release': '6.12.0', 'qualification': 'SYNTHETIC fixture; not reviewed real material',
                'components': components, 'material_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in texts.items()}}
    (root / 'native.json').write_text(json.dumps(manifest))
    return manifest, facts


class NativeMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)
        self.builder = load('build_portable')
        self.crt, self.binding, self.mesa = [PREFIX + name for name in ('vcruntime140.dll', 'QtCore.pyd', 'opengl32sw.dll')]
        self.runtime = {self.crt: b'CRT fixture', self.binding: b'binding fixture', self.mesa: b'Mesa fixture',
                        '_internal/shiboken6/shiboken6.pyd': b'outside unchanged scope'}
        self.inventory = {'build': {'Qt': '6.12.0'}, 'dependencies': [], 'build_dependencies': [],
                          'native_evidence': {'untrusted-cached': 'never verification'}}
        self.material = self.root / 'material'
        self.manifest, self.facts = material_fixture(self.material, self.runtime, {self.crt: '14.44.35211', self.mesa: 'Mesa-source-fixture'})
        for name in (self.binding, self.mesa): self.facts[name]['pe'] = {'status': 'absent'}
        self.facts[self.mesa]['origins'] = {'status': 'matched', 'record_status': 'available', 'matches': [
            {'name': 'PySide6_Essentials', 'version': '6.12.0', 'record_path': 'PySide6/opengl32sw.dll',
             'sha256': self.facts[self.mesa]['sha256']}]}
        for item in self.manifest['components']: item['binary_evidence'] = copy.deepcopy(self.facts[item['path']])
        self.prior = self.root / 'older.zip'; self.prior.write_bytes(b'prior artifact')
        (self.root / 'settings.json').write_bytes(b'private settings')
        (self.root / 'unqualified-native-old.json').write_bytes(b'prior report')

    def invoke(self, manifest=None, facts=None):
        (self.material / 'native.json').write_text(json.dumps(self.manifest if manifest is None else manifest))
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        collector = Mock(return_value=self.facts if facts is None else facts)
        out, err = StringIO(), StringIO()
        try:
            with patch.object(self.builder, '_load', return_value=SimpleNamespace(collect=collector)), redirect_stdout(out), redirect_stderr(err):
                return self.builder.collect_native(self.runtime, self.inventory, self.material)
        finally:
            self.assertEqual(out.getvalue(), ''); self.assertEqual(err.getvalue(), '')
            self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
            self.assertEqual(self.prior.read_bytes(), b'prior artifact')
            self.collector = collector

    def test_crt_source_version_qt_release_and_absent_binding_use_fresh_exact_facts(self):
        items, texts = self.invoke()
        self.assertEqual(items, self.manifest['components'])
        self.assertIn('14.44.35211', [item['version'] for item in items])
        self.assertEqual(next(item for item in items if item['path'] == self.binding)['binary_evidence']['pe'], {'status': 'absent'})
        self.collector.assert_called_once_with({name: self.runtime[name] for name in sorted(self.facts)}, self.inventory)
        self.assertEqual(texts['native/LICENSE.txt'], (self.material / 'LICENSE.txt').read_bytes())
        for item in items:
            for proof in item['version_evidence']:
                self.assertEqual(texts['native/' + proof], (self.material / proof).read_bytes())

    def test_mesa_owner_version_without_upstream_source_proof_is_rejected(self):
        item = next(item for item in self.manifest['components'] if item['path'] == self.mesa)
        item['version'] = '6.12.0'  # Owner version must NOT become Mesa source release.
        item['version_evidence'] = []
        with self.assertRaisesRegex(ValueError, '^Incomplete or mismatched native component provenance$'):
            self.invoke()
        self.collector.assert_not_called()

    def test_stale_pe_owner_or_bytes_and_unverifiable_current_facts_rejected(self):
        for change in ('pe', 'owner', 'absent', 'bytes', 'unknown', 'unavailable', 'record-unavailable', 'missing-fact'):
            with self.subTest(change=change):
                facts = copy.deepcopy(self.facts)
                if change == 'pe': facts[self.crt]['pe']['file_version'] = '14.51.36247.0'
                elif change == 'owner': facts[self.mesa]['origins']['matches'][0]['version'] = '6.13.0'
                elif change == 'absent': facts[self.binding]['pe'] = {'status': 'measured', 'file_version': '6.12.0.0', 'product_version': '6.12.0.0'}
                elif change == 'bytes': facts[self.crt]['sha256'] = '0' * 64
                elif change in {'unknown', 'unavailable'}: facts[self.binding]['pe'] = {'status': change}
                elif change == 'record-unavailable': facts[self.binding]['origins']['record_status'] = 'unavailable'
                else: del facts[self.binding]
                # Even declaring matching unavailable/unknown facts cannot admit them.
                manifest = copy.deepcopy(self.manifest)
                if change in {'unknown', 'unavailable', 'record-unavailable'}:
                    next(item for item in manifest['components'] if item['path'] == self.binding)['binary_evidence'] = copy.deepcopy(facts[self.binding])
                with self.assertRaisesRegex(ValueError, '^Native binary evidence does not match verifiable current facts$'):
                    self.invoke(manifest, facts)

    def test_complete_legacy_mapping_is_rejected_without_implicit_migration(self):
        legacy = {'qualification': 'legacy fixture', 'license_sha256': {'LICENSE.txt': self.manifest['material_sha256']['LICENSE.txt']},
                  'components': [{key: ('6.12.0' if key == 'version' else value) for key, value in item.items()
                                  if key not in {'version_evidence', 'binary_evidence'}} for item in self.manifest['components']]}
        with self.assertRaisesRegex(ValueError, '^Unsupported native material schema; expected marsdisplay-native-material-v2$'):
            self.invoke(legacy)
        self.collector.assert_not_called()

    def test_schema_scope_material_sources_and_hash_guards_precede_measurement(self):
        for change in ('legacy', 'diagnostic', 'unknown-schema', 'qt', 'missing', 'extra', 'duplicate', 'hash', 'runtime-bytes', 'license', 'proof', 'shared-proof', 'source', 'version', 'tamper', 'empty-license', 'empty-proof', 'unsafe', 'symlink'):
            with self.subTest(change=change):
                manifest = copy.deepcopy(self.manifest)
                item = manifest['components'][0]
                if change == 'legacy': manifest = {'qualification': 'legacy', 'components': [], 'license_sha256': {}}
                elif change == 'diagnostic': manifest = {'schema': 'marsdisplay-unqualified-native-v1', 'status': 'UNQUALIFIED'}
                elif change == 'unknown-schema': manifest['schema'] = 'unknown'
                elif change == 'qt': manifest['qt_release'] = '6.13.0'
                elif change == 'missing': manifest['components'].pop()
                elif change == 'extra': manifest['components'].append(dict(item, path='_internal/shiboken6/shiboken6.pyd'))
                elif change == 'duplicate': manifest['components'][-1] = copy.deepcopy(item)
                elif change == 'hash': item['sha256'] = '0' * 64
                elif change == 'license': item['licenses'] = []
                elif change == 'proof': item['version_evidence'] = ['missing.txt']
                elif change == 'shared-proof': item['version_evidence'] = item['licenses']
                elif change == 'source': item['sources'] = ['https://user:secret@example.org/source']
                elif change == 'version': item['version'] = 'private/source version'
                elif change == 'unsafe': manifest['material_sha256']['../escape.txt'] = '0' * 64
                license = self.material / 'LICENSE.txt'; original = license.read_bytes()
                proof = self.material / self.manifest['components'][0]['version_evidence'][0]
                proof_bytes = proof.read_bytes()
                runtime_bytes = self.runtime[item['path']]
                if change == 'runtime-bytes': self.runtime[item['path']] = b'changed current binary'
                if change == 'tamper': license.write_bytes(b'tampered')
                if change in {'empty-license', 'empty-proof'}:
                    target = license if change == 'empty-license' else proof
                    target.write_bytes(b'')
                    manifest['material_sha256'][target.name] = hashlib.sha256(b'').hexdigest()
                if change == 'symlink':
                    license.unlink(); license.symlink_to(self.prior)
                try:
                    with self.assertRaises(ValueError): self.invoke(manifest)
                    self.collector.assert_not_called()
                finally:
                    if license.is_symlink(): license.unlink()
                    license.write_bytes(original)
                    proof.write_bytes(proof_bytes)
                    self.runtime[item['path']] = runtime_bytes
