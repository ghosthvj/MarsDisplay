"""Exact output pixels and observer-only popup behavior; synthetic frames only."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QImage, QKeyEvent, QPalette

import test_tray as fixture
from mars_display.frames import RGBFrame
from mars_display.lifecycle import Snapshot, SourceSample
from mars_display.transport import SimulatedTransport


def patterned(width, height):
    pixels = bytes(channel for y in range(height) for x in range(width)
                   for channel in (x % 256, y % 256, (x + y) % 256))
    return RGBFrame(width, height, pixels, 1)


def assert_pixels(test, popup, frame):
    image = popup.image.pixmap().toImage().convertToFormat(QImage.Format.Format_RGB888)
    test.assertEqual((image.width(), image.height()), (frame.width, frame.height))
    test.assertEqual(bytes(image.constBits()), frame.rgb)
    test.assertFalse(popup.image.hasScaledContents())


class PreviewWidgetTests(unittest.TestCase):
    def test_exact_rgb_rows_orientation_and_no_repeat_conversion(self):
        from mars_display.preview import FramePreviewDialog
        popup = FramePreviewDialog()
        try:
            for width, height in ((320, 480), (480, 320)):
                frame = patterned(width, height)
                status = Snapshot(state="running", source_state="ready", latest_frame=frame,
                                  frames_sent=7, live_connected=True, data_stale=False)
                popup.update_snapshot(status)
                assert_pixels(self, popup, frame)
                key = popup.image.pixmap().cacheKey()
                popup.update_snapshot(status)
                self.assertEqual(popup.image.pixmap().cacheKey(), key)
                self.assertIn(f"{width} × {height}", popup.details.text())
                self.assertIn("Frame 7", popup.details.text())
                self.assertEqual(popup.details.textFormat(), Qt.TextFormat.PlainText)
        finally:
            popup.close()

    def test_empty_and_retained_status_do_not_claim_fresh_usb_output(self):
        from mars_display.preview import FramePreviewDialog
        popup = FramePreviewDialog()
        try:
            popup.update_snapshot(Snapshot())
            self.assertTrue(popup.image.pixmap().isNull())
            self.assertIn("No frame", popup.image.text())
            self.assertIn("Start capture", popup.image.text())
            status = Snapshot(state="stopped", source_state="stopped", latest_frame=fixture.FRAME,
                              frames_sent=1)
            popup.update_snapshot(status)
            assert_pixels(self, popup, fixture.FRAME)
            self.assertIn("Capture: stopped", popup.details.text())
            self.assertIn("Retained", popup.note.text())
            self.assertIn("not USB reception", popup.note.text())
        finally:
            popup.close()


class PreviewIntegrationTests(unittest.TestCase):
    setUp = fixture.TrayTests.setUp
    tearDown = fixture.TrayTests.tearDown
    make = fixture.TrayTests.make
    running = fixture.TrayTests.running

    def test_empty_popup_reuses_one_modeless_window_without_capture_or_settings_io(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        shell.dialog.preview_action.click()
        popup = shell.preview
        self.assertTrue(popup.isVisible())
        self.assertFalse(popup.isModal())
        shell.dialog.preview_action.click()
        self.assertIs(shell.preview, popup)
        fixture.APP.sendEvent(popup, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                              Qt.KeyboardModifier.NoModifier))
        self.assertFalse(popup.isVisible())
        shell.dialog.preview_action.click()
        self.assertTrue(popup.isVisible())
        self.assertEqual(self.created, ["coordinator"])
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(fixture.APP.quit_requests, 0)

    def test_visible_preview_follows_accepted_pixels_and_stop_retains_latest(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        with patch.object(self.session, "read", wraps=self.session.read) as read:
            self.running()
            shell.dialog.preview_action.click()
            popup = shell.preview
            assert_pixels(self, popup, fixture.FRAME)
            frame = patterned(480, 320)
            self.session.sample = SourceSample("ready", frame, True, False)
            self.next_sample.set()
            fixture.until(lambda: "Frame 2" in popup.details.text())
            assert_pixels(self, popup, frame)
            for _ in range(5):
                shell.refresh()
            self.assertEqual(read.call_count, 2)
            shell.stop_action.trigger()
            self.next_sample.set()
            self.session.allow_close.set()
            fixture.until(lambda: "Capture: stopped" in popup.details.text())
            assert_pixels(self, popup, frame)
            self.assertEqual(shell.coordinator.snapshot().frames_sent, 2)
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_loading_and_failed_send_retain_only_previously_accepted_frame(self):
        shell = self.make()
        self.running()
        shell.dialog.preview_action.click()
        popup = shell.preview
        self.session.sample = SourceSample("loading", live_connected=False, data_stale=True)
        self.next_sample.set()
        fixture.until(lambda: "Source: loading" in popup.details.text())
        assert_pixels(self, popup, fixture.FRAME)
        self.assertIn("Live connected: no; data stale: yes", popup.details.text())
        self.session.allow_close.set()
        self.session.sample = SourceSample("ready", patterned(480, 320), True, False)
        with patch.object(SimulatedTransport, "send", side_effect=RuntimeError("rejected output")):
            self.next_sample.set()
            fixture.until(lambda: "Capture: retrying" in popup.details.text())
            assert_pixels(self, popup, fixture.FRAME)
            self.assertEqual(shell.coordinator.snapshot().frames_sent, 1)

    def test_hidden_preview_releases_pixmap_reopens_current_and_tracks_session_theme(self):
        shell = self.make()
        self.running()
        shell.dialog.preview_action.click()
        popup = shell.preview
        popup.ensurePolished()
        light = popup.palette().color(QPalette.ColorRole.Window).name()
        shell.dialog.theme_switch.click()
        fixture.APP.processEvents()
        self.assertNotEqual(popup.palette().color(QPalette.ColorRole.Window).name(), light)
        popup.close()
        self.assertFalse(popup.isVisible())
        self.assertTrue(popup.image.pixmap().isNull())
        self.session.sample = SourceSample("ready", patterned(480, 320), True, False)
        self.next_sample.set()
        fixture.until(lambda: shell.coordinator.snapshot().frames_sent == 2)
        self.assertTrue(popup.image.pixmap().isNull())
        shell.dialog.preview_action.click()
        assert_pixels(self, popup, self.session.sample.frame)
        self.assertEqual(shell.dialog.property("theme"), "dark")
        self.assertEqual(shell.coordinator.snapshot().state, "running")

    def test_exit_hides_preview_and_preserves_owned_cleanup_acknowledgement(self):
        shell = self.make()
        self.running()
        shell.dialog.preview_action.click()
        popup = shell.preview
        shell.exit_action.trigger()
        self.assertFalse(popup.isVisible())
        self.assertFalse(shell.dialog.preview_action.isEnabled())
        shell.show_preview()
        self.assertFalse(popup.isVisible())
        self.next_sample.set()
        fixture.until(self.session.closing.is_set)
        self.assertEqual(fixture.APP.quit_requests, 0)
        self.session.allow_close.set()
        fixture.until(lambda: fixture.APP.quit_requests == 1)
