"""Native-only configuration, explicit migration, and a complete fixed-height form."""
from dataclasses import replace
from unittest.mock import patch
import unittest

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QComboBox, QLabel, QMessageBox, QScrollArea

from mars_display.settings import NATIVE_IDENTITY, NATIVE_PROFILE
import test_native_output_ui as native_fixture
from test_output_configuration import device, native
import test_tray as fixture


class FixedNativeSettingsTests(unittest.TestCase):
    setUp = fixture.TrayTests.setUp
    tearDown = fixture.TrayTests.tearDown
    make = fixture.TrayTests.make
    answer = native_fixture.NativeOutputUiTests.answer

    def test_save_requires_explicit_usb_selection_and_migration_without_mode_selector(self):
        shell = self.make()
        raw = self.store.path.read_bytes()
        before = shell.coordinator.snapshot()
        shell.show_settings()
        self.assertFalse(any(combo.isVisible() and combo.accessibleName() == 'Output mode'
                             for combo in shell.dialog.findChildren(QComboBox)))
        shell.dialog.save.click()
        self.assertEqual(shell.dialog.message.text(),
                         'Select an explicit stable USB identity; no device was selected.')
        self.assertEqual(self.store.path.read_bytes(), raw)
        with patch('mars_display.tray.enumerate_devices', return_value=(device(),)):
            shell.dialog.refresh_devices.click()
        self.assertIsNone(shell.dialog.identity.currentData())
        shell.dialog.identity.setCurrentIndex(1)
        self.answer(QMessageBox.StandardButton.No)
        shell.dialog.save.click()
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertFalse(self.store.schema1_backup_path.exists())
        self.answer(QMessageBox.StandardButton.Yes)
        with patch('mars_display.lifecycle.enumerate_devices', return_value=(device(),)):
            shell.dialog.save.click()
        saved = self.store.load()
        self.assertEqual((saved.mars_url, saved.output_mode, saved.device_identity,
                          saved.native_profile, saved.schema_version),
                         ('https://mars.example', 'native', NATIVE_IDENTITY, NATIVE_PROFILE, 2))
        self.assertEqual(self.store.schema1_backup_path.read_bytes(), raw)
        self.assertEqual(shell.coordinator.snapshot(), before)
        self.assertFalse(self.session.opened.is_set())

    def test_usb_selector_and_refresh_share_one_row(self):
        shell = self.make()
        shell.show_settings()
        for width in (650, 900):
            shell.dialog.resize(width, 480)
            fixture.APP.processEvents()
            selector = shell.dialog.identity.geometry()
            refresh = shell.dialog.refresh_devices.geometry()
            self.assertLessEqual(abs(selector.center().y() - refresh.center().y()), 1)
            self.assertLess(selector.right(), refresh.left())
            self.assertLess(refresh.right(), shell.dialog.identity.parentWidget().width())

    def test_legacy_buttons_and_refresh_explanation_are_hidden_not_removed(self):
        shell = self.make()
        shell.show_settings()
        self.assertTrue(shell.dialog.export_settings.isHidden())
        self.assertTrue(shell.dialog.restore_settings.isHidden())
        self.assertFalse(any(label.isVisible() and label.text().startswith('Refresh is passive;')
                             for label in shell.dialog.findChildren(QLabel)))
        self.assertEqual(shell.coordinator.snapshot().state, 'stopped')
        self.assertFalse(self.session.opened.is_set())

    def test_fixed_window_and_footer_fit_the_available_desktop(self):
        shell = self.make()
        shell.show_settings()
        fixture.APP.processEvents()
        dialog = shell.dialog
        available = dialog.screen().availableGeometry()
        self.assertTrue(available.contains(dialog.frameGeometry()),
                        (available.getRect(), dialog.frameGeometry().getRect()))
        for button in (dialog.logs_action, dialog.preview_action, dialog.save):
            bounds = QRect(button.mapToGlobal(QPoint()), button.size())
            self.assertTrue(available.contains(bounds), (button.text(), bounds.getRect()))
        self.assertFalse(self.session.opened.is_set())

    def test_fixed_height_keeps_configuration_footer_and_error_visible_without_scroll(self):
        shell = self.make()
        dialog = shell.dialog
        shell.show_settings()
        height = dialog.height()
        self.assertEqual(dialog.minimumHeight(), dialog.maximumHeight())
        for area in dialog.findChildren(QScrollArea):
            self.assertFalse(area.isAncestorOf(dialog.url))
        message = ('Native delivery is uncertain; the previous host-accepted frame is retained. '
                   'Exit is blocked: check owned browser/output resources; resolve cleanup before '
                   'restarting MarsDisplay. Do not close your normal browser.')
        for configured in (native(), replace(native(), schema_version=3, brightness_percent=40)):
            status = replace(shell.coordinator.snapshot(), state='error', source_state='error',
                             output_mode='native', output_state='native-uncertain',
                             ownership_uncertain=True)
            with patch.object(shell, 'configured', configured), patch.object(
                    shell.coordinator, 'snapshot', return_value=status):
                shell.refresh()
                dialog.show_message(message)
                for width in (650, 900):
                    dialog.resize(width, 400)
                    fixture.APP.processEvents()
                    self.assertEqual(dialog.height(), height)
                    self.assertEqual(dialog.message.text(), message)
                    fixture.until(lambda: dialog.message.height() >=
                                  dialog.message.heightForWidth(dialog.message.width()))
                    for widget in (dialog.url, dialog.identity, dialog.refresh_devices,
                                   dialog.message, dialog.logs_action, dialog.preview_action, dialog.save):
                        self.assertTrue(widget.isVisible())
                        self.assertTrue(widget.parentWidget().rect().contains(widget.geometry()))
                    for label in dialog.body.findChildren(QLabel):
                        if label.isVisible() and label.text():
                            self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()),
                                                    label.text())
                    self.assertLessEqual(dialog.footer.geometry().bottom(), height)
        self.assertFalse(self.session.opened.is_set())
