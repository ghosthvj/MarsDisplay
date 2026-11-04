"""Independent capture probes, retained without Windows symlink privileges."""
import ast
import hashlib
from importlib import util
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from test_packaging_payload import load

ROOT = Path(__file__).resolve().parents[1]


class CaptureBoundaryTests(unittest.TestCase):
    def test_linked_parent_never_opened_or_changed(self):
        module = load('openssl_selection')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            name = module.NAMES[0]
            source = root / name
            source.write_bytes(b'MZ private fixture')
            before = hashlib.sha256(source.read_bytes()).digest()
            # Exercise the parent-link boundary on every platform, without
            # requiring Windows Developer Mode or weakening the no-skips gate.
            with (patch.object(Path, 'is_symlink', autospec=True,
                               side_effect=lambda path: path == root),
                  patch.object(Path, 'open', side_effect=AssertionError('linked read')) as opened):
                result = module.capture([(name, str(source), 'BINARY')], roots={'cpython-sdk': root})
            opened.assert_not_called()
            self.assertEqual(result[name], {'status': 'unavailable'})
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), before)

    def test_windows_default_locations_and_unknown_no_open(self):
        module = load('openssl_selection')
        name = module.NAMES[2]
        cases = [('C:/Python/DLLs', 'cpython-sdk'),
                 ('C:/Program Files/OpenSSL/bin', 'openssl-install'),
                 ('C:/Program Files/Git/mingw64/bin', 'git-install'),
                 ('C:/Strawberry/c/bin', 'strawberry-perl'),
                 ('C:/msys64/mingw64/bin', 'msys2-mingw64'),
                 ('C:/msys64/ucrt64/bin', 'msys2-ucrt64'),
                 ('C:/hostedtoolcache/windows/Ruby/3.4.7/x64/bin', 'ruby-toolcache')]
        with (patch.object(module, 'Path', PureWindowsPath),
              patch.object(module.sys, 'platform', 'win32'),
              patch.object(module.sys, 'base_prefix', 'C:/Python'),
              patch.object(module.metadata, 'distribution', side_effect=ValueError('private')),
              patch.dict(module.os.environ, {'ProgramFiles': 'C:/Program Files', 'SystemDrive': 'C:',
                         'RUNNER_TOOL_CACHE': 'C:/hostedtoolcache/windows'}, clear=True),
              patch.object(module, '_read_regular', return_value=b'MZ fixture') as opened):
            for directory, label in cases:
                result = module.capture([(name, directory + '/' + name, 'BINARY')])
                self.assertEqual(result[name]['location'], label)
            opened.reset_mock()
            for directory in ('C:/private', 'C:/Program Files/OpenSSL/bin/subdir', '//server/share'):
                result = module.capture([(name, directory + '/' + name, 'BINARY')])
                self.assertNotEqual(result[name]['status'], 'selected')
            opened.assert_not_called()

    def test_actual_spec_tail_stage_and_corresponding_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            dist = stage / 'dist'
            dist.mkdir()
            tree = ast.parse((ROOT / 'packaging/MarsDisplay.spec').read_text())
            self.assertIsInstance(tree.body[-1], ast.Try)
            code = compile(ast.Module(body=[tree.body[-1]], type_ignores=[]), 'MarsDisplay.spec', 'exec')
            exec(code, {'util': util, 'Path': Path, 'root': ROOT,
                        'DISTPATH': str(dist), 'a': SimpleNamespace(binaries=[])})
            self.assertTrue((stage / 'openssl-selection.json').is_file())
            self.assertEqual(list(dist.iterdir()), [])
            self.assertEqual(load('openssl_selection').read(stage / 'openssl-selection.json', {})['status'],
                             'UNQUALIFIED')
            self.assertIn('packaging/openssl_selection.py', load('payload').collect_source(ROOT))


if __name__ == '__main__':
    unittest.main()
