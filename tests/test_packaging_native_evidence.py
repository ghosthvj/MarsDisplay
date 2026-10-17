"""Synthetic public PE/RECORD providers, not native Windows version proof."""
import base64
import hashlib
from importlib.metadata import PackagePath
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_packaging_payload import load

DATA = b'immutable synthetic PE bytes'
PATH = '_internal/PySide6/Qt6Core.dll'


def parser(pe):
    return SimpleNamespace(__version__='2024.8.26', PE=Mock(return_value=pe),
                           DIRECTORY_ENTRY={'IMAGE_DIRECTORY_ENTRY_RESOURCE': 2})


def record(path, data=DATA, mode='sha256'):
    item = PackagePath(path)
    item.hash = SimpleNamespace(mode=mode, value=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('='))
    return item


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.helper = load('native_evidence')
        self.inventory = {'dependencies': [], 'build_dependencies': [], 'build': {'Qt': '6.12.0'}}

    def fixed(self):
        return SimpleNamespace(Signature=0xFEEF04BD, FileVersionMS=(14 << 16) | 44,
                               FileVersionLS=(35211 << 16) | 65535,
                               ProductVersionMS=(1 << 16) | 2, ProductVersionLS=7)

    def test_fixed_versions_from_bytes_are_not_qt_or_resource_string_versions(self):
        pe = SimpleNamespace(VS_FIXEDFILEINFO=[self.fixed()],
                             FileInfo={'CompanyName': 'private-secret-path', 'FileVersion': '6.12.0'},
                             parse_data_directories=Mock(), close=Mock())
        sdk = parser(pe)
        result = self.helper.collect({PATH: DATA}, self.inventory, parser=sdk)
        item = result[PATH]
        self.assertEqual(item['sha256'], hashlib.sha256(DATA).hexdigest())
        self.assertEqual(item['pe'], {'status': 'measured', 'file_version': '14.44.35211.65535',
                                     'product_version': '1.2.0.7'})
        self.assertEqual(item['origins'], {'status': 'unknown', 'record_status': 'available', 'matches': []})
        sdk.PE.assert_called_once_with(data=DATA, fast_load=True)
        pe.parse_data_directories.assert_called_once_with(directories=[2])
        pe.close.assert_called_once()
        self.assertNotIn('private-secret', json.dumps(result))
        self.assertNotIn('6.12.0', json.dumps(result))

    def test_record_owners_match_only_exact_hash_safe_path_and_declared_identity(self):
        self.inventory['dependencies'] = [{'name': 'wheel-b', 'version': '2'}, {'name': 'wheel-a', 'version': '1'}]
        self.inventory['build_dependencies'] = [{'name': 'wheel-a', 'version': '1'}]
        bad = record('invalid/base64.dll'); bad.hash.value = 'not-a-digest'
        records = [record('same/Qt6Core.dll', b'different'), record('../escape.dll'), record('C:/SDK.dll'),
                   record('/absolute.dll'), record('a\\b.dll'), record('.env/file.dll'), bad,
                   record('other/hash.dll', mode='sha512')]
        dists = {}
        for name, version, path in [('wheel-a', '1', 'wheel_a/native.dll'), ('wheel-b', '2', 'wheel_b/renamed.dll')]:
            dist = SimpleNamespace(metadata={'Name': name, 'Version': version}, version=version,
                                   files=records + [record(path)], locate_file=Mock(side_effect=AssertionError('no SDK file lookup')))
            dists[name] = dist
        lookup = Mock(side_effect=dists.__getitem__)
        sdk = SimpleNamespace(__version__='wrong-parser-version')
        other = '_internal/unknown.dll'
        result = self.helper.collect({other: b'unmatched', PATH: DATA}, self.inventory, parser=sdk, lookup=lookup)
        digest = hashlib.sha256(DATA).hexdigest()
        self.assertEqual(result[PATH]['origins'], {'status': 'matched', 'record_status': 'available', 'matches': [
            {'name': 'wheel-a', 'version': '1', 'record_path': 'wheel_a/native.dll', 'sha256': digest},
            {'name': 'wheel-b', 'version': '2', 'record_path': 'wheel_b/renamed.dll', 'sha256': digest}]})
        self.assertEqual(result[other]['origins']['status'], 'unknown')
        self.assertEqual(result[other]['origins']['matches'], [])
        self.assertEqual(lookup.call_count, 2)
        for dist in dists.values(): dist.locate_file.assert_not_called()

    def test_sparse_malformed_unavailable_and_provider_errors_remain_sanitized(self):
        for case in ('absent', 'malformed', 'bad-dword', 'boolean-dword', 'overflow', 'parser-error', 'close-error'):
            with self.subTest(case=case):
                pe = SimpleNamespace(parse_data_directories=Mock(), close=Mock())
                if case != 'absent': pe.VS_FIXEDFILEINFO = [self.fixed()]
                if case == 'malformed': pe.VS_FIXEDFILEINFO.append(self.fixed())
                if case == 'bad-dword': pe.VS_FIXEDFILEINFO[0].FileVersionMS = -1
                if case == 'boolean-dword': pe.VS_FIXEDFILEINFO[0].FileVersionMS = True
                if case == 'overflow': pe.VS_FIXEDFILEINFO[0].FileVersionMS = 1 << 32
                if case == 'parser-error': pe.parse_data_directories.side_effect = ValueError('private-secret-URL')
                if case == 'close-error': pe.close.side_effect = ValueError('private-secret-URL')
                result = self.helper.collect({PATH: DATA}, self.inventory, parser=parser(pe))
                self.assertEqual(result[PATH]['pe'], {'status': 'absent' if case == 'absent' else 'unknown'})
                pe.close.assert_called_once()
                self.assertNotIn('private-secret', json.dumps(result))
        self.inventory['dependencies'] = [{'name': 'wheel-a', 'version': '1'}]
        for name, version in [('other-wheel', '1'), ('wheel-a', '2')]:
            dist = SimpleNamespace(metadata={'Name': name}, version=version, files=[record('valid.dll')])
            result = self.helper.collect({PATH: DATA}, self.inventory, parser=SimpleNamespace(__version__='unknown'),
                                         lookup=Mock(return_value=dist))
            self.assertEqual(result[PATH]['origins'], {'status': 'unknown', 'record_status': 'unavailable', 'matches': []})
        with patch.dict('sys.modules', {'pefile': None}):
            result = self.helper.collect({PATH: DATA}, self.inventory,
                                         lookup=Mock(side_effect=RuntimeError('private-secret-path')))
        self.assertEqual(result[PATH]['pe'], {'status': 'unavailable'})
        self.assertEqual(result[PATH]['origins'], {'status': 'unknown', 'record_status': 'unavailable', 'matches': []})
        self.assertNotIn('private-secret', json.dumps(result))
