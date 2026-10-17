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


def until(predicate, milliseconds=4000):
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
        raise AssertionError("Application condition was not acknowledged before deadline")


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

    def test_no_real_tray_rejects_without_settings_or_coordinator(self):
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
            with patch("mars_display.app.Coordinator", side_effect=AssertionError("no tray")):
                with self.assertRaisesRegex(RuntimeError, "^A system tray is required; run MarsDisplay in an interactive Windows session\\.$"):
                    build_shell(APP, self.store)
        self.assertEqual(list(Path(self.temp).iterdir()), [])

    def test_unsupported_module_command_has_exact_output_and_no_eager_qt(self):
        # Separate interpreter proves admission happens before Qt import or store construction.
        script = ("import runpy,sys; import mars_display.app as app; "
                  "app.sys.platform='linux'; sys.modules['PySide6']=None; "
                  "runpy.run_module('mars_display',run_name='__main__')")
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                                timeout=3, env={**os.environ, "LOCALAPPDATA": self.temp})
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, "", "MarsDisplay requires Windows x64; use Windows 11 x64.\n"))
        self.assertEqual(list(Path(self.temp).iterdir()), [])

    def test_main_host_branches_and_sanitized_startup_messages(self):
        with patch("mars_display.app.sys.platform", "win32"), patch("mars_display.app.platform.machine", return_value="ARM64"):
            self.assertEqual(self.invoke(), (1, "", "MarsDisplay requires Windows x64; use Windows 11 x64.\n"))
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

    def test_real_browser_tray_start_stop_exit_both_orientations(self):
        html = Path(__file__).with_name("fixtures").joinpath("display.html").read_text()
        for landscape in (False, True):
            with self.subTest(landscape=landscape):
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
                            self.assertEqual(owned, [])
                            self.assertEqual(fixture.snapshot().owned_counts, ())
                            self.shell.start_action.trigger()
                            pulses = []
                            QTimer.singleShot(0, lambda: pulses.append("responsive"))
                            until(lambda: self.shell.coordinator.snapshot().frames_sent >= 1)
                            self.assertEqual(pulses, ["responsive"])
                            status = self.shell.coordinator.snapshot()
                            self.assertEqual((status.source_state, status.output_state), ("ready", "simulated-open"))
                            self.assertEqual((status.live_connected, status.data_stale), (False, True))
                            frame = status.latest_frame
                            self.assertEqual((frame.width, frame.height), (480, 320) if landscape else (320, 480))
                            self.assertEqual(frame.rgb, bytes((17, 34, 51)) * (320 * 480))
                            self.shell.stop_action.trigger()
                            until(lambda: not self.shell.coordinator.snapshot().worker_alive)
                            stopped = self.shell.coordinator.snapshot()
                            self.assertEqual((stopped.state, stopped.output_state), ("stopped", "simulated-closed"))
                            self.assertTrue(owned)
                            self.assertTrue(all(not browser.is_connected() for browser in owned))
                            self.shell.refresh()
                            self.assertEqual(self.shell.dialog.source.text(), "stopped")
                            self.assertEqual(self.store.path.read_bytes(), original)
                            self.assertEqual(self.shell.coordinator.snapshot().frames_sent, stopped.frames_sent)
                            self.shell.start_action.trigger()
                            until(lambda: self.shell.coordinator.snapshot().frames_sent > stopped.frames_sent)
                            with patch.object(APP, "quit") as quit_app:
                                self.shell.exit_action.trigger()
                                until(lambda: quit_app.called)
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
                            self.dispose()
                            self.shell = None

    def test_browser_startup_failure_is_sanitized_and_stop_cancels_recovery(self):
        self.store.save(Settings("https://private.example"))
        original = self.store.path.read_bytes()
        with patch.object(BrowserSession, "open", side_effect=RuntimeError("private-url-token")):
            self.shell = build_shell(APP, self.store)
            self.shell.start_action.trigger()
            until(lambda: self.shell.dialog.runtime.text() == "recovering (retrying)")
            self.assertEqual(self.shell.dialog.message.text(), "Capture or output failed; retrying.")
            self.assertEqual(self.shell.coordinator.snapshot().frames_sent, 0)
            self.shell.stop_action.trigger()
            until(lambda: not self.shell.coordinator.snapshot().worker_alive)
            self.assertEqual(self.shell.coordinator.snapshot().failures, 1)
            self.assertEqual(self.store.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
