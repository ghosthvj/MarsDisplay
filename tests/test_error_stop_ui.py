"""Configuration exposes tray Stop after errors without changing retry authority."""
from unittest.mock import patch
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from mars_display.usb_transport import UsbError
import test_brightness_ui as native_fixture
import test_tray as fixture


class ErrorStopUiTests(unittest.TestCase):
    setUp = fixture.TrayTests.setUp
    tearDown = fixture.TrayTests.tearDown

    def test_native_start_error_can_stop_from_configuration_without_retry(self):
        shell = native_fixture.BrightnessUiTests.make(self)
        raw = self.store.path.read_bytes()
        self.output.fail_open = True
        shell.show_settings()
        shell.dialog.capture_action.click()
        fixture.until(lambda: shell.dialog.runtime.text() == 'Error')
        button = shell.dialog.error_stop_action
        self.assertEqual(button.text(), 'Stop capture')
        self.assertTrue(button.isVisible())
        self.assertTrue(button.isEnabled())
        self.assertEqual(shell.dialog.capture_action.text(), 'Start capture')
        self.assertTrue(shell.start_action.isEnabled())
        before = shell.coordinator.snapshot()
        with patch.object(shell.coordinator, 'stop', wraps=shell.coordinator.stop) as stop, \
                patch.object(shell.coordinator, 'start', wraps=shell.coordinator.start) as start:
            QTest.keyClick(button, Qt.Key.Key_Space)
            stop.assert_called_once_with()
            start.assert_not_called()
        after = shell.coordinator.snapshot()
        self.assertEqual(after.state, 'stopped')
        self.assertTrue(shell.dialog.save.isEnabled())
        self.assertFalse(shell.dialog.url.isReadOnly())
        self.assertTrue(button.isHidden())
        self.assertEqual((after.frames_sent, after.failures, after.retries),
                         (before.frames_sent, before.failures, before.retries))
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(self.output.events, ['close'])

    def test_exhausted_simulation_error_uses_same_stop_and_preserves_start(self):
        shell = fixture.TrayTests.make(self, wait_override=lambda cancel, seconds: cancel.is_set())
        raw = self.store.path.read_bytes()
        self.session.read_error = True
        self.session.allow_open.set()
        self.session.allow_close.set()
        shell.dialog.capture_action.click()
        fixture.until(lambda: shell.dialog.runtime.text() == 'Error')
        button = shell.dialog.error_stop_action
        self.assertFalse(button.isHidden())
        self.assertTrue(button.isEnabled())
        self.assertEqual(shell.dialog.capture_action.text(), 'Start capture')
        self.assertEqual(shell.coordinator.snapshot().failures, 6)
        button.click()
        self.assertEqual(shell.coordinator.snapshot().state, 'stopped')
        self.assertEqual(shell.coordinator.snapshot().failures, 6)
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        self.assertEqual(shell.dialog.message.text(), '')
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertTrue(shell.dialog.save.isEnabled())

    def test_saved_brightness_survives_error_stop_and_explicit_restart(self):
        from hashlib import sha256

        shell = native_fixture.BrightnessUiTests.make(self)
        shell.configured = shell.coordinator.enable_brightness(
            acknowledge_legacy_incompatibility=True)
        shell.refresh()
        shell.dialog.brightness.setValue(1)
        digest = lambda: sha256(self.store.path.read_bytes()).hexdigest()
        original = digest()
        self.assertEqual(self.output.events, [])
        self.output.fail_open = True
        shell.dialog.capture_action.click()
        fixture.until(lambda: shell.dialog.runtime.text() == 'Error')
        before = shell.coordinator.snapshot()
        self.assertFalse(shell.dialog.brightness.isEnabled())
        self.assertEqual(digest(), original)
        shell.dialog.error_stop_action.click()
        after = shell.coordinator.snapshot()
        self.assertEqual(after.state, 'stopped')
        self.assertEqual((after.frames_sent, after.failures, after.retries),
                         (before.frames_sent, before.failures, before.retries))
        self.assertEqual(digest(), original)
        self.assertTrue(shell.dialog.brightness.isEnabled())
        self.assertEqual(shell.dialog.brightness.value(), 1)
        self.assertEqual(self.store.load().brightness_percent, 40)
        self.assertEqual(self.output.events, ['close'])
        self.output.fail_open = False
        shell.dialog.capture_action.click()
        self.assertTrue(self.gate.entered.wait(1))
        shell.refresh()
        self.assertEqual(shell.coordinator.snapshot().brightness_applied, 40)
        self.assertEqual(digest(), original)

    def test_stop_does_not_clear_uncertain_cleanup_or_bypass_exit(self):
        shell = native_fixture.BrightnessUiTests.make(self)
        self.output.fail_open = True
        raw = self.store.path.read_bytes()
        with patch.object(self.output, 'close', side_effect=UsbError('close', ownership_uncertain=True)):
            shell.dialog.capture_action.click()
            fixture.until(lambda: shell.dialog.runtime.text() == 'Error')
        button = shell.dialog.error_stop_action
        self.assertTrue(button.isEnabled())
        button.click()
        self.assertEqual(shell.coordinator.snapshot().state, 'error')
        self.assertTrue(shell.coordinator.snapshot().ownership_uncertain)
        self.assertFalse(shell.dialog.save.isEnabled())
        self.assertEqual(self.store.path.read_bytes(), raw)
        shell.exit_action.trigger()
        self.assertFalse(shell.coordinator.snapshot().exit_ready)
        self.assertTrue(button.isHidden())
        self.assertFalse(button.isEnabled())
        with patch.object(shell.coordinator, 'stop') as stop:
            button.click()
            stop.assert_not_called()


if __name__ == '__main__':
    unittest.main()
