"""Controlled build inputs are verified before creating an output tree."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from test_packaging_payload import load

VERSION = (b'MAJOR=3\nMINOR=5\nPATCH=9\nPRE_RELEASE_TAG=\nBUILD_METADATA=\n'
           b'RELEASE_DATE="29 Sep 2026"\nSHLIB_VERSION=3\n')


class OpenSSLInputTests(unittest.TestCase):
    def setUp(self):
        self.module = load('openssl_inputs')
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.archive = self.root / 'source.tar.gz'
        self.target = self.root / 'source'

    def fixture(self, extra=(), version=VERSION):
        entries = [('VERSION.dat', version, tarfile.REGTYPE), *extra]
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, data, kind in entries:
                member = tarfile.TarInfo(self.module.SOURCE_ROOT + '/' + name)
                member.type = kind
                member.size = len(data) if kind == tarfile.REGTYPE else 0
                member.linkname = '../../outside'
                archive.addfile(member, io.BytesIO(data))
        return patch.object(self.module, 'SOURCE_SHA256',
                            hashlib.sha256(self.archive.read_bytes()).hexdigest())

    def test_exact_source_and_version_are_extracted_without_modifying_archive(self):
        with self.fixture([('crypto/sample.c', b'known source', tarfile.REGTYPE)]):
            before = self.archive.read_bytes()
            self.assertEqual(self.module.extract_source(self.archive, self.target), self.target)
            self.assertEqual((self.target / 'VERSION.dat').read_bytes(), VERSION)
            self.assertEqual((self.target / 'crypto/sample.c').read_bytes(), b'known source')
            self.assertEqual(self.archive.read_bytes(), before)

    def test_digest_and_version_mismatch_leave_destination_absent(self):
        self.fixture()
        with self.assertRaisesRegex(ValueError, '^OpenSSL source digest mismatch$'):
            self.module.extract_source(self.archive, self.target)
        self.assertFalse(self.target.exists())
        with self.fixture(version=b'wrong version'):
            with self.assertRaisesRegex(ValueError, '^OpenSSL version input mismatch$'):
                self.module.extract_source(self.archive, self.target)
        self.assertFalse(self.target.exists())

    def test_unsafe_members_and_windows_aliases_are_rejected_before_writing(self):
        cases = [[(name, b'x', tarfile.REGTYPE)] for name in
                 ('../escape', 'C:escape', 'dir\\escape', 'NUL.txt', 'trailing.', 'a//b')]
        cases += [[('link', b'', kind)] for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE)]
        cases += [[('same', b'a', tarfile.REGTYPE), ('SAME', b'b', tarfile.REGTYPE)],
                  [('parent', b'a', tarfile.REGTYPE), ('parent/child', b'b', tarfile.REGTYPE)]]
        for entries in cases:
            with self.subTest(entries=entries), self.fixture(entries):
                with self.assertRaises(ValueError):
                    self.module.extract_source(self.archive, self.target)
                self.assertFalse(self.target.exists())
        self.assertFalse((self.root / 'escape').exists())

    def test_existing_output_and_oversized_input_are_not_modified(self):
        with self.fixture():
            self.target.mkdir()
            marker = self.target / 'human.txt'
            marker.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):
                self.module.extract_source(self.archive, self.target)
            self.assertEqual(marker.read_bytes(), b'keep')
            with patch.object(self.module, 'MAX_ARCHIVE', 1):
                with self.assertRaisesRegex(ValueError, '^Input exceeds size limit$'):
                    self.module.extract_source(self.archive, self.root / 'other')
            self.assertFalse((self.root / 'other').exists())

    def test_tree_fingerprint_is_location_independent_and_detects_changed_bytes(self):
        roots = [self.root / 'first', self.root / 'different-location']
        for root in roots:
            root.mkdir()
            (root / 'tool.exe').write_bytes(b'compiler')
        before = self.module.fingerprint(roots[0])
        self.assertEqual(before, self.module.fingerprint(roots[1]))
        self.assertEqual(before['files'], 1)
        self.assertEqual(before['bytes'], 8)
        self.assertNotIn(str(self.root), str(before))
        (roots[1] / 'tool.exe').write_bytes(b'tampered')
        self.assertNotEqual(before, self.module.fingerprint(roots[1]))

    def reject(self, entries, message):
        with self.fixture(entries):
            before = self.archive.read_bytes()
            with self.assertRaisesRegex(ValueError, '^' + message + '$'):
                self.module.extract_source(self.archive, self.target)
            self.assertFalse(self.target.exists())
            self.assertEqual(self.archive.read_bytes(), before)

    def test_additional_namespace_boundaries(self):
        for index, name in enumerate(('COM¹.txt', 'LPT²', 'CONIN$', 'CONOUT$',
                                      'bad?.c', 'bad*.c', 'bad<c', 'bad>c', 'bad|c', 'bad"c')):
            with self.subTest(name=name):
                self.target = self.root / f'output-{index}'
                self.reject([(name, b'x', tarfile.REGTYPE)], 'Unsafe source archive path')

    def test_limits_and_prefix_collisions(self):
        self.reject([('a/x', b'x', tarfile.REGTYPE), ('A/y', b'y', tarfile.REGTYPE)],
                    'Ambiguous source archive path')
        self.reject([('x', b'x', tarfile.FIFOTYPE)], 'Source archive contains unsupported entries')
        for field, value, message in (
                ('MAX_FILES', 1, 'Source archive exceeds entry limit'),
                ('MAX_SOURCE_FILE', 1, 'Source archive member exceeds size limit'),
                ('MAX_EXPANDED', 1, 'Source archive exceeds expanded size limit')):
            with patch.object(self.module, field, value):
                self.reject([('x', b'x', tarfile.REGTYPE)], message)

    def test_links_errors_and_tree_bounds(self):
        tree = self.root / 'tools'
        tree.mkdir()
        (tree / 'tool').write_bytes(b'abc')
        for field, value, message in (
                ('MAX_FILES', 0, 'Build input tree exceeds entry limit'),
                ('MAX_TREE', 2, 'Build input tree exceeds size limit')):
            with patch.object(self.module, field, value):
                with self.assertRaisesRegex(ValueError, '^' + message + '$'):
                    self.module.fingerprint(tree)
        with patch.object(self.module, 'MAX_TREE', 3):
            self.assertEqual(self.module.fingerprint(tree)['bytes'], 3)

        def unreadable(*args, **kwargs):
            kwargs['onerror'](PermissionError('unreadable tree'))
            return iter(())

        with patch.object(self.module.os, 'walk', side_effect=unreadable):
            with self.assertRaisesRegex(PermissionError, '^unreadable tree$'):
                self.module.fingerprint(tree)
        # No Windows symlink privilege or new platform skip is required.
        for method in ('is_junction', 'is_symlink'):
            with patch.object(Path, method, return_value=True):
                with self.assertRaisesRegex(ValueError, '^Linked build input is forbidden$'):
                    self.module.fingerprint(tree)
        self.assertEqual((tree / 'tool').read_bytes(), b'abc')

    def test_nested_location_and_name_sensitivity(self):
        roots = [self.root / 'one', self.root / 'two']
        for root in roots:
            (root / 'bin').mkdir(parents=True)
            (root / 'bin' / 'tool').write_bytes(b'abc')
            (root / 'rootfile').write_bytes(b'def')
        expected = self.module.fingerprint(roots[0])
        self.assertEqual(expected, self.module.fingerprint(roots[1]))
        (roots[1] / 'bin' / 'tool').rename(roots[1] / 'bin' / 'other')
        self.assertNotEqual(expected, self.module.fingerprint(roots[1]))

    def test_reparse_inputs_are_rejected_without_reading_or_writing(self):
        self.fixture()
        with (patch.object(Path, 'is_symlink', return_value=True),
              patch.object(Path, 'open', side_effect=AssertionError('Unexpected read'))):
            for operation in (lambda: self.module.extract_source(self.archive, self.target),
                              lambda: self.module.fingerprint(self.root)):
                with self.assertRaisesRegex(ValueError, '^Linked build input is forbidden$'):
                    operation()
        self.assertFalse(self.target.exists())
