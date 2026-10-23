"""Five-position native slider with explicit migration and isolated persistence."""
from unittest.mock import patch
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from mars_display.lifecycle import Coordinator
from mars_display.settings import Settings
from mars_display.tray import create_shell
from test_lifecycle import Source, GateWait
from test_brightness_lifecycle import BrightOutput
import test_native_output_ui as native_fixture
from test_output_configuration import native, device
import test_tray as fixture


class BrightnessUiTests(unittest.TestCase):
    setUp = fixture.TrayTests.setUp
    tearDown = fixture.TrayTests.tearDown
    answer = native_fixture.NativeOutputUiTests.answer

    def make(self):
        self.store.save(Settings('https://mars.example'))
        self.store.migrate_to_v2(native(), acknowledge_legacy_incompatibility=True)
        self.original = self.store.path.read_bytes()
        self.output = BrightOutput()
        self.gate = GateWait()
        self.shell = create_shell(fixture.APP, self.store, lambda: Coordinator(
            self.store, lambda _: Source(), transport_context_factory=lambda _: self.output,
            inventory_provider=lambda: (device(),), wait=self.gate))
        return self.shell

    def enable(self):
        button = self.shell.dialog.enable_brightness
        self.answer(QMessageBox.StandardButton.Yes)
        button.click()

    def test_exact_positions_migration_cancel_and_persist_without_usb(self):
        shell = self.make()
        dialog = shell.dialog
        slider = dialog.brightness
        self.assertEqual((slider.minimum(), slider.maximum(), slider.value()), (0, 4, 4))
        self.assertFalse(slider.isEnabled())
        self.answer(QMessageBox.StandardButton.No)
        dialog.enable_brightness.click()
        self.assertEqual(self.store.path.read_bytes(), self.original)
        self.assertFalse(self.store.pre_brightness_backup_path.exists())
        self.enable()
        self.assertTrue(slider.isEnabled())
        self.assertEqual(self.store.pre_brightness_backup_path.read_bytes(), self.original)
        dialog.url.setText('https://unsaved.example')
        for position, percent in enumerate((20, 40, 60, 80, 100)):
            slider.setValue(position)
            self.assertEqual(self.store.load().brightness_percent, percent)
            self.assertEqual(self.store.load().mars_url, 'https://mars.example')
            self.assertIn(f'{percent}%', dialog.brightness_status.text())
        self.assertEqual(self.output.events, [])
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        self.assertIn('Start', dialog.brightness_status.text())

    def test_keyboard_live_change_stop_and_schema3_ordinary_save(self):
        shell = self.make()
        self.enable()
        shell.dialog.brightness.setValue(2)
        shell.start_action.trigger()
        self.assertTrue(self.gate.entered.wait(1))
        shell.refresh()
        self.assertTrue(shell.dialog.brightness.isEnabled())
        self.assertFalse(shell.dialog.enable_brightness.isEnabled())
        self.assertIn('Host-completed: 60%', shell.dialog.brightness_status.text())
        QTest.keyClick(shell.dialog.brightness, Qt.Key.Key_Left)
        self.assertEqual(self.store.load().brightness_percent, 40)
        self.assertIn('Requested: 40%', shell.dialog.brightness_status.text())
        self.assertEqual(self.output.events.count('open'), 1)
        shell.stop_action.trigger()
        self.assertTrue(shell.coordinator.wait_stopped(2))
        shell.refresh()
        self.assertIn('Start', shell.dialog.brightness_status.text())
        shell.dialog.url.setText('https://saved.example')
        with patch('mars_display.lifecycle.enumerate_devices', return_value=(device(),)):
            shell.dialog.save.click()
        saved = self.store.load()
        self.assertEqual((saved.schema_version, saved.brightness_percent, saved.mars_url),
                         (3, 40, 'https://saved.example'))
        shell.coordinator.request_exit()
        shell.refresh()
        self.assertFalse(shell.dialog.brightness.isEnabled())

    def test_enable_rechecks_authority_after_modal_and_restore_preserves_bytes(self):
        shell = self.make()
        button = shell.dialog.enable_brightness
        self.answer(QMessageBox.StandardButton.Yes, shell.coordinator.start)
        button.click()
        self.assertEqual(self.store.path.read_bytes(), self.original)
        self.assertFalse(self.store.pre_brightness_backup_path.exists())
        self.assertIn('stopped', shell.dialog.message.text())
        shell.coordinator.stop()
        self.assertTrue(shell.coordinator.wait_stopped(2))
        shell.refresh()
        self.enable()
        shell.dialog.brightness.setValue(0)
        self.answer(QMessageBox.StandardButton.Yes)
        shell.dialog.restore_brightness.click()
        self.assertEqual(self.store.path.read_bytes(), self.original)
        self.assertFalse(shell.dialog.brightness.isEnabled())
        self.assertEqual(shell.configured.schema_version, 2)

    def test_slider_rejection_restores_saved_value_and_small_window_remains_scrollable(self):
        shell = self.make()
        self.enable()
        raw = self.store.path.read_bytes()
        from mars_display.settings import SettingsError
        with patch.object(self.store, 'save', side_effect=SettingsError('Cannot save brightness.')):
            shell.dialog.brightness.setValue(0)
        self.assertEqual(shell.dialog.brightness.value(), 4)
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertIn('Cannot save brightness.', shell.dialog.message.text())
        shell.show_settings()
        shell.dialog.resize(600, 480)
        shell.dialog.set_dark_mode(True)
        fixture.APP.processEvents()
        self.assertTrue(shell.dialog.scroll_area.isAncestorOf(shell.dialog.brightness))
        self.assertTrue(shell.dialog.save.isVisible())
        self.assertLessEqual(shell.dialog.footer.geometry().bottom(), shell.dialog.height())
        self.assertGreater(shell.dialog.scroll_area.verticalScrollBar().maximum(), 0)


if __name__ == '__main__':
    unittest.main()
