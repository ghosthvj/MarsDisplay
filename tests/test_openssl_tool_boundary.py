"""Retained independent portable-tool preparation boundary probes."""
import hashlib
import stat
import unittest
import zipfile
from unittest.mock import patch
import test_openssl_tools as existing


class ToolBoundaryTests(unittest.TestCase):
    setUp = existing.OpenSSLToolTests.setUp
    fixture = existing.OpenSSLToolTests.fixture

    def reject(self, message, error=ValueError):
        before = hashlib.sha256(self.archive.read_bytes()).digest()
        with self.assertRaises(error) as caught:
            self.module.prepare('fixture', self.archive, self.target)
        self.assertEqual(str(caught.exception), message)
        self.assertFalse(self.target.exists())
        self.assertEqual(hashlib.sha256(self.archive.read_bytes()).digest(), before)

    def test_types_duplicates_bounds_and_selection(self):
        for mode in (stat.S_IFIFO, stat.S_IFSOCK, stat.S_IFCHR, stat.S_IFLNK):
            member = zipfile.ZipInfo('special')
            member.external_attr = (mode | 0o600) << 16
            with self.subTest(mode=mode), self.fixture([(member, b'x')]):
                self.reject('Unsupported tool archive entry')
        with self.fixture([('bin/tool.exe', b'MZ duplicate')]):
            self.reject('Duplicate tool archive entry')
        with self.fixture(), patch.object(self.module, 'MAX_MEMBER', 1):
            self.reject('Tool archive member exceeds size limit')
        with self.fixture([('c/bin/nasm.exe', b'MZ wrong tool')]):
            self.module.TOOLS['fixture']['executable'] = 'missing.exe'
            self.reject('Controlled executable is missing')
        with self.fixture([('c/bin/nasm.exe', b'MZ wrong tool')]):
            result = self.module.prepare('fixture', self.archive, self.target)
            self.assertEqual(result.read_bytes(), b'MZ fixture tool')

    def test_crc_malformed_and_same_size_tamper(self):
        with self.fixture():
            data = self.archive.read_bytes().replace(b'MZ fixture tool', b'MZ corrupt tool')
            self.archive.write_bytes(data)
            self.reject('Controlled tool archive mismatch')
            self.module.TOOLS['fixture']['sha256'] = hashlib.sha256(data).hexdigest()
            self.reject("Bad CRC-32 for file 'bin/tool.exe'", zipfile.BadZipFile)
        with self.fixture():
            data = b'not a zip'
            self.archive.write_bytes(data)
            self.module.TOOLS['fixture'].update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
            self.reject('File is not a zip file', zipfile.BadZipFile)

    def test_linked_destination_preserves_existing_data(self):
        with self.fixture():
            owned = self.root / 'owned'
            owned.mkdir()
            marker = owned / 'keep'
            marker.write_bytes(b'keep')
            with patch.object(type(self.target), 'is_symlink', lambda p: p == self.target):
                self.reject('Linked build input is forbidden')
            self.assertEqual(marker.read_bytes(), b'keep')
