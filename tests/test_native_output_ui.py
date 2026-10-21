"""Explicit native drafts and real modal admission; no host inventory or ports."""
from dataclasses import replace
from unittest.mock import patch
import unittest

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import test_tray as fixture
from test_output_configuration import device
from mars_display.settings import Settings, SettingsStore, NATIVE_IDENTITY, NATIVE_PROFILE
from mars_display.preview import FramePreviewDialog


class NativeOutputUiTests(unittest.TestCase):
    setUp = fixture.TrayTests.setUp
    tearDown = fixture.TrayTests.tearDown
    make = fixture.TrayTests.make

    def draft(self):
        dialog = self.shell.dialog
        dialog.output_mode.setCurrentIndex(1)
        with patch('mars_display.tray.enumerate_devices', return_value=(device(),)):
            dialog.refresh_devices.click()
        dialog.identity.setCurrentIndex(1)

    def answer(self, answer, during=None):
        def respond():
            modal = QApplication.activeModalWidget()
            self.assertIsInstance(modal, QMessageBox)
            self.assertEqual(modal.defaultButton(), modal.button(QMessageBox.StandardButton.No))
            self.assertEqual(modal.textFormat(), Qt.TextFormat.PlainText)
            if during:
                during()
            modal.button(answer).click()
        QTimer.singleShot(0, respond)

    def test_passive_draft_explicit_selection_keyboard_and_footer(self):
        with patch('mars_display.tray.enumerate_devices') as inventory:
            shell = self.make()
            shell.refresh()
            inventory.assert_not_called()
        raw = self.store.path.read_bytes()
        before = shell.coordinator.snapshot()
        dialog = shell.dialog
        dialog.output_mode.setCurrentIndex(1)
        with patch('mars_display.tray.enumerate_devices', return_value=(device(),)) as inventory:
            dialog.refresh_devices.click()
            inventory.assert_called_once()
        self.assertIsNone(dialog.identity.currentData())
        dialog.save.click()
        self.assertEqual(dialog.message.text(), 'Select an explicit stable USB identity; no device was selected.')
        shell.show_settings()
        dialog.resize(600, 480)
        dialog.identity.setFocus()
        QTest.keyClick(dialog.identity, Qt.Key.Key_Down)
        self.assertEqual(dialog.identity.currentData(), NATIVE_IDENTITY)
        fixture.APP.processEvents()
        for widget in (dialog.output_mode, dialog.identity, dialog.refresh_devices,
                       dialog.export_settings, dialog.restore_settings):
            self.assertTrue(dialog.scroll_area.isAncestorOf(widget))
        self.assertTrue(dialog.save.isVisible())
        self.assertLessEqual(dialog.footer.geometry().bottom(), dialog.height())
        self.assertGreater(dialog.scroll_area.verticalScrollBar().maximum(), 0)
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(shell.coordinator.snapshot(), before)

    def test_migration_no_then_yes_preserves_backup_and_schema2_url_edit(self):
        shell = self.make()
        raw = self.store.path.read_bytes()
        self.draft()
        self.answer(QMessageBox.StandardButton.No)
        shell.dialog.save.click()
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertFalse(self.store.schema1_backup_path.exists())
        self.answer(QMessageBox.StandardButton.Yes)
        with patch('mars_display.lifecycle.enumerate_devices', return_value=(device(),)):
            shell.dialog.save.click()
            shell.dialog.url.setText('https://changed.example')
            shell.dialog.save.click()
        self.assertEqual(self.store.load(), Settings('https://changed.example', NATIVE_IDENTITY, 2, 'native', NATIVE_PROFILE))
        self.assertEqual(self.store.schema1_backup_path.read_bytes(), raw)
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        self.assertFalse(self.session.opened.is_set())

    def test_modal_start_rechecks_authority_and_preserves_bytes(self):
        shell = self.make()
        raw = self.store.path.read_bytes()
        self.draft()
        self.answer(QMessageBox.StandardButton.Yes, shell.coordinator.start)
        with patch('mars_display.lifecycle.enumerate_devices') as inventory:
            shell.dialog.save.click()
            inventory.assert_not_called()
        self.assertEqual(shell.dialog.message.text(), 'Settings can be saved only while stopped.')
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertFalse(self.store.schema1_backup_path.exists())
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        for widget in (shell.dialog.output_mode, shell.dialog.identity,
                       shell.dialog.refresh_devices, shell.dialog.export_settings,
                       shell.dialog.restore_settings):
            self.assertFalse(widget.isEnabled())

    def test_fresh_save_rejects_disappeared_device(self):
        shell = self.make()
        raw = self.store.path.read_bytes()
        self.draft()
        self.answer(QMessageBox.StandardButton.Yes)
        with patch('mars_display.lifecycle.enumerate_devices', return_value=()):
            shell.dialog.save.click()
        self.assertEqual(shell.dialog.message.text(), 'Selected native screen is unavailable or ambiguous; refresh selection before saving.')
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertFalse(self.store.schema1_backup_path.exists())
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)

    def test_export_restore_and_restored_form(self):
        shell = self.make()
        original = self.store.load()
        raw = self.store.path.read_bytes()
        self.draft()
        self.answer(QMessageBox.StandardButton.Yes)
        with patch('mars_display.lifecycle.enumerate_devices', return_value=(device(),)):
            shell.dialog.save.click()
        destination = self.store.path.parent / 'export.json'
        with patch('mars_display.tray.QFileDialog.getSaveFileName', return_value=(str(destination), '')):
            shell.dialog.export_settings.click()
        self.assertEqual(SettingsStore(destination).load().schema_version, 1)
        self.answer(QMessageBox.StandardButton.Yes)
        shell.dialog.restore_settings.click()
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(shell.configured, original)
        self.assertEqual(shell.dialog.output_mode.currentData(), 'simulated')
        shell.dialog.url.setText('https://restored.example')
        shell.dialog.save.click()
        self.assertEqual(self.store.load(), replace(original, mars_url='https://restored.example'))
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)

    def test_export_real_file_modal_rechecks_start(self):
        shell = self.make()
        raw = self.store.path.read_bytes()
        destination = self.store.path.parent / 'blocked.json'
        original = QFileDialog.getSaveFileName

        def respond():
            modal = QApplication.activeModalWidget()
            self.assertIsInstance(modal, QFileDialog)
            shell.coordinator.start()
            modal.selectFile(str(destination))
            modal.accept()

        QTimer.singleShot(0, respond)
        with patch('mars_display.tray.QFileDialog.getSaveFileName',
                   side_effect=lambda *args: original(*args, options=QFileDialog.Option.DontUseNativeDialog)):
            shell.dialog.export_settings.click()
        self.assertEqual(shell.dialog.message.text(), 'Settings can be saved only while stopped.')
        self.assertFalse(destination.exists())
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)

    def test_restore_real_modal_rechecks_start(self):
        shell = self.make()
        self.draft()
        self.answer(QMessageBox.StandardButton.Yes)
        with patch('mars_display.lifecycle.enumerate_devices', return_value=(device(),)):
            shell.dialog.save.click()
        # Switch explicitly to Simulation so the legacy fixture can start.
        shell.dialog.output_mode.setCurrentIndex(0)
        shell.dialog.save.click()
        raw = self.store.path.read_bytes()
        backup = self.store.schema1_backup_path.read_bytes()
        self.answer(QMessageBox.StandardButton.Yes, shell.coordinator.start)
        shell.dialog.restore_settings.click()
        self.assertEqual(shell.dialog.message.text(), 'Settings can be saved only while stopped.')
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(self.store.schema1_backup_path.read_bytes(), backup)
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)

    def test_duplicate_selection_and_inventory_error_preserve_settings(self):
        from mars_display.devices import DeviceInventoryError
        shell = self.make()
        raw = self.store.path.read_bytes()
        shell.dialog.output_mode.setCurrentIndex(1)
        with patch('mars_display.tray.enumerate_devices', return_value=(device(), device('COM8'))):
            shell.dialog.refresh_devices.click()
        shell.dialog.identity.setCurrentIndex(1)
        shell.dialog.save.click()
        self.assertEqual(shell.dialog.message.text(),
                         'Selected USB identity is ambiguous; disconnect duplicates or identify the hardware before selecting.')
        with patch('mars_display.tray.enumerate_devices', side_effect=DeviceInventoryError(
                'Cannot list USB serial descriptors; check system device access and retry.')):
            shell.dialog.refresh_devices.click()
        self.assertEqual(shell.dialog.message.text(),
                         'Cannot list USB serial descriptors; check system device access and retry.')
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertFalse(self.store.schema1_backup_path.exists())
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)

    def test_native_cleanup_uncertainty_retains_lock_and_configuration_guards(self):
        from mars_display.lifecycle import Coordinator
        from mars_display.transport import SimulatedTransport
        from mars_display.tray import create_shell, SingleInstanceGuard
        self.store.save(Settings('https://mars.example'))
        self.store.migrate_to_v2(Settings('https://mars.example', NATIVE_IDENTITY, 2,
                                        'native', NATIVE_PROFILE),
                                 acknowledge_legacy_incompatibility=True)
        controller = Coordinator(self.store, lambda _: self.session,
                                 transport_context_factory=lambda _: SimulatedTransport())
        self.shell = create_shell(fixture.APP, self.store, lambda: controller)
        raw = self.store.path.read_bytes()
        self.session.cleanup_error = True
        self.session.allow_open.set()
        self.shell.start_action.trigger()
        fixture.until(lambda: controller.snapshot().frames_sent == 1)
        self.shell.exit_action.trigger()
        self.session.allow_close.set()
        fixture.until(lambda: self.shell.dialog.runtime.text() == 'error')
        status = controller.snapshot()
        self.assertTrue(status.ownership_uncertain)
        self.assertFalse(status.exit_ready)
        self.assertFalse(status.worker_alive)
        self.assertEqual(fixture.APP.quit_requests, 0)
        guard = SingleInstanceGuard(self.store)
        try:
            self.assertFalse(guard.acquire())
        finally:
            guard.release()
        for widget in (self.shell.dialog.save, self.shell.dialog.output_mode,
                       self.shell.dialog.refresh_devices, self.shell.dialog.export_settings,
                       self.shell.dialog.restore_settings):
            self.assertFalse(widget.isEnabled())
        self.assertIn('native-cleanup-uncertain', self.shell.dialog.output.text())
        self.assertIn('Exit is blocked', self.shell.dialog.message.text())
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(status.frames_sent, 1)

    def test_truthful_native_status_and_neutral_retained_preview(self):
        shell = self.make()
        before = shell.coordinator.snapshot()
        for state in ('native-opening', 'native-host-complete', 'native-error', 'native-cleanup-uncertain'):
            status = replace(before, output_mode='native', output_state=state,
                             latest_frame=fixture.FRAME, frames_sent=1)
            with patch.object(shell.coordinator, 'snapshot', return_value=status):
                shell.refresh()
                self.assertEqual(shell.dialog.output.text(), f'Native USB — {state} (host completion, not panel acknowledgement)')
                self.assertEqual(shell.tray.toolTip(), 'MarsDisplay — native output')
            popup = FramePreviewDialog()
            try:
                popup.update_snapshot(status)
                self.assertIn('accepted by host output', popup.note.text())
                self.assertNotIn('accepted by simulated', popup.note.text())
                self.assertIn('not USB reception', popup.note.text())
                self.assertEqual(popup.image.pixmap().width(), 320)
            finally:
                popup.close()
        self.assertEqual(shell.coordinator.snapshot(), before)

