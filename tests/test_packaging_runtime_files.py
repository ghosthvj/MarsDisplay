"""Structural spec/copy tests only: no compiler or Windows executable runs."""
from pathlib import Path, PurePosixPath
from types import ModuleType, SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_packaging_payload import load
import test_packaging_payload as fixtures

REPO = Path(__file__).absolute().parents[1]
PREFIX = 'playwright/driver/package/.local-browsers/'


class RuntimeFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)
        self.payload = load('payload')

    def spec_copy(self, name='case', extra=None):
        """Run the real spec against a minimal fake PyInstaller DATA TOC DSL."""
        root = self.root / name
        sdk, output = root / 'sdk', root / 'frozen'
        runtime = fixtures.PayloadTests().fixture() | {
            '_internal/playwright/driver/LICENSE': b'Node legal fixture',
            '_internal/playwright/driver/package/LICENSE': b'Playwright legal fixture',
            '_internal/playwright/driver/package/NOTICE': b'attribution fixture',
            '_internal/playwright/driver/package/ThirdPartyNotices.txt': b'vendor notice fixture',
            '_internal/' + PREFIX + 'chromium_headless_shell-1248/LICENSE': b'browser legal fixture',
            '_internal/' + PREFIX + 'ffmpeg-1013/COPYING.LGPLv2.1': b'FFmpeg legal fixture',
            '_internal/' + PREFIX + 'winldd-1007/PrintDeps.exe': b'synthetic tool',
        }
        runtime.update(extra or {})
        files = {key.removeprefix('_internal/'): data for key, data in runtime.items() if key != 'MarsDisplay.exe'}
        markers = {PREFIX + directory + '/' + marker: b''
                   for directory in ('chromium_headless_shell-1248', 'ffmpeg-1013', 'winldd-1007')
                   for marker in ('INSTALLATION_COMPLETE', 'DEPENDENCIES_VALIDATED')}
        links = {PREFIX + '.links/sdk-reference': b'C:\\build-only-sdk\\playwright-driver'}
        all_source = files | markers | links
        sources = {}
        for destination, data in all_source.items():
            path = sdk / destination
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            sources[destination] = str(path)
        # Initial collection contains one marker and .links. Analysis hooks add
        # all markers, including another copy of the initial one, afterwards.
        initial_names = list(files) + [next(iter(markers))] + list(links)
        initial = [(sources[key], str(PurePosixPath(key).parent)) for key in initial_names]
        hook_names = list(markers) + [key for key in files if len(PurePosixPath(key).parts) == 2 and key.endswith('/py.typed')]
        added = [(key.replace('/', '\\'), sources[key], 'DATA') for key in hook_names]
        before = {key: (sdk / key).read_bytes() for key in all_source}
        observed = {}

        def analysis(*args, **kwargs):
            entries = [(str(PurePosixPath(destination) / Path(source).name), source, 'DATA')
                       for source, destination in kwargs['datas']]
            entries.extend(added)
            observed['before'] = tuple(entries)
            return SimpleNamespace(datas=entries, binaries=[], pure=[], scripts=[])

        def collect(exe, binaries, entries, **kwargs):
            observed['selected'] = tuple(entries)
            output.mkdir()
            (output / 'MarsDisplay.exe').write_bytes(runtime['MarsDisplay.exe'])
            for destination, source, kind in entries:
                path = output / '_internal' / destination.replace('\\', '/')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(Path(source).read_bytes())
            return output

        hooks = ModuleType('PyInstaller.utils.hooks')
        hooks.collect_data_files = Mock(return_value=initial)
        modules = {'PyInstaller': ModuleType('PyInstaller'),
                   'PyInstaller.utils': ModuleType('PyInstaller.utils'),
                   'PyInstaller.utils.hooks': hooks,
                   'PyInstaller.building': SimpleNamespace(build_main=SimpleNamespace(find_binary_dependencies=Mock())),
                   'PyInstaller.depend': SimpleNamespace(dylib=SimpleNamespace(include_library=Mock()))}
        namespace = {'SPECPATH': str(REPO / 'packaging'), 'Analysis': analysis,
                     'PYZ': Mock(), 'EXE': Mock(), 'COLLECT': collect}
        # Absolute SPECPATH, not cwd or a packaging import-path side effect,
        # must locate the helper. Real PyInstaller is never imported here.
        with patch.dict(sys.modules, modules), patch.object(sys, 'platform', 'win32'), patch('os.getcwd', return_value=str(root / 'unrelated')):
            exec(compile((REPO / 'packaging/MarsDisplay.spec').read_text(), 'MarsDisplay.spec', 'exec'), namespace)
        self.assertEqual(before, {key: (sdk / key).read_bytes() for key in all_source})
        self.assertEqual({path.relative_to(sdk).as_posix() for path in sdk.rglob('*') if path.is_file()}, set(all_source))
        return output, runtime, observed

    def test_post_analysis_hook_state_excluded_before_public_runtime_validation(self):
        output, expected, observed = self.spec_copy()
        # RED on the original spec: the unchanged reader rejects empty flags.
        actual = self.payload.read_tree(output)
        self.assertEqual(actual, expected)
        self.assertFalse(any('/.links/' in name for name in actual))
        self.assertNotIn(b'C:\\build-only-sdk', b''.join(actual.values()))
        self.assertGreater(len(observed['before']), len(observed['selected']))
        self.assertTrue(any('\\DEPENDENCIES_VALIDATED' in entry[0] for entry in observed['before']))
        expected_entries = tuple(entry for entry in observed['before']
                                 if '_internal/' + entry[0].replace('\\', '/') in expected)
        self.assertEqual(observed['selected'], expected_entries)
        for actual_entry, original_entry in zip(observed['selected'], expected_entries):
            self.assertIs(actual_entry, original_entry)

    def test_known_package_root_typing_metadata_excluded_before_runtime_validation(self):
        # Package typing markers are metadata even when nonempty. They are not
        # executable/runtime resources; the source SDK must retain every byte.
        markers = {'_internal/' + package + '/py.typed': data for package, data in (
            ('playwright', b''), ('PySide6', b'nonempty typing metadata fixture'),
            ('shiboken6', b'nonempty typing metadata fixture'), ('PIL', b''),
            ('pyee', b''), ('greenlet', b''))}
        prior = self.root / 'prior.zip'; prior.write_bytes(b'prior artifact bytes')
        output, expected, observed = self.spec_copy(extra=markers)
        for name in markers:
            del expected[name]
        actual = self.payload.read_tree(output)
        self.assertEqual(actual, expected)
        selected_names = [entry[0].replace('\\', '/') for entry in observed['selected']]
        self.assertTrue(all(name.removeprefix('_internal/') not in selected_names for name in markers))
        expected_entries = tuple(entry for entry in observed['before']
                                 if '_internal/' + entry[0].replace('\\', '/') in expected)
        self.assertEqual(observed['selected'], expected_entries)
        self.assertTrue(all(entry is original for entry, original in zip(observed['selected'], expected_entries)))
        self.assertEqual(prior.read_bytes(), b'prior artifact bytes')

    def test_separator_normalization_exact_scope_and_tuple_identity(self):
        helper = load('runtime_files')
        removed = [PREFIX + '.links/reference', PREFIX + '.links/nested/reference',
                   PREFIX + 'chromium_headless_shell-1248/INSTALLATION_COMPLETE',
                   PREFIX + 'ffmpeg-1013/DEPENDENCIES_VALIDATED',
                   PREFIX + 'winldd-1007/INSTALLATION_COMPLETE']
        typing = [package + '/py.typed' for package in ('playwright', 'PySide6', 'shiboken6', 'PIL', 'pyee', 'greenlet')]
        removed += typing + [name.swapcase() for name in typing]
        retained = ['py.typed', 'other/py.typed', 'playwright/nested/py.typed', 'PIL/resources/py.typed',
                    'playwright/py.typed.extra',
                    'assets/INSTALLATION_COMPLETE', 'playwright/driver/package/DEPENDENCIES_VALIDATED',
                    PREFIX + 'chromium_headless_shell-1248/resources/INSTALLATION_COMPLETE',
                    PREFIX + 'chromium_headless_shell-1248/.links/legitimate',
                    PREFIX + 'ffmpeg-1013/empty.txt', PREFIX + 'ffmpeg-1013/LICENSE',
                    PREFIX + 'not_revision/INSTALLATION_COMPLETE', PREFIX + 'ffmpeg-abc/INSTALLATION_COMPLETE',
                    PREFIX + '.links-other/reference', 'other/' + PREFIX + '.links/reference']
        for separator in ('/', '\\'):
            entries = [(name.replace('/', separator), '/synthetic/source', 'DATA') for name in removed + retained]
            binary = ((PREFIX + 'winldd-1007/INSTALLATION_COMPLETE').replace('/', separator), '/synthetic/source', 'BINARY')
            entries.extend([binary, ('playwright/py.typed'.replace('/', separator), '/synthetic/source', 'BINARY'),
                            ('PIL/py.typed'.replace('/', separator), '/synthetic/source', 'SYMLINK')])
            before = tuple(entries)
            result = helper.select_runtime_data(entries)
            expected = entries[len(removed):]
            self.assertEqual(result, expected)
            self.assertEqual(tuple(entries), before)
            self.assertTrue(all(actual is original for actual, original in zip(result, expected)))

    def test_other_empty_material_still_rejected_without_publication_or_prior_changes(self):
        cases = ('_internal/' + PREFIX + 'chromium_headless_shell-1248/LICENSE',
                 '_internal/playwright/driver/node.exe',
                 '_internal/' + PREFIX + 'ffmpeg-1013/empty.txt',
                 '_internal/' + PREFIX + 'chromium_headless_shell-1248/resources/INSTALLATION_COMPLETE',
                 '_internal/assets/INSTALLATION_COMPLETE',
                 '_internal/other/py.typed', '_internal/playwright/nested/py.typed')
        prior = self.root / 'prior.zip'; prior.write_bytes(b'prior artifact bytes')
        for index, name in enumerate(cases):
            with self.subTest(path=name):
                output, _, observed = self.spec_copy(str(index), {name: b''})
                self.assertIn(name.removeprefix('_internal/'), [entry[0].replace('\\', '/') for entry in observed['selected']])
                publisher = Mock()
                with self.assertRaisesRegex(ValueError, '^Duplicate path or empty/non-byte material$'):
                    publisher(self.payload.read_tree(output))
                publisher.assert_not_called()
                self.assertEqual(prior.read_bytes(), b'prior artifact bytes')
                self.assertFalse((self.root / 'dist').exists())
