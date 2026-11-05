"""Native category navigation must not become a configuration operation."""
from dataclasses import replace
from unittest.mock import patch
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTabWidget

import test_tray as fixture


class SettingsTabsTests(unittest.TestCase):
    setUp = fixture.TrayTests.setUp
    tearDown = fixture.TrayTests.tearDown
    make = fixture.TrayTests.make

    def test_categories_group_controls_and_keep_chrome_persistent(self):
        shell = self.make()
        shell.show_settings()
        dialog = shell.dialog
        tabs = dialog.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],
                         ['Connection', 'Display', 'Startup', 'Diagnostics'])
        self.assertEqual(tabs.currentIndex(), 0)
        groups = ((dialog.url, dialog.device, dialog.identity, dialog.refresh_devices),
                  (dialog.brightness, dialog.enable_brightness),
                  (dialog.start_on_launch, dialog.start_with_windows, dialog.update_startup_path),
                  (dialog.source, dialog.output, dialog.metadata, dialog.frames))
        for index, widgets in enumerate(groups):
            for widget in widgets:
                self.assertTrue(tabs.widget(index).isAncestorOf(widget))
        for widget in (dialog.runtime_card, dialog.capture_action, dialog.footer):
            self.assertFalse(tabs.isAncestorOf(widget))
        self.assertTrue(dialog.footer.isAncestorOf(dialog.message))

    def test_keyboard_navigation_refresh_and_drafts_have_no_side_effects(self):
        shell = self.make()
        shell.show_settings()
        dialog = shell.dialog
        tabs = dialog.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        raw = self.store.path.read_bytes()
        before = shell.coordinator.snapshot()
        dialog.url.setText('http://draft.example')
        bar = tabs.tabBar()
        bar.setFocus()
        fixture.APP.processEvents()
        with patch.object(shell._startup_store, 'save') as startup:
            for key, index in ((Qt.Key.Key_Right, 1), (Qt.Key.Key_End, 3),
                               (Qt.Key.Key_Home, 0), (Qt.Key.Key_Left, 3)):
                QTest.keyClick(bar, key)
                self.assertEqual(tabs.currentIndex(), index)
                shell.refresh()
                self.assertEqual(tabs.currentIndex(), index)
                self.assertTrue(bar.hasFocus())
            startup.assert_not_called()
        with patch.object(shell.coordinator, 'snapshot', return_value=replace(before, frames_sent=123)):
            tabs.setCurrentIndex(1)
            shell.refresh()
            self.assertEqual(dialog.frames.text(), '123')
            self.assertFalse(dialog.frames.isVisible())
        tabs.setCurrentIndex(0)
        self.assertEqual(dialog.url.text(), 'http://draft.example')
        self.assertIsNone(dialog.identity.currentData())
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(shell.coordinator.snapshot(), before)
        self.assertFalse(self.session.opened.is_set())

    def test_save_routes_validation_to_connection_without_saving(self):
        shell = self.make()
        shell.show_settings()
        dialog = shell.dialog
        tabs = dialog.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        raw = self.store.path.read_bytes()
        before = shell.coordinator.snapshot()
        for text, target, message in (
                ('invalid', dialog.url, 'MARS URL must be HTTP(S)'),
                ('http://draft.example', dialog.identity,
                 'Select an explicit stable USB identity; no device was selected.')):
            dialog.url.setText(text)
            tabs.setCurrentIndex(3)
            dialog.save.click()
            fixture.APP.processEvents()
            self.assertEqual(tabs.currentIndex(), 0)
            self.assertTrue(target.hasFocus())
            self.assertIn(message, dialog.message.text())
            self.assertEqual(dialog.url.text(), text)
            self.assertEqual(self.store.path.read_bytes(), raw)
            self.assertEqual(shell.coordinator.snapshot(), before)
        self.assertFalse(self.session.opened.is_set())
