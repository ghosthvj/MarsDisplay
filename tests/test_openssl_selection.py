"""OpenSSL selection is bounded, redacted evidence, never qualification."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_packaging_payload import load


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.module = load('openssl_selection')
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.data = b'MZ isolated OpenSSL fixture'
        self.roots = {'cpython-sdk': self.root}
        self.entries = []
        self.runtime = {}
        for name in self.module.NAMES:
            source = self.root / name
            source.write_bytes(self.data)
            self.entries.append((name, str(source), 'BINARY'))
            self.runtime['_internal/' + name] = self.data

    def test_four_selected_sources_bind_exact_packaged_bytes_without_paths(self):
        sidecar = self.root / 'selection.json'
        self.module.write(sidecar, self.entries, roots=self.roots)
        result = self.module.read(sidecar, self.runtime)
        expected = {name: {'status': 'matched', 'location': 'cpython-sdk',
                           'sha256': hashlib.sha256(self.data).hexdigest()}
                    for name in self.module.NAMES}
        self.assertEqual(result, {'status': 'UNQUALIFIED', 'files': expected})
        self.assertNotIn(str(self.root), sidecar.read_text())
        self.assertLess(sidecar.stat().st_size, 4096)
        before = sidecar.read_bytes()
        with self.assertRaises(FileExistsError):
            self.module.write(sidecar, self.entries, roots=self.roots)
        self.assertEqual(sidecar.read_bytes(), before)

    def test_default_runner_locations_classify_without_claiming_a_supplier(self):
        name = self.module.NAMES[0]
        programs, cache = self.root / 'programs', self.root / 'cache'
        locations = {'openssl-install': programs / 'OpenSSL/bin',
                     'git-install': programs / 'Git/mingw64/bin',
                     'ruby-toolcache': cache / 'Ruby/3.4.7/x64/bin'}
        with (patch.object(self.module.sys, 'platform', 'win32'),
              patch.dict(self.module.os.environ, {'ProgramFiles': str(programs),
                                                  'SystemDrive': 'X:',
                                                  'RUNNER_TOOL_CACHE': str(cache)}, clear=True),
              patch.object(self.module.metadata, 'distribution', side_effect=ValueError('private'))):
            for location, directory in locations.items():
                with self.subTest(location=location):
                    directory.mkdir(parents=True)
                    source = directory / name
                    source.write_bytes(self.data)
                    result = self.module.capture([(name, str(source), 'BINARY')])
                    self.assertEqual(result[name]['location'], location)
                    self.assertEqual(result[name]['source_sha256'], hashlib.sha256(self.data).hexdigest())
                    self.assertNotIn(str(self.root), json.dumps(result))

    def test_unknown_source_is_redacted_without_opening_it(self):
        name = self.module.NAMES[0]
        entries = [(name, str(self.root / 'private-secret' / name), 'BINARY')]
        with patch.object(Path, 'open', side_effect=AssertionError('No unknown source read')):
            result = self.module.capture(entries, roots=self.roots)
        self.assertEqual(result[name], {'status': 'unknown_location'})
        self.assertNotIn('private', json.dumps(result))

    def test_unrelated_entries_are_ignored_and_duplicates_are_ambiguous(self):
        entry = self.entries[0]
        result = self.module.capture([entry, entry, ('private-secret.dll', '/private', 'BINARY')],
                                     roots=self.roots)
        self.assertEqual(result[entry[0]], {'status': 'ambiguous'})
        self.assertEqual(set(result), set(self.module.NAMES))
        self.assertNotIn('private', json.dumps(result))

    def test_invalid_type_destination_and_non_pe_source_do_not_produce_matches(self):
        name, source, _ = self.entries[0]
        for entry in [(name, source, 'DATA'), ('../' + name, source, 'BINARY'),
                      (name, source + ':secret', 'BINARY')]:
            with self.subTest(entry=entry):
                result = self.module.capture([entry], roots=self.roots)
                self.assertNotEqual(result[name].get('status'), 'selected')
        Path(source).write_bytes(b'private non-PE bytes')
        self.assertEqual(self.module.capture(self.entries, roots=self.roots)[name],
                         {'status': 'unavailable'})

    def test_source_missing_oversized_or_reparse_point_is_not_read(self):
        name, source, _ = self.entries[0]
        source = Path(source)
        source.unlink()
        self.assertEqual(self.module.capture(self.entries, roots=self.roots)[name],
                         {'status': 'unavailable'})
        source.write_bytes(self.data)
        with patch.object(self.module, 'DLL_LIMIT', 1):
            self.assertEqual(self.module.capture(self.entries, roots=self.roots)[name],
                             {'status': 'unavailable'})
        with patch.object(Path, 'is_junction', return_value=True):
            with patch.object(Path, 'open', side_effect=AssertionError('No linked source read')):
                self.assertEqual(self.module.capture(self.entries, roots=self.roots)[name],
                                 {'status': 'unavailable'})

    def test_missing_malformed_oversized_or_linked_sidecar_is_unavailable(self):
        sidecar = self.root / 'selection.json'
        self.assertEqual(self.module.read(sidecar, self.runtime), {'status': 'unavailable'})
        for data in (b'private-secret', b'[' * 4097, b'{"schema": 2}', b'{"schema":1,"files":[]}'):
            with self.subTest(data=data[:20]):
                sidecar.write_bytes(data)
                self.assertEqual(self.module.read(sidecar, self.runtime), {'status': 'unavailable'})
        self.module.write(self.root / 'valid.json', self.entries, roots=self.roots)
        with patch.object(Path, 'is_junction', return_value=True):
            self.assertEqual(self.module.read(self.root / 'valid.json', self.runtime),
                             {'status': 'unavailable'})

    def test_changed_source_or_tampered_metadata_never_exports_unbound_values(self):
        sidecar = self.root / 'selection.json'
        self.module.write(sidecar, self.entries, roots=self.roots)
        captured = json.loads(sidecar.read_bytes())
        name = self.module.NAMES[0]
        self.runtime['_internal/' + name] = b'MZ changed packaged bytes'
        self.assertEqual(self.module.read(sidecar, self.runtime)['files'][name],
                         {'status': 'hash_mismatch'})
        captured['files'][name]['location'] = 'private-secret-C:/SDK'
        captured['files'][name]['exception'] = 'private-secret'
        sidecar.write_text(json.dumps(captured))
        result = self.module.read(sidecar, self.runtime)
        self.assertEqual(result['files'][name], {'status': 'unavailable'})
        self.assertNotIn('private', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
