"""Compact settings geometry and nonzero Wayland maximum-size hints."""
import sys
import unittest
from unittest.mock import patch

from PySide6.QtCore import QRect
from PySide6.QtGui import QScreen

from mars_display.tray import QApplication, SettingsDialog
from test_output_configuration import native
from test_tray import APP


class WindowGeometryTests(unittest.TestCase):
    def dialog(self, host, backend):
        with patch.object(sys, "platform", host), patch.object(
                QApplication, "platformName", return_value=backend), patch.object(
                QScreen, "availableGeometry", return_value=QRect(0, 0, 1920, 1080)):
            dialog = SettingsDialog(native())
        self.addCleanup(dialog.close)
        self.addCleanup(dialog.logs_window.close)
        return dialog

    def test_linux_wayland_avoids_unbounded_width_with_fixed_height(self):
        for backend in ("wayland", "wayland-egl"):
            with self.subTest(backend=backend):
                dialog = self.dialog("linux", backend)
                # Qt encodes its default 16777215 maximum as zero in xdg-shell.
                # COSMIC mishandles that zero paired with a fixed height.
                self.assertEqual(dialog.maximumWidth(), 650)
                self.assertEqual(dialog.minimumWidth(), 650)
                self.assertEqual(dialog.minimumHeight(), 760)
                self.assertEqual(dialog.maximumHeight(), 760)
                dialog.show()
                APP.processEvents()
                self.assertEqual(dialog.windowHandle().maximumWidth(), 650)
                self.assertEqual(dialog.windowHandle().maximumHeight(), 760)
                dialog.close()

    def test_wayland_hint_keeps_compact_running_form_and_fixed_size(self):
        dialog = self.dialog("linux", "wayland")
        dialog.start_with_windows.hide()
        dialog.windows_startup_hint.hide()
        dialog.runtime.setText("Running")
        dialog.source.setText("Ready")
        dialog.capture_action.setText("Stop capture")
        dialog.output.setText(
            "Native USB — native-host-complete (host completion, not panel acknowledgement)")
        dialog.metadata.setText("Live connected: yes; data stale: no")
        dialog.hint.setText("Capture is running. Stop capture to save changes.")
        dialog.show()
        APP.processEvents()
        self.assertEqual((dialog.width(), dialog.height()), (650, 760))
        for dark in (False, True):
            dialog.set_dark_mode(dark)
            for width in (900, 650):
                dialog.resize(width, 760)
                APP.processEvents()
                self.assertEqual((dialog.width(), dialog.height()), (650, 760))
                self.assertEqual(dialog.scroll_area.horizontalScrollBar().maximum(), 0)
                for label in (dialog.output, dialog.device, dialog.hint):
                    self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
                for button in (dialog.logs_action, dialog.preview_action, dialog.save):
                    self.assertTrue(button.isVisible())
                    self.assertTrue(button.parentWidget().rect().contains(button.geometry()))

    def test_small_desktop_resize_and_reopen(self):
        for backend in ("wayland", "wayland-egl", "xcb", "offscreen"):
            with self.subTest(backend=backend), patch.object(
                    sys, "platform", "linux"), patch.object(
                    QApplication, "platformName", return_value=backend), patch.object(
                    QScreen, "availableGeometry", return_value=QRect(0, 0, 800, 600)):
                dialog = SettingsDialog(None)
                try:
                    dialog.show()
                    APP.processEvents()
                    self.assertEqual((dialog.width(), dialog.height()), (650, 552))
                    for requested, expected in ((400, 650), (1280, 650), (650, 650)):
                        dialog.resize(requested, 900)
                        APP.processEvents()
                        self.assertEqual((dialog.width(), dialog.height()), (expected, 552))
                        self.assertEqual(dialog.scroll_area.horizontalScrollBar().maximum(), 0)
                        self.assertTrue(dialog.rect().contains(dialog.footer.geometry()))
                        for button in (dialog.logs_action, dialog.preview_action, dialog.save):
                            self.assertTrue(button.isVisible())
                            self.assertTrue(button.parentWidget().rect().contains(button.geometry()))
                    dialog.hide()
                    dialog.show()
                    APP.processEvents()
                    self.assertEqual((dialog.width(), dialog.height()), (650, 552))
                finally:
                    dialog.logs_window.close()
                    dialog.close()

    def test_windows_and_other_backends_keep_fixed_size_limits(self):
        for host, backend in (("win32", "windows"), ("linux", "xcb"),
                              ("linux", "offscreen"), ("win32", "wayland")):
            with self.subTest(host=host, backend=backend):
                dialog = self.dialog(host, backend)
                self.assertEqual(dialog.maximumWidth(), 650)
                self.assertEqual(dialog.minimumWidth(), 650)
                self.assertEqual((dialog.width(), dialog.height()), (650, 760))
                self.assertEqual(dialog.minimumHeight(), dialog.maximumHeight())
