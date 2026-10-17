"""Fake Qt collector/spec execution: structural inputs, never native proof."""
from importlib import metadata
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from test_packaging_payload import load

REPO = Path(__file__).absolute().parents[1]
HOOK = 'hook-PySide6.QtGui.py'
STOCK = Path(metadata.distribution('PyInstaller').locate_file('PyInstaller/hooks/' + HOOK))
OPTIONAL = {'imageformats': ('qpdf.dll', 'qsvg.dll'), 'iconengines': ('qsvgicon.dll',),
            'platforminputcontexts': ('qtvirtualkeyboardplugin.dll',)}


class FakeQtInfo:
    def __init__(self):
        names = {'generic': ('qgeneric.dll',), 'imageformats': ('qjpeg.dll', 'qico.dll', 'qpdf.dll', 'qsvg.dll'),
                 'iconengines': ('qsvgicon.dll', 'othericon.dll'), 'platforms': ('qwindows.dll',),
                 'platforminputcontexts': ('qtvirtualkeyboardplugin.dll', 'otherinput.dll'),
                 'styles': ('qmodernwindowsstyle.dll',), 'tls': ('qopensslbackend.dll',),
                 'networkinformation': ('qnetworklistmanager.dll',)}
        self.roots = {family: [('C:\\SDK\\plugins\\' + family + '\\' + name, 'PySide6/plugins/' + family)
                               for name in files] for family, files in names.items()}
        self.hidden = ['PySide6.QtCore', 'PySide6.QtNetwork']
        self.data = [('C:/SDK/qtbase_en.qm', 'PySide6/translations')]
        self.extras = [('C:/SDK/' + name, 'PySide6') for name in
                       ('Qt6Core.dll', 'Qt6Widgets.dll', 'Qt6Network.dll', 'libssl-3-x64.dll',
                        'opengl32sw.dll', 'libEGL.dll', 'libGLESv2.dll', 'vcruntime140.dll')]
        self.calls, self.validated = [], []
        self.fail = False

    def __getattr__(self, name):
        if name == 'version':
            self.version = [6, 12, 0]  # Model pinned library-info lazy initialization.
            return self.version
        raise AttributeError(name)

    def collect_plugins(self, family):
        self.calls.append(family)
        roots = self.roots[family]
        # Model stock release/dependency validation BEFORE the local policy.
        self.validated.extend(roots)
        return list(roots)

    def collect_module(self, module):
        assert module == 'PySide6.QtGui'
        assert self.version == [6, 12, 0]
        result = []
        for family in ('generic', 'imageformats', 'iconengines', 'platforms', 'platforminputcontexts'):
            result.extend(self.collect_plugins(family))
        if self.fail:
            raise RuntimeError('synthetic native traversal failure')
        return self.hidden, result, self.data


class QtPluginTests(unittest.TestCase):
    def execute_hook(self, path, info):
        qt = ModuleType('PyInstaller.utils.hooks.qt')
        def delegate(hook_file):
            self.assertEqual(Path(hook_file).name, HOOK)
            return info.collect_module(Path(hook_file).stem.removeprefix('hook-'))
        qt.add_qt6_dependencies = Mock(side_effect=delegate)
        qt.pyside6_library_info = info
        namespace = {'__file__': str(path)}
        with patch.dict(sys.modules, {'PyInstaller.utils.hooks.qt': qt}):
            exec(compile(path.read_text(), str(path), 'exec'), namespace)
        qt.add_qt6_dependencies.assert_called_once_with(str(path))
        return namespace

    def test_spec_hook_suppresses_only_selected_roots_before_native_closure(self):
        info = FakeQtInfo()
        before = {family: tuple(entries) for family, entries in info.roots.items()}
        observed = {}
        def analysis(*args, **kwargs):
            paths = [Path(path) / HOOK for path in kwargs.get('hookspath', [])]
            hook = next((path for path in paths if path.is_file()), STOCK)
            observed['hook'] = hook
            result = self.execute_hook(hook, info)
            observed['result'] = result
            # Model subsequent stock Widgets/Network hooks and binding extras.
            roots = list(result['binaries'])
            for family in ('styles', 'tls', 'networkinformation'):
                roots.extend(info.collect_plugins(family))
            roots.extend(info.extras)
            # This snapshot is Analysis' native dependency-closure INPUT, not
            # a late COLLECT/EXE purge; dependency libraries are not rewritten.
            observed['closure_inputs'] = tuple(roots)
            return SimpleNamespace(pure=[], scripts=[], datas=[], binaries=roots)
        hooks = ModuleType('PyInstaller.utils.hooks')
        hooks.collect_data_files = Mock(return_value=[])
        modules = {'PyInstaller': ModuleType('PyInstaller'), 'PyInstaller.utils': ModuleType('PyInstaller.utils'),
                   'PyInstaller.utils.hooks': hooks}
        namespace = {'SPECPATH': str(REPO / 'packaging'), 'Analysis': analysis,
                     'PYZ': Mock(), 'EXE': Mock(), 'COLLECT': Mock()}
        with patch.dict(sys.modules, modules), patch.object(sys, 'platform', 'win32'), patch('os.getcwd', return_value='/unrelated'):
            exec(compile((REPO / 'packaging/MarsDisplay.spec').read_text(), 'MarsDisplay.spec', 'exec'), namespace)
        expected = tuple(entry for family, entries in before.items() for entry in entries
                         if entry[0].rsplit('\\', 1)[-1] not in OPTIONAL.get(family, ())) + tuple(info.extras)
        self.assertEqual(observed['closure_inputs'], expected)
        self.assertEqual(observed['hook'], REPO / 'packaging/hooks' / HOOK)
        self.assertIs(observed['result']['hiddenimports'], info.hidden)
        self.assertIs(observed['result']['datas'], info.data)
        self.assertEqual(info.calls, list(before))
        self.assertEqual(info.validated, [entry for entries in before.values() for entry in entries])
        self.assertTrue(all(actual is original for actual, original in zip(observed['closure_inputs'], expected)))
        self.assertEqual(before, {family: tuple(entries) for family, entries in info.roots.items()})
        self.assertNotIn('collect_plugins', info.__dict__)

    def test_exact_family_basename_case_and_separators_preserve_tuple_identity(self):
        policy = load('qt_plugins')
        for family, names in OPTIONAL.items():
            for separator in ('/', '\\'):
                entries = [(separator.join(('C:', 'SDK', family, name.upper())), 'unchanged destination') for name in names]
                retained = [(separator.join(('C:', 'SDK', family, name)), 'unchanged destination')
                            for name in ('qjpeg.dll', 'qwindows.dll', 'qpdfd.dll', 'qsvg.dll.extra', 'Qt6Svg.dll')]
                entries += retained
                original = tuple(entries)
                result = policy.select_plugin_roots(family.upper(), entries)
                self.assertEqual(result, retained)
                self.assertEqual(tuple(entries), original)
                self.assertTrue(all(actual is old for actual, old in zip(result, retained)))
                self.assertEqual(policy.select_plugin_roots('styles', entries), entries)
                self.assertEqual(policy.select_plugin_roots('other/' + family, entries), entries)

    def test_instance_descriptor_and_preexisting_override_restored_even_on_failure(self):
        for overridden in (False, True):
            for failed in (False, True):
                with self.subTest(overridden=overridden, failed=failed):
                    info = FakeQtInfo()
                    override = Mock(side_effect=info.collect_plugins)
                    if overridden:
                        info.collect_plugins = override
                    info.fail = failed
                    path = REPO / 'packaging/hooks' / HOOK
                    if failed:
                        with self.assertRaisesRegex(RuntimeError, '^synthetic native traversal failure$'):
                            self.execute_hook(path, info)
                    else:
                        self.execute_hook(path, info)
                    if overridden:
                        self.assertIs(info.__dict__['collect_plugins'], override)
                        self.assertEqual(override.call_count, 5)
                    else:
                        self.assertNotIn('collect_plugins', info.__dict__)
                        self.assertIs(info.collect_plugins.__func__, FakeQtInfo.collect_plugins)
                    self.assertIn('version', info.__dict__)
