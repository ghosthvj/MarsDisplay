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
                if isinstance(name, str):
                    member = zipfile.ZipInfo('fixture')
                    member.filename = name  # Preserve intentionally malformed archive bytes.
                    name = member
                archive.writestr(name, content)
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual([member.orig_filename for member in archive.infolist()[1:]],
                             [name if isinstance(name, str) else name.filename for name, _ in extra])
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
        for index, entries in enumerate(cases):
            target = self.root / f'case-{index}'
            with self.subTest(entries=entries), self.fixture(entries):
                before = self.archive.read_bytes()
                with self.assertRaises(ValueError):
                    self.module.prepare('fixture', self.archive, target)
                self.assertFalse(target.exists())
                self.assertEqual(self.archive.read_bytes(), before)

    def test_raw_names_are_rejected_before_zip_normalization_can_hide_them(self):
        for separator in ('/', '\\'):
            for index, name in enumerate(('dir\\escape', 'dir\x00hidden')):
                target = self.root / f'raw-{ord(separator)}-{index}'
                with (self.subTest(separator=separator, name=name),
                      patch.object(zipfile.os, 'sep', separator), self.fixture([(name, b'x')])):
                    before = self.archive.read_bytes()
                    with self.assertRaises(ValueError) as caught:
                        self.module.prepare('fixture', self.archive, target)
                    if separator == '\\' or '\x00' in name:
                        self.assertEqual(str(caught.exception), 'Tool archive member name was normalized')
                    self.assertFalse(target.exists())
                    self.assertEqual(self.archive.read_bytes(), before)

    def test_raw_writer_and_independent_reader(self):
        for sep in ('/', '\\'):
            for index, name in enumerate(
                    ('extra/file', 'extra\\file', 'extra\x00file')):
                with self.subTest(separator=sep, name=name):
                    target = self.root / f'probe-{ord(sep)}-{index}'
                    with self.fixture([(name, b'preserved')]):
                        before = hashlib.sha256(self.archive.read_bytes()).digest()
                        with patch.object(zipfile.os, 'sep', sep):
                            if index == 0:
                                result = self.module.prepare(
                                    'fixture', self.archive, target)
                                self.assertEqual(
                                    result.read_bytes(), b'MZ fixture tool')
                                self.assertEqual(
                                    (target / 'extra/file').read_bytes(),
                                    b'preserved')
                            else:
                                message = (
                                    'Tool archive member name was normalized'
                                    if sep == '\\' or index == 2
                                    else 'Unsafe source archive path')
                                with self.assertRaises(ValueError) as caught:
                                    self.module.prepare(
                                        'fixture', self.archive, target)
                                self.assertEqual(str(caught.exception), message)
                                self.assertFalse(target.exists())
                        self.assertEqual(
                            hashlib.sha256(self.archive.read_bytes()).digest(),
                            before)

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
