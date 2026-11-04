"""Portable regressions for canonical fixture paths and exact release bytes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ReleasePortabilityTests(unittest.TestCase):
    def check_case(self, case):
        result = unittest.TestResult()
        case.run(result)
        self.assertTrue(result.wasSuccessful(), str(result.failures + result.errors))
        self.assertEqual((result.testsRun, result.skipped), (1, []))

    def test_fixture_paths_accept_equivalent_lexical_roots(self):
        from test_linux_build_evidence import AcquisitionTests
        from test_linux_release_assembly import AssemblyTests
        from test_linux_release_build import BuildTests
        from test_linux_sdk_transport import TransportTests

        temporary_directory = tempfile.TemporaryDirectory

        def aliased_directory(*args, **kwargs):
            directory = temporary_directory(*args, **kwargs)
            child = Path(directory.name) / 'alias-child'
            child.mkdir()
            # No symlink privileges or Windows-only 8.3 API are required.
            return SimpleNamespace(name=str(child / '..'), cleanup=directory.cleanup)

        cases = [
            (AcquisitionTests, 'test_complete_package_acquisition'),
            (AcquisitionTests, 'test_cpython_archive_pin_and_license_complete'),
            (AssemblyTests, 'test_success_measures_and_preserves'),
            (BuildTests, 'test_four_assets_bind_committed_source_without_mutating_original_index'),
            (TransportTests, 'test_streams_to_original_nonroot_owner_and_validates_exports'),
        ]
        for cls, name in cases:
            with self.subTest(case=name):
                case = cls(name)
                self.addCleanup(case.doCleanups)
                # Only fixture setup receives the alias; production temp handling
                # and all existing public CLI assertions stay unchanged.
                with patch.object(tempfile, 'TemporaryDirectory', aliased_directory):
                    case.setUp()
                getattr(case, name)()
                case.tearDown()

    def test_retained_runtime_bytes_survive_git_checkout_conversion(self):
        registry = json.loads((ROOT / 'packaging/linux/runtime-inputs.json').read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
            material = root / 'third_party/linux-runtime'
            material.mkdir(parents=True)
            for name in registry['retained']:
                (material / name).write_bytes((ROOT / 'third_party/linux-runtime' / name).read_bytes())
            subprocess.run(['git', 'init', '-q'], cwd=root, capture_output=True, check=True)
            subprocess.run(['git', '-c', 'core.autocrlf=false', 'add', '.gitattributes',
                            'third_party/linux-runtime'], cwd=root, capture_output=True, check=True)
            for autocrlf in ('false', 'true'):
                for name, expected in registry['retained'].items():
                    with self.subTest(autocrlf=autocrlf, file=name):
                        # Read only this generated fixture's index, never checkout history.
                        filtered = subprocess.check_output(
                            ['git', '-c', 'core.autocrlf=' + autocrlf, 'cat-file', '--filters',
                             ':third_party/linux-runtime/' + name], cwd=root)
                        self.assertEqual(filtered, (material / name).read_bytes())
                        self.assertEqual(hashlib.sha256(filtered).hexdigest(), expected)
                # Exercise a real checkout too, not just Git's filter plumbing.
                # Only generated fixture files are replaced; source is untouched.
                for name in registry['retained']:
                    (material / name).unlink()
                subprocess.run(['git', '-c', 'core.autocrlf=' + autocrlf,
                                'checkout-index', '--all', '--force'],
                               cwd=root, capture_output=True, check=True)
                for name, expected in registry['retained'].items():
                    with self.subTest(autocrlf=autocrlf, file=name, phase='checkout'):
                        checked_out = (material / name).read_bytes()
                        self.assertEqual(checked_out,
                                         (ROOT / 'third_party/linux-runtime' / name).read_bytes())
                        self.assertEqual(hashlib.sha256(checked_out).hexdigest(), expected)

    def test_crlf_fixtures_use_committed_bytes_for_both_platforms(self):
        from test_release_linux import CombinedReleaseTests
        write_text = Path.write_text

        def windows_write(path, data, *args, **kwargs):
            if path.name == 'pyproject.toml':
                kwargs['newline'] = '\r\n'
            return write_text(path, data, *args, **kwargs)

        for autocrlf in ('false', 'true'):
            with (self.subTest(autocrlf=autocrlf),
                  patch.object(Path, 'write_text', windows_write),
                  patch.dict(os.environ, {'GIT_CONFIG_COUNT': '1',
                                          'GIT_CONFIG_KEY_0': 'core.autocrlf',
                                          'GIT_CONFIG_VALUE_0': autocrlf})):
                self.check_case(CombinedReleaseTests(
                    'test_real_linux_validator_composes_with_windows_and_publish'))

    def test_real_validator_preserves_git_lookup_in_isolated_environment(self):
        from test_release_linux import CombinedReleaseTests
        # Git is not installed on the default executable search path on Windows.
        # Its inherited PATH must survive the fixture's isolated GitHub environment.
        with patch.object(os, 'defpath', ''):
            self.check_case(CombinedReleaseTests(
                'test_real_linux_validator_composes_with_windows_and_publish'))


if __name__ == '__main__':
    unittest.main()
