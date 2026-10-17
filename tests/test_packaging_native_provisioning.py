"""Source and explicitly SYNTHETIC provider tests; no Windows/legal qualification."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_packaging_payload import load
import test_packaging_build as build_fixtures

ROOT = Path(__file__).resolve().parents[1]
PREFIX = '_internal/PySide6/'


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def synthetic_inputs(repo):
    """Small fixture with substituted trust anchors, NEVER real qualification."""
    real = json.loads((ROOT / 'third_party/native-material/provenance.json').read_bytes())
    registry = dict(schema=real['schema'], modules=real['modules'], openssl=real['openssl'], files=[], declared_license_files=[])
    texts = {'README.md': b'SYNTHETIC source-access fixture, not genuine material'}
    groups = dict(real['modules']) | {'openssl-' + v: dict(item, repository='openssl/openssl', release=v)
                                       for v, item in real['openssl'].items()}
    for module, item in groups.items():
        for source_path, kind, data in [('LICENSE.txt', 'license', b'SYNTHETIC license ' + module.encode()),
                                       ('@release-' + module, 'release-reference', encoded({
                                           'sha': 'a' * 40, 'object': {'sha': item['commit'], 'type': 'commit'},
                                           'tag': ('openssl-' if module.startswith('openssl-') else 'v') + item['release'],
                                           'url': f"https://api.github.com/repos/{item['repository']}/git/tags/" + 'a' * 40}))]:
            name = 'raw/' + digest(data) + '.txt'; texts[name] = data
            record = dict(module=module, source_commit=item['commit'], source_path=source_path,
                          kind=kind, path=name, sha256=digest(data))
            if kind == 'release-reference':
                record['source_url'] = json.loads(data)['url']
                (registry['openssl'][item['release']] if module.startswith('openssl-') else registry['modules'][module])['release_reference'] = name
            else:
                record['git_blob_sha1'] = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                record['source_url'] = f"https://raw.githubusercontent.com/{item['repository']}/{item['commit']}/{source_path}"
            registry['files'].append(record)
    paths = [(PREFIX + 'Qt6Core.dll', 'qtbase', 'PySide6_Essentials'),
             (PREFIX + 'QtCore.pyd', 'pyside', 'PySide6_Essentials'),
             (PREFIX + 'plugins/imageformats/qicns.dll', 'qtimageformats', 'PySide6_Essentials'),
             (PREFIX + 'plugins/platforms/qwindows.dll', 'qtbase', 'PySide6_Essentials'),
             ('_internal/shiboken6/Shiboken.pyd', 'pyside', 'shiboken6'),
             ('_internal/shiboken6/shiboken6.abi3.dll', 'pyside', 'shiboken6'),
             ('_internal/libcrypto-3-x64.dll', 'openssl-3.5.5', None),
             ('_internal/libssl-3-x64.dll', 'openssl-3.5.5', None),
             ('_internal/libcrypto-3.dll', 'openssl-3.5.9', None),
             ('_internal/libssl-3.dll', 'openssl-3.5.9', None)]
    runtime, components, supplemental, facts = {}, [], [], {}
    for path, module, owner in paths:
        data = b'SYNTHETIC non-executable ' + path.encode(); runtime[path] = data
        version = module.removeprefix('openssl-') if owner is None else '6.12.0'
        pe = {'status': 'absent'} if module == 'pyside' else dict(status='measured', file_version=version + '.0', product_version=version + '.0')
        association = dict(name=owner, version='6.12.0', record_path=path.removeprefix('_internal/'), sha256=digest(data)) if owner else None
        item = dict(path=path, module=module, sha256=digest(data), pe=pe, owner=association)
        (components if path.startswith(PREFIX) else supplemental).append(item)
        facts[path] = dict(sha256=digest(data), pe=pe, origins=dict(status='matched' if owner else 'unknown', record_status='available', matches=[association] if owner else []))
    texts['provenance.json'] = encoded(registry)
    policy = dict(schema='marsdisplay-native-source-policy-v1', registry_sha256=digest(texts['provenance.json']),
                  qt_release='6.12.0', qualification='SYNTHETIC policy, not actual qualification',
                  components=components, supplemental=supplemental)
    texts['policy.json'] = encoded(policy)
    root = repo / 'third_party/native-material'
    for name, data in texts.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    return root, policy, runtime, facts


class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.repo = Path(self.temporary)
        self.builder = load('build_portable')

    def fixture(self):
        module = self.builder.native_material
        root, policy, runtime, facts = synthetic_inputs(self.repo)
        self.enterContext(patch.object(module, 'REGISTRY_SHA256', digest((root / 'provenance.json').read_bytes())))
        self.enterContext(patch.object(module, 'POLICY_SHA256', digest((root / 'policy.json').read_bytes())))
        return module, root, policy, runtime, facts

    def unchanged(self):
        return {p.relative_to(self.repo): p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}

    def test_present_invalid_source_root_is_not_silently_ignored(self):
        root = self.repo / 'third_party/native-material'; root.mkdir(parents=True)
        (root / 'provenance.json').write_bytes(b'{}')
        before = self.unchanged()
        with self.assertRaises(ValueError): self.builder.payload.collect_source(self.repo)
        self.assertEqual(self.unchanged(), before)

    def test_missing_verified_inputs_fail_before_any_sdk_process_or_directory(self):
        before = self.unchanged(); run = Mock()
        with patch.object(self.builder, 'require_host'), self.assertRaisesRegex(ValueError, '^Missing verified native sources: third_party/native-material; Windows qualification is pending$'):
            self.builder.build(self.repo, run=run)
        run.assert_not_called(); self.assertEqual(self.unchanged(), before)
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_real_reader_preserves_all_raw_and_explicit_source_coverage_then_rejects_corruption(self):
        module = self.builder.native_material
        bundle = module.read_inputs(ROOT)
        self.assertEqual(len(bundle['registry']['files']), 233)
        self.assertEqual(len([p for p in bundle['files'] if p.startswith('raw/')]), 204)
        source = self.builder.payload.collect_source(ROOT)
        for name, data in bundle['files'].items(): self.assertEqual(source['third_party/native-material/' + name], data)
        for name, data in bundle['files'].items():
            path = self.repo / 'third_party/native-material' / name
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        root = self.repo / 'third_party/native-material'
        for target, replacement in [('policy.json', b'{}'), ('provenance.json', b'{}'),
                                    (bundle['registry']['files'][0]['path'], b'changed raw bytes')]:
            with self.subTest(target=target):
                original = (root / target).read_bytes(); (root / target).write_bytes(replacement)
                before = self.unchanged(); run = Mock()
                with patch.object(self.builder, 'require_host'), self.assertRaisesRegex(ValueError, '^Invalid verified native sources or policy$'):
                    self.builder.build(self.repo, run=run)
                run.assert_not_called(); self.assertEqual(self.unchanged(), before)
                (root / target).write_bytes(original)

    def test_release_blob_declared_license_and_private_url_reject_under_synthetic_anchors(self):
        module, root, policy, runtime, facts = self.fixture()
        original = (root / 'provenance.json').read_bytes()
        for change in ('release', 'blob', 'declared-license', 'private-url', 'duplicate'):
            with self.subTest(change=change):
                registry = json.loads(original)
                record = next(item for item in registry['files'] if item['kind'] == ('release-reference' if change == 'release' else 'license'))
                if change == 'release':
                    tag = json.loads((root / record['path']).read_bytes()); tag['object']['sha'] = '0' * 40
                    raw = encoded(tag); old_path = record['path']; record['sha256'] = digest(raw)
                    record['path'] = 'raw/' + digest(raw) + '.txt'; (root / record['path']).write_bytes(raw)
                    for group in [registry['modules'], registry['openssl']]:
                        for item in group.values():
                            if item['release_reference'] == old_path: item['release_reference'] = record['path']
                elif change == 'blob': record['git_blob_sha1'] = '0' * 40
                elif change == 'declared-license': registry['declared_license_files'] = [dict(module='qtbase', attribution='missing.json', license_file='LICENSE.txt')]
                elif change == 'private-url': record['source_url'] = 'https://user:secret@example.org/private'
                else: registry['files'].append(copy.deepcopy(record))
                data = encoded(registry); (root / 'provenance.json').write_bytes(data)
                updated = dict(policy, registry_sha256=digest(data)); (root / 'policy.json').write_bytes(encoded(updated))
                before = self.unchanged()
                with patch.object(module, 'REGISTRY_SHA256', digest(data)), patch.object(module, 'POLICY_SHA256', digest(encoded(updated))), self.assertRaisesRegex(ValueError, '^Invalid verified native sources or policy$'):
                    module.read_inputs(self.repo)
                self.assertEqual(self.unchanged(), before)

    def test_sdk_record_and_qt_admission_is_fresh_and_fail_closed(self):
        module, root, policy, runtime, facts = self.fixture()
        inventory = dict(build={'Qt': '6.12.0'}, dependencies=[dict(name=n, version='6.12.0') for n in ('PySide6_Essentials', 'shiboken6')])
        class Entry(str): pass
        def lookup(name):
            owner_name = 'shiboken6' if name == 'shiboken6' else 'PySide6_Essentials'
            entries = []
            for item in policy['components'] + policy['supplemental']:
                if item['owner'] and item['owner']['name'] == owner_name:
                    entry = Entry(item['owner']['record_path'])
                    entry.hash = SimpleNamespace(mode='sha256', value=base64.urlsafe_b64encode(bytes.fromhex(item['sha256'])).decode().rstrip('='))
                    entries.append(entry)
            return SimpleNamespace(metadata={'Name': owner_name}, version='6.12.0', files=entries)
        before = self.unchanged()
        with patch.object(module.metadata, 'distribution', side_effect=lookup): module.preflight(self.repo, inventory)
        for change in ('Qt', 'hash', 'owner', 'path'):
            with self.subTest(change=change):
                def stale(name):
                    dist = lookup(name)
                    if change == 'hash': dist.files[0].hash.value = 'A' * 43
                    if change == 'owner': dist.version = '6.13.0'
                    if change == 'path': dist.files[0] = Entry('unexpected.dll')
                    return dist
                info = copy.deepcopy(inventory)
                if change == 'Qt': info['build']['Qt'] = '6.13.0'
                with patch.object(module.metadata, 'distribution', side_effect=stale), self.assertRaises(ValueError): module.preflight(self.repo, info)
        self.assertEqual(self.unchanged(), before)

    def test_materialization_checks_fresh_facts_before_exclusive_stage_and_unchanged_gate(self):
        module, root, policy, runtime, facts = self.fixture()
        inventory = dict(build={'Qt': '6.12.0'})
        collector = Mock(side_effect=lambda data, _: {k: v for k, v in facts.items() if k in data})
        evidence = SimpleNamespace(collect=collector)
        prior = self.repo / 'dist/older.zip'; prior.parent.mkdir(); prior.write_bytes(b'previous artifact')
        destination = self.repo / 'owned-stage'; before = self.unchanged()
        with patch.object(module, '_load', return_value=evidence): module.prepare(self.repo, runtime, inventory, destination)
        with patch.object(self.builder, '_load', return_value=evidence): components, texts = self.builder.collect_native(runtime, inventory, destination)
        self.assertEqual(len(components), 4)
        self.assertEqual(collector.call_count, 2)  # Independent fresh call in unchanged gate.
        self.assertIn('native/SOURCE-ACCESS.txt', texts)
        self.assertIn('native/supplemental.json', texts)
        for item in components:
            self.assertFalse(set(item['licenses']) & set(item['version_evidence']))
            self.assertEqual(item['binary_evidence'], facts[item['path']])
        self.assertIn(b'complete', texts['native/SOURCE-ACCESS.txt'])
        with patch.object(module, '_load', return_value=evidence), self.assertRaises(FileExistsError): module.prepare(self.repo, runtime, inventory, destination)
        self.assertEqual({name: self.unchanged()[name] for name in before}, before)
        for change in ('path', 'shiboken-path', 'ssl-path', 'bytes', 'pe', 'owner', 'missing', 'supplemental'):
            with self.subTest(change=change):
                data, fresh = dict(runtime), copy.deepcopy(facts)
                key = next(iter(runtime))
                if change == 'path': data[PREFIX + 'unknown.dll'] = b'unknown'
                elif change == 'shiboken-path': data['_internal/shiboken6/unknown.dll'] = b'unknown'
                elif change == 'ssl-path': data['_internal/libssl-unknown.dll'] = b'unknown'
                elif change == 'bytes': data[key] = b'changed'
                elif change == 'pe': fresh[key]['pe'] = {'status': 'absent'}
                elif change == 'owner': fresh[key]['origins']['matches'] = []
                elif change == 'missing': del fresh[key]
                else: fresh['_internal/libssl-3.dll']['pe'] = {'status': 'unavailable'}
                collector.side_effect = lambda data, _: {k: v for k, v in fresh.items() if k in data}
                target = self.repo / ('rejected-' + change)
                with patch.object(module, '_load', return_value=evidence), self.assertRaises(ValueError): module.prepare(self.repo, data, inventory, target)
                self.assertFalse(target.exists())
        self.assertEqual({name: self.unchanged()[name] for name in before}, before)

    def test_default_builder_materializes_after_smoke_and_publishes_once(self):
        fixture = build_fixtures.BuildTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.repo, self.builder = fixture.repo, fixture.builder
        module, root, policy, runtime, facts = self.fixture()
        fixture.runtime = {p: b for p, b in fixture.runtime.items() if not p.startswith(PREFIX)} | runtime
        fixture.source.update({'third_party/native-material/' + name: data
                               for name, data in self.builder.payload.read_tree(root).items()})
        fixture.source['packaging/PORTABLE-README.txt'] = (ROOT / 'packaging/PORTABLE-README.txt').read_bytes()
        prior = self.repo / 'dist/older.zip'; prior.parent.mkdir(); prior.write_bytes(b'previous artifact')
        evidence = SimpleNamespace(collect=Mock(side_effect=lambda data, _: {k: v for k, v in facts.items() if k in data}))
        def inspect(repo):
            fixture.events.append('inspect'); return copy.deepcopy(fixture.info), {'SDK/LICENSE': b'SDK fixture'}
        def smoke(folder, scratch):
            fixture.events.append('smoke')
            self.assertFalse(any((self.repo / 'build').rglob('native.json')))
            return {'Node': 'v24.fixture'}
        assemble = self.builder.payload.assemble
        def publish(*args): fixture.events.append('publish'); return assemble(*args)
        with patch.object(self.builder, 'require_host'), patch.object(self.builder, 'inspect_environment', side_effect=inspect), patch.object(self.builder.payload, 'collect_source', return_value=fixture.source), patch.object(self.builder.payload, 'assemble', side_effect=publish), patch.object(module, '_load', return_value=evidence), patch.object(self.builder, '_load', return_value=evidence):
            folder, archive, checksum = self.builder.build(self.repo, run=fixture.process, smoke_check=smoke)
        self.assertEqual(fixture.events, ['inspect', 'compile', 'smoke', 'publish'])
        self.assertEqual(len(json.loads((folder / 'inventory.json').read_bytes())['native_components']), 4)
        self.assertTrue((folder / 'notices/native/SOURCE-ACCESS.txt').is_file())
        self.assertTrue((folder / 'source/third_party/native-material/policy.json').is_file())
        self.assertEqual((folder / 'README.txt').read_bytes(), fixture.source['packaging/PORTABLE-README.txt'])
        self.assertTrue(archive.is_file() and checksum.is_file())
        self.assertEqual(prior.read_bytes(), b'previous artifact')
        self.assertEqual(list((self.repo / 'build').iterdir()), [])
