"""Portable public-CLI contract for measured native evidence (no host discovery)."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'packaging/linux/attribution.py'
ELF = b'\x7fELFfixture-native-bytes'


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = self.root / 'payload'
        self.build = self.root / 'build'
        self.output = self.root / 'result'
        self.payload.mkdir()
        self.build.mkdir()
        (self.payload / 'native.so').write_bytes(ELF)
        (self.payload / 'readme.txt').write_text('not native')
        for name, data in {'original.so': ELF, 'COPYING': b'license',
                           'owner.txt': b'exact owner metadata'}.items():
            (self.build / name).write_bytes(data)
        self.owner = {'kind': 'package', 'name': 'libexample', 'version': '1.2-3',
                      'source': {'name': 'example', 'version': '1.2-3',
                                 'reference': 'https://example.org/source/1.2-3'},
                      'licenses': ['COPYING'], 'evidence': ['owner.txt']}
        self.records = [{'file': 'native.so', 'original': 'original.so',
                         'owners': [self.owner]}]

    def invoke(self, expected, records=None):
        (self.build / 'evidence.json').write_text(json.dumps(
            {'schema_version': 1, 'records': self.records if records is None else records}))
        before = self.snapshot()
        run = subprocess.run([sys.executable, '-B', str(CLI), '--payload', str(self.payload),
                              '--build', str(self.build), '--output', str(self.output)],
                             capture_output=True, text=True)
        self.assertEqual((run.returncode, run.stdout, run.stderr), expected)
        self.assertEqual(self.snapshot(), before)
        return json.loads((self.output / 'inventory.json').read_text()) if self.output.exists() else None

    def snapshot(self):
        return {str(p): p.read_bytes() for root in (self.payload, self.build)
                for p in root.rglob('*') if p.is_file() and not p.is_symlink()}

    def unresolved(self, reason):
        result = self.invoke((1, 'measured=1 associated=0 unresolved=1\n', ''))
        self.assertEqual(result['unresolved'], [{'file': 'native.so', 'reason': reason}])
        self.assertEqual(result['files'], [])

    def test_exact_association_and_recorded_material(self):
        result = self.invoke((0, 'measured=1 associated=1 unresolved=0\n', ''))
        self.assertEqual(result['unresolved'], [])
        self.assertEqual(result['qualification'], 'Measured byte association; supplied ownership claims, not legal approval')
        record = result['files'][0]
        self.assertEqual(record['file'], 'native.so')
        self.assertEqual(record['original'], 'original.so')
        self.assertEqual(record['sha256'], hashlib.sha256(ELF).hexdigest())
        self.assertEqual(record['owner'], self.owner)
        self.assertEqual(record['materials'], {name: hashlib.sha256((self.build / name).read_bytes()).hexdigest()
                                              for name in ('COPYING', 'owner.txt')})

    def test_same_basename_is_not_equivalence(self):
        (self.build / 'original.so').write_bytes(ELF + b'changed')
        self.unresolved('original SHA256 differs from payload')

    def test_missing_mapping(self):
        self.records = []
        self.unresolved('acquire exact original-file mapping')

    def test_multiple_owners(self):
        self.records[0]['owners'].append(copy.deepcopy(self.owner))
        self.unresolved('acquire exactly one owner')

    def test_missing_original(self):
        self.records[0]['original'] = 'absent.so'
        self.unresolved('Missing selected material')

    def test_required_owner_fields(self):
        original = copy.deepcopy(self.owner)
        for field in ('name', 'version', 'source', 'licenses', 'evidence'):
            with self.subTest(field=field):
                self.records[0]['owners'][0] = dict(original, **{field: None})
                self.unresolved('acquire owner name/version, source name/version/reference, legal and ownership inputs')
                # Each invocation gets an independent output; never replace diagnostics.
                self.output = self.root / ('result-' + field)

    def test_source_reference_must_be_public(self):
        self.owner['source']['reference'] = 'https://user:password@example.org/src'
        self.unresolved('Missing public commit-pinned source provenance')

    def test_empty_legal_material(self):
        (self.build / 'COPYING').write_bytes(b'')
        self.unresolved('Duplicate path or empty/non-byte material')

    def test_missing_legal_material(self):
        self.owner['licenses'] = ['LICENSE-missing']
        self.unresolved('Missing selected material')

    def test_unknown_owner_kind(self):
        self.owner['kind'] = 'basename-candidate'
        self.unresolved('unsupported owner kind')

    def test_unsafe_mapping_rejected_before_output(self):
        self.records[0]['original'] = '../outside.so'
        self.invoke((2, '', 'attribution: Unsafe payload path\n'))
        self.assertFalse(self.output.exists())

    def test_duplicate_mapping_rejected_before_output(self):
        self.records.append(copy.deepcopy(self.records[0]))
        self.invoke((2, '', 'attribution: duplicate payload mapping\n'))
        self.assertFalse(self.output.exists())

    def test_existing_output_untouched(self):
        self.output.mkdir()
        (self.output / 'inventory.json').write_text('{}')
        self.invoke((2, '', 'attribution: output must not exist\n'))
        self.assertEqual((self.output / 'inventory.json').read_text(), '{}')

    def test_output_overlap(self):
        self.output = self.build / 'result'
        self.invoke((2, '', 'attribution: output overlaps input\n'))
        self.assertFalse(self.output.exists())

    def test_no_elf_is_not_coverage(self):
        (self.payload / 'native.so').write_bytes(b'not ELF')
        self.invoke((2, '', 'attribution: payload contains no ELF files\n'))
        self.assertFalse(self.output.exists())


class SymlinkTests(AttributionTests):
    def test_symlink_escape_rejected(self):
        (self.payload / 'escape.so').symlink_to(self.build / 'original.so')
        self.invoke((2, '', 'attribution: Symlink material or parent\n'))
        self.assertFalse(self.output.exists())


def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromTestCase(AttributionTests)
    # Windows hosts may lack symlink privileges; do not add platform skips.
    if sys.platform != 'win32':
        suite.addTest(SymlinkTests('test_symlink_escape_rejected'))
    return suite
