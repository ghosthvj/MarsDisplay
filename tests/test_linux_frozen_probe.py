"""Portable probe contracts; fake backends do not qualify frozen execution."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
from urllib.request import urlopen

PATH = Path(__file__).resolve().parents[1] / 'packaging/linux/smoke_probe.py'


class ProbeTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('smoke_probe', PATH)
        self.probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.probe)

    def invoke(self, args=()):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.probe.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_passive_help_and_host_guards(self):
        with patch.object(self.probe, 'qualify') as qualify:
            self.assertEqual(self.invoke(['--help']), (0, self.probe.HELP, ''))
            with patch.object(sys, 'platform', 'win32'):
                self.assertEqual(self.invoke(), (2, '', 'FAIL: Linux nonroot required\n'))
            for uid, euid in [(0, 1000), (1000, 0)]:
                with patch.object(sys, 'platform', 'linux'), \
                     patch.object(os, 'getuid', return_value=uid, create=True), \
                     patch.object(os, 'geteuid', return_value=euid, create=True):
                    self.assertEqual(self.invoke(), (2, '', 'FAIL: Linux nonroot required\n'))
            self.assertEqual(self.invoke(['--unknown']), (2, '', self.probe.HELP))
            qualify.assert_not_called()

    def test_isolation_success_and_failure_restore_environment(self):
        original = dict(os.environ)
        for failure in [None, RuntimeError('sandbox permission denied')]:
            seen = []
            def qualify():
                home = Path(os.environ['HOME'])
                seen.append(home)
                self.assertEqual(os.environ['QT_QPA_PLATFORM'], 'offscreen')
                self.assertEqual((home / 'settings.json').read_bytes(), b'sentinel')
                self.assertNotIn('DISPLAY', os.environ)
                if failure:
                    raise failure
            with patch.object(sys, 'platform', 'linux'), \
                 patch.object(os, 'getuid', return_value=1000, create=True), \
                 patch.object(os, 'geteuid', return_value=1000, create=True), \
                 patch.object(self.probe, 'qualify', side_effect=qualify), \
                 patch.object(self.probe, 'watchdog', contextlib.nullcontext):
                expected = ((1, '', 'FAIL: sandbox permission denied\n') if failure else
                            (0, self.probe.PASS, ''))
                self.assertEqual(self.invoke(), expected)
            self.assertEqual(dict(os.environ), original)
            self.assertFalse(seen[0].exists())

    def test_fixture_and_public_session_cleanup(self):
        for failure in [False, True]:
            session = Mock()
            frame = session.read.return_value.frame
            frame.width, frame.height = 320, 480
            frame.rgb = bytes((17, 34, 51)) * (320 * 480)
            session.read.return_value.state = 'ready'
            def opened():
                with urlopen(url[0], timeout=2) as response:
                    self.assertEqual(response.read(), self.probe.HTML)
                if failure:
                    raise RuntimeError('open failed')
            url = []
            def factory(settings):
                url.append(settings.capture_url)
                return session
            session.open.side_effect = opened
            if failure:
                with self.assertRaisesRegex(RuntimeError, 'open failed'):
                    self.probe.capture(factory)
            else:
                self.probe.capture(factory)
            session.close.assert_called_once_with()
            with self.assertRaises(OSError):
                urlopen(url[0], timeout=0.2)

    def test_bad_frame_still_closes(self):
        session = Mock()
        with self.assertRaisesRegex(RuntimeError, 'RGB frame mismatch'):
            self.probe.capture(lambda settings: session)
        session.close.assert_called_once_with()

    def test_qt_dependency_failure_quits_before_browser(self):
        app = Mock()
        core = types.ModuleType('PySide6.QtCore')
        core.QLibraryInfo = Mock()
        core.QLibraryInfo.path.return_value = '/probe/plugins'
        gui = types.ModuleType('PySide6.QtGui')
        gui.QGuiApplication = Mock()
        gui.QGuiApplication.platformName.return_value = 'offscreen'
        widgets = types.ModuleType('PySide6.QtWidgets')
        widgets.QApplication = Mock(return_value=app)
        with patch.dict(sys.modules, {'PySide6.QtCore': core, 'PySide6.QtGui': gui,
                                     'PySide6.QtWidgets': widgets}), \
             patch.object(self.probe, 'children', return_value=set()), \
             patch.object(self.probe.ctypes, 'CDLL', side_effect=OSError('missing lib')), \
             patch.object(self.probe.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'Qt platform dependency: libqxcb.so: missing lib'):
                self.probe.qualify()
        app.quit.assert_called_once_with()
        run.assert_not_called()

    def test_wayland_payload_name_and_failure_cleanup(self):
        app = Mock()
        core = types.ModuleType('PySide6.QtCore')
        core.QLibraryInfo = Mock()
        core.QLibraryInfo.path.return_value = '/probe/plugins'
        gui = types.ModuleType('PySide6.QtGui')
        gui.QGuiApplication = Mock()
        gui.QGuiApplication.platformName.return_value = 'offscreen'
        widgets = types.ModuleType('PySide6.QtWidgets')
        widgets.QApplication = Mock(return_value=app)
        with patch.dict(sys.modules, {'PySide6.QtCore': core, 'PySide6.QtGui': gui,
                                     'PySide6.QtWidgets': widgets}), \
             patch.object(self.probe, 'children', return_value=set()), \
             patch.object(self.probe.ctypes, 'CDLL', side_effect=[Mock(), OSError('missing dependency')]) as load, \
             patch.object(self.probe.subprocess, 'run') as run, \
             patch('playwright.sync_api.sync_playwright') as driver, \
             patch('mars_display.browser.BrowserSession') as session:
            with self.assertRaises(RuntimeError) as caught:
                self.probe.qualify()
        app.quit.assert_called_once_with()
        run.assert_not_called()
        driver.assert_not_called()
        session.assert_not_called()
        self.assertEqual([call.args[0] for call in load.call_args_list],
                         [str(Path('/probe/plugins/platforms') / name)
                          for name in ('libqxcb.so', 'libqwayland.so')])
        self.assertEqual(str(caught.exception),
                         'Qt platform dependency: libqwayland.so: missing dependency')

    def test_launch_failure_classification(self):
        for text, expected in [('Operation not permitted', 'browser permission/sandbox'),
                               ('libX.so: cannot open shared object', 'browser package/dependencies'),
                               ('unexpected', 'browser launch unclassified')]:
            self.assertEqual(self.probe.launch_failure(text), expected)
