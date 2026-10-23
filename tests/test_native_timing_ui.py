"""Read-only native timing in a modeless Logs window; no extra capture."""
from dataclasses import replace
import unittest
from unittest.mock import patch
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QPalette
from mars_display import lifecycle
import test_tray as fixture


class TimingUITests(unittest.TestCase):
    setUp = fixture.TrayTests.setUp
    tearDown = fixture.TrayTests.tearDown
    make = fixture.TrayTests.make

    def test_logs_button_opens_reusable_observer_window_like_preview(self):
        shell = self.make()
        dialog = shell.dialog
        original = self.store.path.read_bytes()
        before = shell.coordinator.snapshot()
        shell.show_settings()
        self.assertEqual(dialog.logs_action.text(), 'Logs')
        self.assertEqual(dialog.logs_action.parentWidget(), dialog.preview_action.parentWidget())
        self.assertFalse(dialog.logs_action.autoDefault())
        self.assertFalse(dialog.logs_window.isVisible())
        dialog.logs_action.click()
        popup = dialog.logs_window
        self.assertEqual(popup.windowTitle(), 'MarsDisplay — Logs')
        self.assertTrue(popup.isWindow())
        self.assertTrue(popup.isVisible())
        self.assertFalse(popup.isModal())
        self.assertTrue(popup.empty.isVisible())
        self.assertIn('No native timing', popup.empty.text())
        self.assertFalse(dialog.body.isAncestorOf(dialog.native_timing))
        popup.ensurePolished()
        light = popup.palette().color(QPalette.ColorRole.Window).name()
        dialog.theme_switch.click()
        fixture.APP.processEvents()
        self.assertNotEqual(popup.palette().color(QPalette.ColorRole.Window).name(), light)
        popup.close_action.click()
        self.assertFalse(popup.isVisible())
        dialog.logs_action.click()
        self.assertIs(dialog.logs_window, popup)
        self.assertTrue(popup.isVisible())
        fixture.APP.sendEvent(popup, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                             Qt.KeyboardModifier.NoModifier))
        self.assertFalse(popup.isVisible())
        dialog.logs_action.click()
        with patch.object(shell.coordinator, 'snapshot', return_value=replace(
                before, exit_requested=True)):
            shell.refresh()
            self.assertFalse(popup.isVisible())
            self.assertFalse(dialog.logs_action.isEnabled())
            shell.show_logs()
            self.assertFalse(popup.isVisible())
        self.assertEqual(shell.coordinator.snapshot(), before)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(fixture.APP.quit_requests, 0)

    def test_numeric_labels_scroll_footer_keyboard_and_no_extra_capture(self):
        shell = self.make()
        dialog = shell.dialog
        raw = self.store.path.read_bytes()
        before = shell.coordinator.snapshot()
        self.assertTrue(dialog.native_timing.isHidden())
        stage = lifecycle.TimingAggregate(2, .125, .0625, .1875, .125)
        report = lifecycle.NativeTiming(stage, stage, lifecycle.TimingAggregate())
        with patch.object(shell.coordinator, 'snapshot', return_value=replace(
                before, output_mode='native', native_timing=report)):
            shell.show_settings()
            dialog.logs_action.click()
            popup = dialog.logs_window
            popup.resize(600, 300)
            dialog.resize(600, 480)
            fixture.APP.processEvents()
            self.assertEqual(dialog.native_timing.text(),
                'Native timing — current/last Start; successful samples only (ms)\n'
                'Source read (observations): count 2; last 125.000; min 62.500; max 187.500; mean 125.000\n'
                'Host send (encoding / IPC / helper total): count 2; last 125.000; min 62.500; max 187.500; mean 125.000\n'
                'Cadence wait (non-cancelled): count 0; last —; min —; max —; mean —\n'
                'Helper frame decode (ms): unavailable (count 0)\n'
                'Helper identity resolution (ms): unavailable (count 0)\n'
                'Helper RGB565 encode (ms): unavailable (count 0)\n'
                'Helper packet writes (ms): unavailable (count 0)\n'
                'Helper queue drain (ms): unavailable (count 0)\n'
                'Host IPC body encode (ms): unavailable (count 0)\n'
                'Host exchange (includes helper work) (ms): unavailable (count 0)\n'
                'Helper orientation write (ms): unavailable (count 0)\n'
                'Helper bitmap-header write (ms): unavailable (count 0)\n'
                'Helper pixel writes (ms): unavailable (count 0)\n'
                'Write groups are subsets of total packet writes, not additional costs.\n'
                'Host send is not isolated serial write/drain or panel rendering. Counts are independent, not panel FPS.\n'
                'Host exchange includes helper work; do not add exchange and helper stages as separate costs.')
            self.assertEqual(dialog.native_timing.textFormat(), Qt.TextFormat.PlainText)
            measured = replace(report, decode=stage, identity=stage, encode=stage, write=stage,
                               drain=stage, body_encode=stage, exchange=stage,
                               orientation=stage, header=stage, pixels=stage)
            with patch.object(shell.coordinator, 'snapshot', return_value=replace(
                    before, output_mode='native', native_timing=measured)):
                shell.refresh()
                for title in ('Helper frame decode', 'Helper identity resolution',
                              'Helper RGB565 encode', 'Helper packet writes', 'Helper queue drain',
                              'Host IPC body encode', 'Host exchange (includes helper work)',
                              'Helper orientation write', 'Helper bitmap-header write', 'Helper pixel writes'):
                    self.assertIn(f'{title} (ms): count 2; last 125.000; min 62.500; '
                                  'max 187.500; mean 125.000', dialog.native_timing.text())
            shell.refresh()
            self.assertFalse(dialog.body.isAncestorOf(dialog.native_timing))
            self.assertTrue(popup.scroll_area.isAncestorOf(dialog.native_timing))
            self.assertFalse(popup.empty.isVisible())
            self.assertGreater(popup.scroll_area.verticalScrollBar().maximum(), 0)
            self.assertTrue(popup.close_action.isVisible())
            self.assertFalse(dialog.body.isAncestorOf(dialog.save))
            self.assertTrue(dialog.save.isVisible())
            self.assertLessEqual(dialog.footer.geometry().bottom(), dialog.height())
            self.assertEqual(dialog.minimumHeight(), dialog.maximumHeight())
            self.assertEqual(dialog.hint.text(), 'Capture is stopped. Settings can be saved.')
            dialog.url.setFocus()
            fixture.APP.sendEvent(dialog.url, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab,
                                                       Qt.KeyboardModifier.NoModifier))
            self.assertIsNot(fixture.APP.focusWidget(), dialog.url)
            fixture.APP.sendEvent(dialog, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                                   Qt.KeyboardModifier.NoModifier))
            self.assertFalse(dialog.isVisible())
            popup.close()
        shell.refresh()
        self.assertTrue(dialog.native_timing.isHidden())
        self.assertEqual(dialog.native_timing.text(), '')
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(shell.coordinator.snapshot(), before)
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(fixture.APP.quit_requests, 0)
