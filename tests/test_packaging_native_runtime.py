"""Synthetic SDK/spec hooks; never native build or clean Windows acceptance."""
from importlib import metadata
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from test_packaging_payload import load

REPO = Path(__file__).absolute().parents[1]
SDK = Path(metadata.distribution('PyInstaller').locate_file('PyInstaller'))


class NativeRuntimeTests(unittest.TestCase):
    def test_spec_externalizes_existing_roots_and_dependencies_before_retention(self):
        observed = {}
        roots = [('PySide6/VCRUNTIME140.dll', 'C:/SDK/VCRUNTIME140.dll', 'BINARY'),
                 ('shiboken6/msvcp140_1.dll', 'C:/SDK/msvcp140_1.dll', 'BINARY'),
                 ('python313.dll', 'C:/SDK/python313.dll', 'BINARY'),
                 ('Qt6Gui.dll', 'C:/SDK/Qt6Gui.dll', 'BINARY')]
        dependencies = ['C:/SDK/ucrtbase.dll', 'C:/SDK/api-ms-win-crt-runtime-l1-1-0.dll',
                        'C:/SDK/VCRUNTIME140_1.dll', 'C:/SDK/libssl-3-x64.dll', 'C:/SDK/libcrypto-3-x64.dll',
                        'C:/SDK/opengl32sw.dll', 'C:/SDK/excluded-default.dll']
        dylib = SimpleNamespace(include_library=Mock(side_effect=lambda path: 'excluded-default' not in path))
        original_include = dylib.include_library
        def find(binaries, import_packages, symlink_suppression_patterns):
            observed['closure_input'] = tuple(binaries)
            self.assertEqual((import_packages, symlink_suppression_patterns), (['app'], {'keep-links'}))
            return list(binaries) + [(Path(path).name, path, 'BINARY') for path in dependencies if dylib.include_library(path)]
        main = SimpleNamespace(find_binary_dependencies=Mock(side_effect=find))
        original_find = main.find_binary_dependencies
        def analysis(*args, **kwargs):
            retained = list(roots)
            # Exact pinned call shape: original roots survive unless the owned
            # list is selected BEFORE find/closure, not only its returned list.
            retained.extend(main.find_binary_dependencies(retained, ['app'], {'keep-links'}))
            observed['retained'] = tuple(dict.fromkeys(retained))
            return SimpleNamespace(pure=[], scripts=[], datas=[], binaries=retained)
        hooks = ModuleType('PyInstaller.utils.hooks'); hooks.collect_data_files = Mock(return_value=[])
        modules = {'PyInstaller': ModuleType('PyInstaller'), 'PyInstaller.utils': ModuleType('PyInstaller.utils'),
                   'PyInstaller.utils.hooks': hooks, 'PyInstaller.building': SimpleNamespace(build_main=main),
                   'PyInstaller.depend': SimpleNamespace(dylib=dylib)}
        namespace = {'SPECPATH': str(REPO / 'packaging'), 'Analysis': analysis, 'PYZ': Mock(), 'EXE': Mock(), 'COLLECT': Mock()}
        with patch.dict(sys.modules, modules), patch.object(sys, 'platform', 'win32'):
            exec(compile((REPO / 'packaging/MarsDisplay.spec').read_text(), 'MarsDisplay.spec', 'exec'), namespace)
        expected = tuple(roots[2:]) + tuple((Path(path).name, path, 'BINARY') for path in dependencies[3:6])
        self.assertEqual(observed['retained'], expected)
        self.assertEqual(observed['closure_input'], tuple(roots[2:]))
        self.assertTrue(all(actual is old for actual, old in zip(observed['closure_input'], roots[2:])))
        self.assertIs(main.find_binary_dependencies, original_find)
        self.assertIs(dylib.include_library, original_include)
        self.assertEqual(original_include.call_args_list, [unittest.mock.call(path) for path in dependencies[3:]])

    def test_base_hook_omits_only_mesa_request_preserving_stock_guard_and_outputs(self):
        class Info:
            version = [6, 12, 0]
            def _collect_all_or_none(self, mandatory, *args, **kwargs):
                calls.append((mandatory, args, kwargs))
                return [(name, 'PySide6') for name in mandatory]
            def collect_extra_binaries(self):
                result = self._collect_all_or_none(['libEGL.dll', 'libGLESv2.dll'], ['d3dcompiler_??.dll'])
                result += self._collect_all_or_none(['opengl32sw.dll'])
                result += self._collect_all_or_none(['icudt??.dll', 'icuin??.dll', 'icuuc??.dll'])
                return result
        calls = []; info = Info()
        qt = ModuleType('PyInstaller.utils.hooks.qt')
        qt.pyside6_library_info = info; qt.ensure_single_qt_bindings_package = Mock()
        hooks = ModuleType('PyInstaller.utils.hooks'); hooks.check_requirement = Mock(return_value=True)
        package = ModuleType('PyInstaller'); package.__file__ = str(SDK / '__init__.py')
        local = REPO / 'packaging/hooks/hook-PySide6.py'
        path = local if local.exists() else SDK / 'hooks/hook-PySide6.py'
        namespace = {'__file__': str(path)}
        with patch.dict(sys.modules, {'PyInstaller': package, 'PyInstaller.utils': ModuleType('PyInstaller.utils'),
                                     'PyInstaller.utils.hooks': hooks, 'PyInstaller.utils.hooks.qt': qt}):
            exec(compile(path.read_text(), str(path), 'exec'), namespace)
        self.assertEqual(namespace['binaries'], [('libEGL.dll', 'PySide6'), ('libGLESv2.dll', 'PySide6'),
                                               ('icudt??.dll', 'PySide6'), ('icuin??.dll', 'PySide6'), ('icuuc??.dll', 'PySide6')])
        self.assertEqual(namespace['hiddenimports'], ['shiboken6', 'inspect', 'PySide6.support.deprecated'])
        qt.ensure_single_qt_bindings_package.assert_called_once_with('PySide6')
        hooks.check_requirement.assert_called_once_with('PySide6 >= 6.4.0')
        self.assertNotIn('_collect_all_or_none', info.__dict__)
        self.assertEqual(len(calls), 2)

    def test_exact_policies_restoration_and_final_rejection_without_purge(self):
        policy = load('native_runtime')
        external = ['MSVCP140.dll', 'msvcp140_1.dll', 'MSVCP140_2.DLL', 'vcruntime140.dll', 'vcruntime140_1.dll',
                    'ucrtbase.dll', 'api-ms-win-core-path-l1-1-0.dll', 'api-ms-win-crt-heap-l1-1-0.dll']
        kept = ['msvcp140_extra.dll', 'vcruntime140d.dll', 'api-ms-win-other-x.dll', 'myucrtbase.dll',
                'python313.dll', 'Qt6Gui.dll', 'libssl-3-x64.dll', 'node.exe', 'vulkan-1.dll',
                'vk_swiftshader.dll', 'ffmpeg-win64.exe', 'PrintDeps.exe', 'LICENSE',
                'Qt6Network.dll', 'libEGL.dll', 'icuuc76.dll', '_imaging.cp313-win_amd64.pyd', 'opengl32sw.dll']
        for separator in ('/', '\\'):
            self.assertTrue(all(policy.is_external('C:' + separator + name) for name in external))
            self.assertFalse(any(policy.is_external('C:' + separator + name) for name in kept))
        entries = [(name, name, 'BINARY') for name in external + kept]
        selected = policy.select_roots(entries)
        self.assertEqual(selected, entries[len(external):])
        self.assertTrue(all(a is b for a, b in zip(selected, entries[len(external):])))
        for name in external + ['opengl32sw.dll']:
            runtime = {'_internal/' + name: b'fixture', 'Qt6Gui.dll': b'keep'}; before = dict(runtime)
            with self.assertRaisesRegex(ValueError, 'External-runtime profile'):
                policy.assert_profile(runtime)
            self.assertEqual(runtime, before)
        main = SimpleNamespace(find_binary_dependencies=Mock(side_effect=RuntimeError('closure failed')))
        dylib = SimpleNamespace(include_library=Mock(return_value=True))
        old_find, old_include = main.find_binary_dependencies, dylib.include_library
        with patch.dict(sys.modules, {'PyInstaller.building': SimpleNamespace(build_main=main), 'PyInstaller.depend': SimpleNamespace(dylib=dylib)}):
            with self.assertRaisesRegex(RuntimeError, 'closure failed'), policy.external_dependencies():
                main.find_binary_dependencies([], [], set())
        self.assertIs(main.find_binary_dependencies, old_find); self.assertIs(dylib.include_library, old_include)
        class Info:
            def _collect_all_or_none(self, *args, **kwargs): return [('untargeted', 'keep')]
        for overridden in (False, True):
            info = Info(); override = Mock(return_value=[('override', 'keep')])
            if overridden: info._collect_all_or_none = override
            with self.assertRaisesRegex(RuntimeError, 'hook failed'):
                with policy.omit_optional_mesa(info):
                    self.assertEqual(info._collect_all_or_none(['opengl32sw.dll']), [])
                    self.assertTrue(info._collect_all_or_none(['OPENGL32SW.DLL']))
                    raise RuntimeError('hook failed')
            if overridden: self.assertIs(info.__dict__['_collect_all_or_none'], override)
            else: self.assertNotIn('_collect_all_or_none', info.__dict__)
