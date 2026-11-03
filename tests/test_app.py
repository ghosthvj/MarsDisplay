"""Application admission and real Qt/browser composition, without production MARS."""
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from playwright.sync_api import Browser, Page, Route

from browser_fixture import BrowserFixture
from mars_display.app import build_shell, main
from mars_display.browser import BrowserSession
from mars_display.settings import Settings, SettingsError, SettingsStore, SettingsStoreError
from mars_display.tray import SingleInstanceGuard

APP = None  # Construct lazily so other Qt suites can share their application.


def until(predicate, milliseconds=4000, diagnostics=None):
    loop = QEventLoop()
    poll, deadline = QTimer(), QTimer()
    poll.setInterval(5)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    poll.start()
    deadline.start(milliseconds)
    if not predicate():
        loop.exec()
    poll.stop()
    deadline.stop()
    if not predicate():
        message = "Application condition was not acknowledged before deadline"
        if diagnostics is not None:
            message += "; " + diagnostics()
        raise AssertionError(message)


class AppTests(unittest.TestCase):
    def setUp(self):
        global APP
        APP = QApplication.instance() or QApplication([])
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.store = SettingsStore(Path(self.temp) / "settings.json")
        self.shell = None
        self.enterContext(patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=True))
        self.addCleanup(self.dispose)

    def dispose(self):
        if self.shell is not None:
            self.shell.coordinator.request_exit()
            self.assertTrue(self.shell.coordinator.wait_stopped(3))
            self.shell.refresh()
            self.shell.timer.stop()
            self.shell.tray.hide()
            self.shell.dialog.hide()
            self.shell.deleteLater()

    def admitted(self):
        guard = SingleInstanceGuard(self.store)
        self.assertTrue(guard.acquire())
        guard.release()

    def invoke(self):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = main()
        return result, out.getvalue(), err.getvalue()

    def test_first_run_idle_and_duplicate_before_coordinator(self):
        with patch("mars_display.app.BrowserSession", side_effect=AssertionError("no browser")):
            self.shell = build_shell(APP, self.store)
            self.assertFalse(APP.quitOnLastWindowClosed())
            self.assertEqual(self.shell.coordinator.snapshot().state, "stopped")
            self.assertFalse(self.shell.coordinator.snapshot().worker_alive)
            self.assertFalse(self.store.path.exists())
            self.assertEqual(self.shell.dialog.url.text(), "")
            self.assertEqual(self.shell.dialog.output.text(),
                             "Simulated — simulated-closed (no USB output)")
            with patch("mars_display.app.Coordinator", side_effect=AssertionError("duplicate")):
                self.assertIsNone(build_shell(APP, self.store))
            self.shell.start_action.trigger()
            self.assertEqual(self.shell.dialog.message.text(), "Configure a MARS URL before starting.")
            self.assertFalse(self.store.path.exists())

    def test_linux_first_save_through_shell_uses_linux_selection_without_capture(self):
        from mars_display.linux_usb_worker import resolve
        from test_output_configuration import device, native
        from mars_display.settings import NATIVE_IDENTITY

        with patch('mars_display.app.BrowserSession') as browser:
            factory = Mock()
            self.shell = build_shell(APP, self.store, native_factory=factory,
                                     configuration_resolver=resolve, windows_login=False)
            before = self.shell.coordinator.snapshot()
            dialog = self.shell.dialog
            dialog.url.setText('https://mars.example')
            with patch('mars_display.tray.enumerate_devices', return_value=(device('/dev/ttyACM0'),)):
                dialog.refresh_devices.click()
            dialog.identity.setCurrentIndex(1)
            self.assertEqual(dialog.identity.currentData(), NATIVE_IDENTITY)
            with patch('mars_display.lifecycle.enumerate_devices', return_value=(device('/dev/ttyACM0'),)) as inventory:
                dialog.save.click()
                inventory.assert_called_once_with()
            self.assertEqual(self.store.load(), native(), dialog.message.text())
            self.assertEqual(SettingsStore(self.store.schema1_backup_path).load(),
                             Settings('https://mars.example', NATIVE_IDENTITY))
            self.assertFalse(self.store.pre_brightness_backup_path.exists())
            self.assertEqual(self.shell.coordinator.snapshot(), before)
            browser.assert_not_called(); factory.assert_not_called()

    def test_invalid_and_corrupt_settings_are_unchanged_and_release_lock(self):
        for raw, message in (
            (b"private-url invalid JSON", "Settings file is not valid JSON; correct it or explicitly save new settings."),
            (b'{"schema_version":1,"mars_url":"private-url","device_identity":null}',
             "MARS URL must be HTTP(S) with a valid host and port, without credentials, query, fragment, whitespace or control characters."),
        ):
            with self.subTest(raw=raw):
                self.store.path.write_bytes(raw)
                with patch("mars_display.app.Coordinator", side_effect=AssertionError("invalid config")):
                    with self.assertRaises(SettingsError) as caught:
                        build_shell(APP, self.store)
                self.assertEqual(str(caught.exception), message)
                self.assertEqual(self.store.path.read_bytes(), raw)
                self.admitted()

    def test_shell_constructor_failure_releases_lock_for_both_capabilities(self):
        for windows_login in (True, False):
            with self.subTest(windows_login=windows_login), patch(
                'mars_display.tray.TrayShell', side_effect=RuntimeError('constructor')
            ):
                with self.assertRaisesRegex(RuntimeError, '^constructor$'):
                    build_shell(APP, self.store, windows_login=windows_login)
            self.admitted()
            self.assertFalse(self.store.path.exists())

    def test_no_real_tray_rejects_without_settings_or_coordinator(self):
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
            with patch("mars_display.app.Coordinator", side_effect=AssertionError("no tray")):
                with self.assertRaisesRegex(RuntimeError, "^A system tray is required; run MarsDisplay in an interactive Windows session\\.$"):
                    build_shell(APP, self.store)
        self.assertEqual(list(Path(self.temp).iterdir()), [])

    def test_unsupported_module_command_has_exact_output_and_no_eager_qt(self):
        # Separate interpreter proves admission happens before Qt import or store construction.
        script = ("import runpy,sys; import mars_display.app as app; "
                  "app.sys.platform='darwin'; sys.modules['PySide6']=None; "
                  "runpy.run_module('mars_display',run_name='__main__')")
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                                timeout=3, env={**os.environ, "LOCALAPPDATA": self.temp})
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, "", "MarsDisplay requires Windows or Linux x64.\n"))
        self.assertEqual(list(Path(self.temp).iterdir()), [])

    def test_host_rejection_precedes_startup_resources(self):
        for host, machine, pointer_size in (
            ("linux", "ARM64", 8),
            ("linux", "x86_64", 4),
            ("darwin", "x86_64", 8),
            ("win32", "ARM64", 8),
            ("win32", "AMD64", 4),
        ):
            with self.subTest(host=host, machine=machine, pointer_size=pointer_size):
                with patch("mars_display.app.sys.platform", host), patch(
                    "mars_display.app.platform.machine", return_value=machine
                ), patch("mars_display.app.struct.calcsize", return_value=pointer_size), patch(
                    "PySide6.QtWidgets.QApplication"
                ) as application, patch("mars_display.app.SettingsStore") as store, patch(
                    "mars_display.app.build_shell"
                ) as shell:
                    self.assertEqual(self.invoke(), (
                        1, "", "MarsDisplay requires Windows or Linux x64.\n"))
                    application.assert_not_called()
                    store.assert_not_called()
                    shell.assert_not_called()
                self.assertEqual(list(Path(self.temp).iterdir()), [])

    def test_linux_root_and_failed_uid_checks_precede_resources(self):
        for uid, euid in ((0, 1000), (1000, 0), (0, 0),
                          (OSError('private'), 1000), (1000, OSError('private')),
                          (AttributeError('getuid'), 1000), (1000, None)):
            script = f'''
import sys, os
from unittest.mock import patch
import mars_display.app as app
sys.modules.update({{name: None for name in (
    'PySide6', 'mars_display.linux_paths', 'mars_display.linux_usb_transport')}})
with patch.object(app.sys, 'platform', 'linux'), \\
     patch.object(app.platform, 'machine', return_value='x86_64'), \\
     patch.object(app.struct, 'calcsize', return_value=8), \\
     patch.object(os, 'getuid', create=True, side_effect={repr(uid) if isinstance(uid, Exception) else 'None'}, return_value={uid if isinstance(uid, int) else 1000}), \\
     patch.object(os, 'geteuid', create=True, side_effect={repr(euid) if isinstance(euid, Exception) else 'None'}, return_value={repr(euid) if not isinstance(euid, Exception) else 1000}), \\
     patch.object(app, 'SettingsStore', side_effect=AssertionError('store')):
    raise SystemExit(app.main())
'''
            result = subprocess.run([sys.executable, '-B', '-c', script],
                                    capture_output=True, text=True, timeout=3)
            self.assertEqual((result.returncode, result.stdout, result.stderr),
                (1, '', 'MarsDisplay requires a non-root Linux user; cannot verify safe user credentials.\n'))
            self.assertEqual(list(Path(self.temp).iterdir()), [])

    def test_native_factory_receives_same_cancel_and_never_falls_back(self):
        from dataclasses import replace
        from threading import Event
        from types import SimpleNamespace
        from mars_display.app import compose_transport
        from mars_display.settings import NATIVE_IDENTITY, NATIVE_PROFILE
        from mars_display.transport import SimulatedTransport
        context = SimpleNamespace(settings=Settings('https://mars.example', NATIVE_IDENTITY,
            2, 'native', NATIVE_PROFILE), cancel=Event())
        factory = Mock()
        self.assertIs(compose_transport(context, native_factory=factory), factory.return_value)
        factory.assert_called_once_with(NATIVE_IDENTITY, cancel=context.cancel)
        factory.side_effect = RuntimeError('native rejected')
        with self.assertRaisesRegex(RuntimeError, '^native rejected$'):
            compose_transport(context, native_factory=factory)
        factory.reset_mock()
        factory.side_effect = None
        context.settings = replace(context.settings, output_mode='simulated', native_profile=None)
        self.assertIsInstance(compose_transport(context, native_factory=factory), SimulatedTransport)
        factory.assert_not_called()
        object.__setattr__(context.settings, 'output_mode', 'invalid')
        with self.assertRaises(SettingsError):
            compose_transport(context, native_factory=factory)
        factory.assert_not_called()

    def test_linux_composition_and_missing_tray(self):
        from mars_display.linux_usb_transport import create_transport
        from mars_display.linux_usb_worker import resolve
        with patch('mars_display.app.sys.platform', 'linux'), patch(
            'mars_display.app.platform.machine', return_value='AMD64'
        ), patch('mars_display.app.struct.calcsize', return_value=8), patch(
            'os.getuid', return_value=1000, create=True
        ), patch('os.geteuid', return_value=1000, create=True), patch(
            'PySide6.QtWidgets.QApplication', return_value=APP
        ), patch.dict(os.environ, {'XDG_CONFIG_HOME': self.temp}), patch(
            'mars_display.app.build_shell', return_value=None
        ) as shell:
            self.assertEqual(self.invoke(), (0, '', 'MarsDisplay is already running.\n'))
            args, kwargs = shell.call_args
            self.assertIs(args[0], APP)
            self.assertEqual(args[1].path, Path(self.temp) / 'MarsDisplay' / 'settings.json')
            self.assertIs(kwargs['native_factory'], create_transport)
            self.assertIs(kwargs['configuration_resolver'], resolve)
            self.assertFalse(kwargs['windows_login'])
            self.assertEqual(kwargs['missing_tray_message'],
                'A system tray is required; run MarsDisplay in an interactive Linux session.')
            shell.reset_mock()
            with patch.object(QSystemTrayIcon, 'isSystemTrayAvailable', return_value=False):
                self.assertEqual(self.invoke(), (1, '',
                    'A system tray is required; run MarsDisplay in an interactive Linux session.\n'))
            shell.assert_not_called()
            self.assertEqual(list(Path(self.temp).iterdir()), [])

    def test_windows_needs_no_unix_apis_or_linux_imports(self):
        script = '''
import os, sys
from unittest.mock import Mock, patch
import mars_display.app as app
for name in ('getuid', 'geteuid'):
    if hasattr(os, name):
        delattr(os, name)
sys.modules.update({name: None for name in (
    'mars_display.linux_paths', 'mars_display.linux_usb_transport',
    'mars_display.linux_usb_worker')})
widgets = Mock()
widgets.QSystemTrayIcon.isSystemTrayAvailable.return_value = True
with patch.dict(sys.modules, {'PySide6.QtWidgets': widgets}), \\
     patch.object(app.sys, 'platform', 'win32'), \\
     patch.object(app.platform, 'machine', return_value='AMD64'), \\
     patch.object(app.struct, 'calcsize', return_value=8), \\
     patch.object(app, 'SettingsStore') as store, \\
     patch.object(app, 'build_shell', return_value=None) as shell:
    result = app.main()
    store.assert_called_once_with()
    shell.assert_called_once_with(widgets.QApplication.return_value, store.return_value)
    raise SystemExit(result)
'''
        result = subprocess.run([sys.executable, '-B', '-c', script],
                                capture_output=True, text=True, timeout=3)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, '', 'MarsDisplay is already running.\n'))

    def test_windows_x64_aliases_reach_existing_duplicate_admission(self):
        for machine in ("AMD64", "x86_64"):
            with self.subTest(machine=machine):
                with patch("mars_display.app.sys.platform", "win32"), patch(
                    "mars_display.app.platform.machine", return_value=machine
                ), patch("mars_display.app.struct.calcsize", return_value=8), patch(
                    "PySide6.QtWidgets.QApplication", return_value=APP
                ), patch("mars_display.app.SettingsStore", return_value=self.store), patch(
                    "mars_display.app.build_shell", return_value=None
                ) as shell:
                    self.assertEqual(self.invoke(), (0, "", "MarsDisplay is already running.\n"))
                    shell.assert_called_once_with(APP, self.store)
                self.assertEqual(list(Path(self.temp).iterdir()), [])

    def test_main_host_branches_and_sanitized_startup_messages(self):
        with patch("mars_display.app.sys.platform", "win32"), patch("mars_display.app.platform.machine", return_value="ARM64"):
            self.assertEqual(self.invoke(), (1, "", "MarsDisplay requires Windows or Linux x64.\n"))
        with patch("mars_display.app.sys.platform", "win32"), patch("mars_display.app.platform.machine", return_value="AMD64"), patch("PySide6.QtWidgets.QApplication", return_value=APP), patch("mars_display.app.SettingsStore", return_value=self.store):
            with patch("mars_display.app.build_shell", return_value=None):
                self.assertEqual(self.invoke(), (0, "", "MarsDisplay is already running.\n"))
            with patch("mars_display.app.build_shell", side_effect=RuntimeError("private-url-token")):
                self.assertEqual(self.invoke(), (1, "", "Cannot start MarsDisplay; check the interactive system tray and settings directory access.\n"))
            self.store.path.write_bytes(b"private-url-token")
            self.assertEqual(self.invoke(), (1, "", "Settings file is not valid JSON; correct it or explicitly save new settings.\n"))
            self.assertEqual(self.store.path.read_bytes(), b"private-url-token")
            self.admitted()
            with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
                self.assertEqual(self.invoke(), (1, "", "A system tray is required; run MarsDisplay in an interactive Windows session.\n"))
            with patch.object(SingleInstanceGuard, "acquire", side_effect=SettingsStoreError("Cannot acquire instance lock; check settings directory access.")):
                self.assertEqual(self.invoke(), (1, "", "Cannot acquire instance lock; check settings directory access.\n"))

    def test_main_retains_shell_until_ack_and_rejects_unexpected_quit(self):
        shell = Mock()
        shell.coordinator.snapshot.return_value.exit_ready = True
        with patch("mars_display.app.sys.platform", "win32"), patch("mars_display.app.platform.machine", return_value="AMD64"), patch("PySide6.QtWidgets.QApplication", return_value=APP), patch("mars_display.app.SettingsStore", return_value=self.store), patch("mars_display.app.build_shell", return_value=shell), patch.object(APP, "exec", return_value=0) as execute:
            self.assertEqual(self.invoke(), (0, "", ""))
            execute.assert_called_once()
            shell.coordinator.request_exit.assert_not_called()
            shell.coordinator.snapshot.return_value.exit_ready = False

            def acknowledge():
                shell.coordinator.snapshot.return_value.exit_ready = True

            execute.reset_mock()
            calls = []

            def event_loop():
                calls.append("exec")
                if len(calls) == 2:
                    acknowledge()
                return 0

            execute.side_effect = event_loop
            self.assertEqual(self.invoke(), (1, "", "Application event loop ended unexpectedly; waiting for owned cleanup.\n"))
            self.assertEqual(calls, ["exec", "exec"])
            shell.coordinator.request_exit.assert_called_once()
            shell.refresh.assert_called_once()

    def test_wait_deadline_reports_selected_state(self):
        with self.assertRaises(AssertionError) as caught:
            until(lambda: False, milliseconds=0,
                  diagnostics=lambda: "state=starting, frames=0")
        self.assertEqual(str(caught.exception),
                         "Application condition was not acknowledged before deadline; state=starting, frames=0")

    def test_failed_orientation_releases_shell_before_next_admission(self):
        case = AppTests("test_real_browser_tray_start_stop_exit_both_orientations")
        captured = []
        factory = build_shell

        def record(*args, **kwargs):
            shell = factory(*args, **kwargs)
            if shell is not None:
                captured.append(shell)
            return shell

        result = unittest.TestResult()
        try:
            with patch("test_app.build_shell", side_effect=record), patch.object(
                BrowserSession, "open", side_effect=RuntimeError("controlled startup failure")
            ), patch("test_app.until", side_effect=AssertionError("controlled wait failure")):
                case.run(result)
            self.assertEqual(len(result.errors), 0,
                             [trace.splitlines()[-1] for _, trace in result.errors])
            self.assertEqual(len(result.failures), 2, result.failures)
            self.assertEqual(len(captured), 2)
            self.assertIsNone(case.shell)
            for shell in captured:
                self.assertFalse(shell.coordinator.snapshot().worker_alive)
                self.assertTrue(shell.coordinator.snapshot().exit_ready)
        finally:
            # The RED version loses its first shell; keep the probe's worker owned.
            for shell in captured:
                if shell.coordinator.snapshot().worker_alive:
                    shell.coordinator.request_exit()
                    self.assertTrue(shell.coordinator.wait_stopped(3))
                    shell.refresh()
                    shell.timer.stop()
                    shell.tray.hide()
                    shell.dialog.hide()
                    shell.deleteLater()

    def test_real_browser_tray_start_stop_exit_both_orientations(self):
        html = Path(__file__).with_name("fixtures").joinpath("display.html").read_text()
        for landscape in (False, True):
            with self.subTest(landscape=landscape):
                self.assertIsNone(self.shell, "Previous orientation still owns resources")
                content = html.replace('connected="true"', 'connected="false"').replace('stale="false"', 'stale="true"')
                if landscape:
                    content = content.replace("portrait", "landscape").replace("320", "TEMP").replace("480", "320").replace("TEMP", "480")
                with BrowserFixture(self.id() + str(landscape), content) as fixture:
                    with fixture.instrument(Page, Route):
                        self.store.save(Settings(fixture.url))
                        original = self.store.path.read_bytes()
                        owned = []
                        new_context = Browser.new_context

                        def record(browser, *args, **kwargs):
                            owned.append(browser)
                            return new_context(browser, *args, **kwargs)

                        with patch.object(Browser, "new_context", record):
                            self.shell = build_shell(APP, self.store)
                            self.assertIsNotNone(self.shell)

                            def diagnostic():
                                status = self.shell.coordinator.snapshot()
                                return (f"state={status.state}, source={status.source_state}, "
                                        f"output={status.output_state}, frames={status.frames_sent}, "
                                        f"failures={status.failures}, retries={status.retries}, "
                                        f"worker_alive={status.worker_alive}, error={status.error!r}")

                            try:
                                self.assertEqual(owned, [])
                                self.assertEqual(fixture.snapshot().owned_counts, ())
                                self.shell.start_action.trigger()
                                pulses = []
                                QTimer.singleShot(0, lambda: pulses.append("responsive"))
                                until(lambda: self.shell.coordinator.snapshot().frames_sent >= 1,
                                      milliseconds=15000, diagnostics=diagnostic)
                                self.assertEqual(pulses, ["responsive"])
                                status = self.shell.coordinator.snapshot()
                                self.assertEqual((status.source_state, status.output_state), ("ready", "simulated-open"))
                                self.assertEqual((status.live_connected, status.data_stale), (False, True))
                                frame = status.latest_frame
                                self.assertEqual((frame.width, frame.height), (480, 320) if landscape else (320, 480))
                                self.assertEqual(frame.rgb, bytes((17, 34, 51)) * (320 * 480))
                                self.shell.stop_action.trigger()
                                until(lambda: not self.shell.coordinator.snapshot().worker_alive, diagnostics=diagnostic)
                                stopped = self.shell.coordinator.snapshot()
                                self.assertEqual((stopped.state, stopped.output_state), ("stopped", "simulated-closed"))
                                self.assertTrue(owned)
                                self.assertTrue(all(not browser.is_connected() for browser in owned))
                                self.shell.refresh()
                                self.assertEqual(self.shell.dialog.source.text(), "Stopped")
                                self.assertEqual(self.store.path.read_bytes(), original)
                                self.assertEqual(self.shell.coordinator.snapshot().frames_sent, stopped.frames_sent)
                                self.shell.start_action.trigger()
                                until(lambda: self.shell.coordinator.snapshot().frames_sent > stopped.frames_sent,
                                      milliseconds=15000, diagnostics=diagnostic)
                                with patch.object(APP, "quit") as quit_app:
                                    self.shell.exit_action.trigger()
                                    until(lambda: quit_app.called, diagnostics=diagnostic)
                                self.assertTrue(self.shell.coordinator.snapshot().exit_ready)
                                self.assertTrue(all(not browser.is_connected() for browser in owned))
                                after_exit = self.shell.coordinator.snapshot().frames_sent
                                self.shell.refresh()
                                self.assertEqual(self.shell.coordinator.snapshot().frames_sent, after_exit)
                                self.admitted()
                                snapshot = fixture.snapshot()
                                self.assertEqual(dict(snapshot.owned_counts), {"/display": 2}, snapshot)
                                self.assertEqual(Counter(dict(snapshot.counts)), Counter(dict(snapshot.owned_counts)) + Counter(dict(snapshot.foreign_counts)))
                                self.assertEqual(self.store.path.read_bytes(), original)
                            finally:
                                self.dispose()
                                self.shell = None

    def test_browser_startup_failure_is_sanitized_and_stop_cancels_recovery(self):
        self.store.save(Settings("https://private.example"))
        original = self.store.path.read_bytes()
        with patch.object(BrowserSession, "open", side_effect=RuntimeError("private-url-token")):
            self.shell = build_shell(APP, self.store)
            self.shell.start_action.trigger()
            until(lambda: self.shell.dialog.runtime.text() == "Recovering (retrying)")
            self.assertEqual(self.shell.dialog.message.text(), "Capture or output failed; retrying.")
            self.assertEqual(self.shell.coordinator.snapshot().frames_sent, 0)
            self.shell.stop_action.trigger()
            until(lambda: not self.shell.coordinator.snapshot().worker_alive)
            self.assertEqual(self.shell.coordinator.snapshot().failures, 1)
            self.assertEqual(self.store.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
