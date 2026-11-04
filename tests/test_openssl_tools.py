"""Portable build tools must come from the explicit pinned archives."""
import hashlib
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch
import zipfile

from test_packaging_payload import load


class OpenSSLToolTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(sys.modules, {'openssl_inputs': load('openssl_inputs')}):
            self.module = load('openssl_tools')
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.archive = self.root / 'tool.zip'
        self.target = self.root / 'tools'

    def fixture(self, extra=()):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('bin/tool.exe', b'MZ fixture tool')
            for name, content in extra:
                archive.writestr(name, content)
        record = {'sha256': hashlib.sha256(self.archive.read_bytes()).hexdigest(),
                  'size': self.archive.stat().st_size, 'executable': 'bin/tool.exe'}
        return patch.dict(self.module.TOOLS, {'fixture': record})

    def test_pinned_tool_extracts_without_changing_archive(self):
        with self.fixture():
            before = self.archive.read_bytes()
            executable = self.module.prepare('fixture', self.archive, self.target)
            self.assertEqual(executable, self.target / 'bin/tool.exe')
            self.assertEqual(executable.read_bytes(), b'MZ fixture tool')
            self.assertEqual(self.archive.read_bytes(), before)

    def test_unknown_tool_and_changed_archive_leave_output_absent(self):
        with self.fixture():
            with self.assertRaisesRegex(ValueError, '^Unknown controlled build tool$'):
                self.module.prepare('ambient', self.archive, self.target)
            self.archive.write_bytes(self.archive.read_bytes() + b'tamper')
            before = self.archive.read_bytes()
            with self.assertRaisesRegex(ValueError, '^Controlled tool archive mismatch$'):
                self.module.prepare('fixture', self.archive, self.target)
            self.assertEqual(self.archive.read_bytes(), before)
            self.assertFalse(self.target.exists())

    def test_namespace_collisions_and_links_fail_before_creating_output(self):
        link = zipfile.ZipInfo('link')
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        cases = [[(name, b'x')] for name in ('../escape', '/absolute', 'COM¹.txt',
                 'CONOUT$', 'bad?.exe', 'trailing.', 'dir\\escape', 'C:escape')]
        cases += [[('BIN/other', b'x')], [('a', b'x'), ('a/b', b'y')], [(link, b'target')]]
        for entries in cases:
            with self.subTest(entries=entries), self.fixture(entries):
                before = self.archive.read_bytes()
                with self.assertRaises(ValueError):
                    self.module.prepare('fixture', self.archive, self.target)
                self.assertFalse(self.target.exists())
                self.assertEqual(self.archive.read_bytes(), before)

    def test_existing_output_bounds_and_linked_input_are_preserved(self):
        with self.fixture():
            self.target.mkdir()
            marker = self.target / 'human.txt'
            marker.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):
                self.module.prepare('fixture', self.archive, self.target)
            self.assertEqual(marker.read_bytes(), b'keep')
            for field, limit in (('MAX_ARCHIVE', 1), ('MAX_FILES', 0), ('MAX_EXPANDED', 1)):
                with patch.object(self.module, field, limit):
                    with self.assertRaises(ValueError):
                        self.module.prepare('fixture', self.archive, self.root / 'new')
                self.assertFalse((self.root / 'new').exists())
            with (patch.object(Path, 'is_junction', return_value=True),
                  patch.object(Path, 'open', side_effect=AssertionError('Unexpected read'))):
                with self.assertRaises(ValueError):
                    self.module.prepare('fixture', self.archive, self.root / 'new')
            self.assertFalse((self.root / 'new').exists())
