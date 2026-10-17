"""Offscreen widgets and public coordinator/lock contracts; no browser or USB."""
from dataclasses import replace
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QEventLoop, QTimer, Qt
from PySide6.QtGui import QKeyEvent, QPalette
from PySide6.QtWidgets import QApplication

from mars_display.frames import RGBFrame
from mars_display.lifecycle import Coordinator, SourceSample
from mars_display.settings import Settings, SettingsStore
from mars_display.transport import SimulatedTransport
from mars_display.tray import SettingsDialog, SingleInstanceGuard, create_shell


class Application(QApplication):
    def quit(self):
        self.quit_requests += 1


APP = Application.instance() or Application([])
APP.quit_requests = 0
FRAME = RGBFrame(320, 480, bytes(320 * 480 * 3), 0)


def until(predicate):
    """Bound every Qt wait; timers yield to both Qt and the capture worker."""
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(5)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    poll.start()
    deadline.start(2000)
    if not predicate():
        loop.exec()
    poll.stop()
    deadline.stop()
    if not predicate():
        raise AssertionError("Qt condition was not acknowledged within two seconds")


class Session:
    def __init__(self):
        self.sample = SourceSample("ready", FRAME, True, False)
        self.opened = Event()
        self.allow_open = Event()
        self.closing = Event()
        self.allow_close = Event()
        self.cleanup_error = False
        self.read_error = False

    def open(self):
        self.opened.set()
        if not self.allow_open.wait(2):
            raise AssertionError("open handshake timed out")

    def read(self):
        if self.read_error:
            raise RuntimeError("controlled source failure")
        return self.sample

    def close(self):
        self.closing.set()
        if not self.allow_close.wait(2):
            raise AssertionError("cleanup handshake timed out")
        if self.cleanup_error:
            raise RuntimeError("controlled cleanup failure")


class TrayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SettingsStore(Path(self.temp.name) / "settings.json")
        self.session = Session()
        self.created = []
        self.waiting = Event()
        self.next_sample = Event()
        self.shell = None
        APP.quit_requests = 0

    def tearDown(self):
        self.session.allow_open.set()
        self.session.allow_close.set()
        self.next_sample.set()
        if self.shell:
            self.shell.coordinator.request_exit()
            self.assertTrue(self.shell.coordinator.wait_stopped(2))
            self.shell.timer.stop()
            self.shell.tray.hide()
            self.shell.dialog.hide()
            self.shell.guard.release()
            self.shell.deleteLater()
        self.temp.cleanup()

    def make(self, configured=True, wait_override=None):
        if configured:
            self.store.save(Settings("https://mars.example", "opaque-device"))

        def wait(cancel, seconds):
            self.waiting.set()
            if not self.next_sample.wait(2):
                return cancel.is_set()
            self.next_sample.clear()
            return cancel.is_set()

        def factory():
            self.created.append("coordinator")
            return Coordinator(self.store, lambda settings: self.session,
                               SimulatedTransport, wait=wait_override or wait)

        self.factory = factory
        self.shell = create_shell(APP, self.store, factory)
        return self.shell

    def running(self):
        self.assertFalse(self.session.opened.is_set())
        self.assertFalse(self.shell.coordinator.snapshot().worker_alive)
        self.shell.start_action.trigger()
        until(self.session.opened.is_set)
        self.assertEqual(self.shell.coordinator.snapshot().state, "starting")
        until(lambda: self.shell.dialog.runtime.text() == "starting")
        self.assertFalse(self.shell.start_action.isEnabled())
        self.session.allow_open.set()
        until(self.waiting.is_set)
        until(lambda: self.shell.dialog.frames.text() == "1")

    def test_light_dark_theme_is_local_and_does_not_persist_or_start_capture(self):
        shell = self.make()
        dialog = shell.dialog
        original = self.store.path.read_bytes()
        self.assertEqual(dialog.property("theme"), "light")
        dialog.ensurePolished()
        light = dialog.palette().color(QPalette.ColorRole.Window).name()
        dialog.theme_switch.click()
        APP.processEvents()
        self.assertEqual(dialog.property("theme"), "dark")
        self.assertNotEqual(dialog.palette().color(QPalette.ColorRole.Window).name(), light)
        self.assertEqual(dialog.theme_switch.text(), "Light mode")
        dialog.close()
        shell.show_settings()
        self.assertEqual(dialog.property("theme"), "dark")
        dialog.theme_switch.click()
        self.assertEqual(dialog.property("theme"), "light")
        self.assertEqual(dialog.theme_switch.text(), "Dark mode")
        fresh = SettingsDialog(self.store.load())
        self.assertEqual(fresh.property("theme"), "light")
        fresh.deleteLater()
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(shell.coordinator.snapshot().state, "stopped")
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        self.assertFalse(self.session.opened.is_set())

    def test_reference_layout_keeps_native_window_plain_text_and_small_window_footer(self):
        shell = self.make()
        dialog = shell.dialog
        self.assertFalse(dialog.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertFalse(dialog.windowIcon().isNull())
        self.assertTrue(dialog.scroll_area.widgetResizable())
        self.assertTrue(dialog.footer.isAncestorOf(dialog.save))
        self.assertFalse(dialog.scroll_area.isAncestorOf(dialog.save))
        self.assertEqual(dialog.window_heading.text(), "Status / Settings")
        for label in (dialog.runtime, dialog.source, dialog.output, dialog.metadata,
                      dialog.frames, dialog.device, dialog.message):
            self.assertEqual(label.textFormat(), Qt.TextFormat.PlainText)
        shell.show_settings()
        dialog.resize(600, 480)
        APP.processEvents()
        self.assertTrue(dialog.save.isVisible())
        self.assertLessEqual(dialog.footer.geometry().bottom(), dialog.height())
        self.assertGreater(dialog.scroll_area.verticalScrollBar().maximum(), 0)
        dialog.close()
        self.assertFalse(dialog.isVisible())
        shell.show_settings()
        APP.sendEvent(dialog, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                       Qt.KeyboardModifier.NoModifier))
        self.assertFalse(dialog.isVisible())
        self.assertEqual(APP.quit_requests, 0)
        self.assertEqual(shell.coordinator.snapshot().state, "stopped")

    def test_window_capture_button_uses_existing_start_stop_and_cleanup_guards(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        button = shell.dialog.capture_action
        self.assertEqual(button.text(), "Start capture")
        self.assertTrue(button.isEnabled())
        button.click()
        until(self.session.opened.is_set)
        until(lambda: button.text() == "Stop capture")
        self.assertEqual(shell.coordinator.snapshot().state, "starting")
        self.session.allow_open.set()
        until(lambda: shell.dialog.frames.text() == "1")
        button.click()
        self.next_sample.set()
        until(self.session.closing.is_set)
        until(lambda: not button.isEnabled())
        self.assertFalse(shell.dialog.save.isEnabled())
        self.session.allow_close.set()
        until(lambda: shell.dialog.runtime.text() == "stopped")
        self.assertEqual(button.text(), "Start capture")
        self.assertTrue(button.isEnabled())
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 1)
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_url_footer_and_feedback_follow_stopped_only_authority(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        self.assertFalse(shell.dialog.url.isReadOnly())
        shell.dialog.save.click()
        self.assertEqual(shell.dialog.message.text(), "Settings saved. Capture remains stopped.")
        self.running()
        self.assertTrue(shell.dialog.url.isReadOnly())
        self.assertEqual(shell.dialog.hint.text(),
                         "Capture is running. Stop capture to save changes.")
        self.assertEqual(shell.dialog.message.text(), "")
        self.assertEqual(shell.dialog.source.property("tone"), "success")
        self.assertEqual(shell.dialog.runtime.property("tone"), "active")
        self.assertEqual(self.store.path.read_bytes(), original)
        shell.exit_action.trigger()
        self.next_sample.set()
        until(self.session.closing.is_set)
        until(lambda: not shell.dialog.capture_action.isEnabled())
        self.assertTrue(shell.dialog.url.isReadOnly())
        self.assertFalse(shell.dialog.save.isEnabled())
        self.assertEqual(APP.quit_requests, 0)
        self.session.allow_close.set()
        until(lambda: APP.quit_requests == 1)

    def test_window_stop_cancels_retry_and_clears_old_runtime_error(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        self.session.read_error = True
        self.session.allow_open.set()
        self.session.allow_close.set()
        shell.start_action.trigger()
        until(lambda: shell.dialog.runtime.text() == "recovering (retrying)")
        self.assertEqual(shell.dialog.capture_action.text(), "Stop capture")
        self.assertTrue(shell.dialog.capture_action.isEnabled())
        self.assertTrue(shell.dialog.url.isReadOnly())
        shell.dialog.capture_action.click()
        self.next_sample.set()
        until(lambda: shell.dialog.runtime.text() == "stopped")
        self.assertEqual(shell.coordinator.snapshot().retries, 1)
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        self.assertEqual(shell.dialog.message.text(), "")
        self.assertFalse(shell.dialog.url.isReadOnly())
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_window_start_restarts_exhausted_error_without_bypassing_coordinator(self):
        shell = self.make(wait_override=lambda cancel, seconds: cancel.is_set())
        self.session.read_error = True
        self.session.allow_open.set()
        self.session.allow_close.set()
        shell.start_action.trigger()
        until(lambda: shell.dialog.runtime.text() == "error")
        self.assertEqual(shell.coordinator.snapshot().failures, 6)
        self.assertEqual(shell.dialog.capture_action.text(), "Start capture")
        self.assertTrue(shell.dialog.capture_action.isEnabled())
        self.assertFalse(shell.dialog.save.isEnabled())
        self.assertTrue(shell.dialog.url.isReadOnly())
        self.assertEqual(shell.dialog.source.property("tone"), "error")
        self.assertEqual(shell.dialog.hint.text(),
                         "Capture is in error. Use tray Stop to edit settings.")
        self.session.read_error = False
        shell.dialog.capture_action.click()
        until(lambda: shell.coordinator.snapshot().frames_sent >= 1)
        until(lambda: shell.dialog.runtime.text() == "running")
        self.assertEqual(shell.dialog.message.text(), "")
        self.assertEqual(shell.dialog.capture_action.text(), "Stop capture")

    def test_lifetime_frame_formatting_only_changes_presentation(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        before = shell.coordinator.snapshot()
        with patch.object(shell.coordinator, "snapshot", return_value=replace(before, frames_sent=7045)):
            shell.refresh()
            self.assertEqual(shell.dialog.frames.text(), "7,045")
        self.assertEqual(shell.coordinator.snapshot(), before)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertFalse(self.session.opened.is_set())

    def test_manual_first_run_menu_dialog_and_close(self):
        shell = self.make(configured=False)
        self.assertFalse(APP.quitOnLastWindowClosed())
        self.assertEqual(shell.coordinator.snapshot().state, "stopped")
        self.assertFalse(self.session.opened.is_set())
        self.assertFalse(self.store.path.exists())
        self.assertFalse(shell.dialog.isVisible())
        self.assertFalse(shell.tray.icon().isNull())
        self.assertEqual([a.text() for a in shell.menu.actions()],
                         ["Status / Settings", "Start", "Stop", "Exit"])
        self.assertTrue(shell.start_action.isEnabled())
        self.assertFalse(shell.stop_action.isEnabled())
        shell.start_action.trigger()
        self.assertEqual(shell.dialog.message.text(), "Configure a MARS URL before starting.")
        shell.settings_action.trigger()
        self.assertTrue(shell.dialog.isVisible())
        self.assertEqual(shell.dialog.url.text(), "")
        self.assertEqual(shell.dialog.device.text(), "Not selected (hardware identification pending)")
        shell.dialog.close()
        self.assertFalse(shell.dialog.isVisible())
        self.assertEqual(APP.quit_requests, 0)
        self.assertFalse(self.session.opened.is_set())

    def test_save_validation_and_active_rejection_preserve_bytes(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        shell.settings_action.trigger()
        self.assertEqual(shell.dialog.device.text(), "opaque-device")
        shell.dialog.url.setText("not a URL")
        shell.dialog.save.click()
        self.assertIn("MARS URL must be HTTP(S)", shell.dialog.message.text())
        self.assertEqual(self.store.path.read_bytes(), original)
        shell.dialog.url.setText("https://other.example")
        shell.dialog.save.click()
        self.assertEqual(self.store.load(), Settings("https://other.example", "opaque-device"))
        original = self.store.path.read_bytes()
        self.running()
        self.assertFalse(shell.dialog.save.isEnabled())
        shell.dialog.url.setText("https://third.example")
        shell.dialog.save.click()
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 1)
        self.assertFalse(shell.start_action.isEnabled())
        self.assertTrue(shell.stop_action.isEnabled())
        shell.stop_action.trigger()
        self.next_sample.set()
        until(self.session.closing.is_set)
        self.assertFalse(shell.start_action.isEnabled())
        self.assertFalse(shell.dialog.save.isEnabled())
        self.session.allow_close.set()
        until(lambda: shell.coordinator.snapshot().state == "stopped")
        until(lambda: shell.start_action.isEnabled() and shell.dialog.save.isEnabled())
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 1)
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_source_and_simulated_output_are_independent(self):
        shell = self.make()
        self.running()
        self.assertEqual(shell.dialog.source.text(), "ready")
        self.assertEqual(shell.dialog.output.text(), "Simulated — simulated-open (no USB output)")
        self.assertEqual(shell.dialog.metadata.text(), "Live connected: yes; data stale: no")
        self.session.sample = SourceSample("empty", live_connected=False, data_stale=True)
        self.next_sample.set()
        until(lambda: shell.dialog.source.text() == "empty")
        self.assertEqual(shell.dialog.frames.text(), "1")
        self.assertEqual(shell.dialog.metadata.text(), "Live connected: no; data stale: yes")
        self.assertIn("simulated-open", shell.dialog.output.text())
        self.session.sample = SourceSample("loading")
        self.next_sample.set()
        until(lambda: shell.dialog.source.text() == "loading")
        self.assertEqual(shell.dialog.metadata.text(), "Live connected: unknown; data stale: unknown")
        self.assertEqual(shell.dialog.frames.text(), "1")

    def test_exit_waits_for_cleanup_acknowledgement(self):
        shell = self.make()
        self.running()
        shell.exit_action.trigger()
        self.next_sample.set()
        until(self.session.closing.is_set)
        self.assertEqual(APP.quit_requests, 0)
        self.assertFalse(shell.start_action.isEnabled())
        self.assertFalse(shell.exit_action.isEnabled())
        self.assertIsNone(create_shell(APP, self.store, self.factory))
        self.assertEqual(self.created, ["coordinator"])
        self.session.allow_close.set()
        until(lambda: APP.quit_requests == 1)
        self.assertTrue(shell.coordinator.snapshot().exit_ready)
        guard = SingleInstanceGuard(self.store)
        self.assertTrue(guard.acquire())
        guard.release()

    def test_cleanup_error_stays_alive_and_visible(self):
        shell = self.make()
        self.session.cleanup_error = True
        self.running()
        shell.exit_action.trigger()
        self.next_sample.set()
        self.session.allow_close.set()
        until(lambda: shell.dialog.runtime.text() == "error")
        self.assertEqual(APP.quit_requests, 0)
        self.assertFalse(shell.coordinator.snapshot().exit_ready)
        self.assertFalse(shell.start_action.isEnabled())
        self.assertTrue(shell.dialog.isVisible())
        self.assertIn("Cleanup failed", shell.dialog.message.text())
        self.assertIn("owned", shell.dialog.message.text())

    def test_recovering_state_can_be_stopped_without_retry(self):
        shell = self.make()
        self.session.read_error = True
        self.session.allow_open.set()
        self.session.allow_close.set()
        shell.start_action.trigger()
        until(lambda: shell.dialog.runtime.text() == "recovering (retrying)")
        self.assertEqual(shell.dialog.source.text(), "error")
        self.assertEqual(shell.dialog.frames.text(), "0")
        self.assertIn("simulated-closed", shell.dialog.output.text())
        self.assertFalse(shell.start_action.isEnabled())
        self.assertTrue(shell.stop_action.isEnabled())
        shell.stop_action.trigger()
        self.next_sample.set()
        until(lambda: shell.dialog.runtime.text() == "stopped")
        self.assertEqual(shell.coordinator.snapshot().retries, 1)
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)

    def test_exhausted_error_allows_explicit_start_or_stop(self):
        shell = self.make(wait_override=lambda cancel, seconds: cancel.is_set())
        self.session.read_error = True
        self.session.allow_open.set()
        self.session.allow_close.set()
        shell.start_action.trigger()
        until(lambda: shell.dialog.runtime.text() == "error")
        self.assertTrue(shell.start_action.isEnabled())
        self.assertTrue(shell.stop_action.isEnabled())
        self.assertFalse(shell.dialog.save.isEnabled())
        self.assertEqual(shell.dialog.message.text(),
                         "Recovery exhausted; check MARS and output, then Start.")
        self.assertEqual(shell.coordinator.snapshot().failures, 6)
        shell.stop_action.trigger()
        self.assertEqual(shell.dialog.runtime.text(), "stopped")
        self.assertTrue(shell.dialog.save.isEnabled())

    def test_guard_public_acquire_release_and_second_admission(self):
        first = SingleInstanceGuard(self.store)
        second = SingleInstanceGuard(self.store)
        try:
            self.assertTrue(first.acquire())
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            second.release()  # a non-owner must not unlock the first guard
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
        finally:
            first.release()
            second.release()
        shell = self.make(configured=False)
        self.assertIsNone(create_shell(APP, self.store, self.factory))
        self.assertEqual(self.created, ["coordinator"])
        self.assertFalse(self.session.opened.is_set())
        self.assertFalse(shell.coordinator.snapshot().worker_alive)

    def test_corrupt_settings_propagate_without_repair_or_coordinator(self):
        self.store.path.write_bytes(b"invalid JSON")
        calls = []
        from mars_display.settings import SettingsError
        with self.assertRaises(SettingsError):
            create_shell(APP, self.store, lambda: calls.append("created"))
        self.assertEqual(calls, [])
        self.assertEqual(self.store.path.read_bytes(), b"invalid JSON")
        guard = SingleInstanceGuard(self.store)
        self.assertTrue(guard.acquire())
        guard.release()


if __name__ == "__main__":
    unittest.main()
