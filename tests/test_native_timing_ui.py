"""Read-only timing presentation in the existing scrollable status window."""
from dataclasses import replace
import unittest
from unittest.mock import patch
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from mars_display import lifecycle
import test_tray as fixture


class TimingUITests(unittest.TestCase):
    setUp = fixture.TrayTests.setUp
    tearDown = fixture.TrayTests.tearDown
    make = fixture.TrayTests.make

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
            self.assertTrue(dialog.scroll_area.isAncestorOf(dialog.native_timing))
            self.assertFalse(dialog.scroll_area.isAncestorOf(dialog.save))
            self.assertTrue(dialog.save.isVisible())
            self.assertLessEqual(dialog.footer.geometry().bottom(), dialog.height())
            self.assertGreater(dialog.scroll_area.verticalScrollBar().maximum(), 0)
            self.assertEqual(dialog.hint.text(), 'Capture is stopped. Settings can be saved.')
            dialog.url.setFocus()
            fixture.APP.sendEvent(dialog.url, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab,
                                                       Qt.KeyboardModifier.NoModifier))
            self.assertIsNot(fixture.APP.focusWidget(), dialog.url)
            fixture.APP.sendEvent(dialog, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                                   Qt.KeyboardModifier.NoModifier))
            self.assertFalse(dialog.isVisible())
        shell.refresh()
        self.assertTrue(dialog.native_timing.isHidden())
        self.assertEqual(dialog.native_timing.text(), '')
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(shell.coordinator.snapshot(), before)
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(fixture.APP.quit_requests, 0)
