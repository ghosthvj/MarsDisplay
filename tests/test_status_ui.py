"""Visible state labels and icons are observers, not lifecycle state changes."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

import test_tray as fixture


class StatusUITests(unittest.TestCase):
    setUp = fixture.TrayTests.setUp
    tearDown = fixture.TrayTests.tearDown
    make = fixture.TrayTests.make

    def test_visible_states_are_capitalized_without_changing_backend_or_controls(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        before = shell.coordinator.snapshot()
        for state, title in (
            ('running', 'Running'), ('stopped', 'Stopped'), ('starting', 'Starting'),
            ('stopping', 'Stopping'), ('error', 'Error'), ('retrying', 'Recovering (retrying)'),
        ):
            with self.subTest(state=state), patch.object(
                    shell.coordinator, 'snapshot', return_value=replace(before, state=state)):
                shell.refresh()
                self.assertEqual(shell.dialog.runtime.text(), title)
                self.assertEqual(shell.dialog.runtime.accessibleName(), title)
                self.assertEqual(shell.coordinator.snapshot().state, state)
                self.assertEqual(shell.dialog.runtime.textFormat(), Qt.TextFormat.PlainText)
                self.assertEqual(shell.dialog.capture_action.text(),
                                 'Start capture' if state in {'stopped', 'error'} else 'Stop capture')
        for state in ('stopped', 'starting', 'ready', 'loading', 'empty', 'error'):
            with self.subTest(source=state), patch.object(
                    shell.coordinator, 'snapshot', return_value=replace(before, source_state=state)):
                shell.refresh()
                self.assertEqual(shell.dialog.source.text(), state.capitalize())
                self.assertEqual(shell.dialog.source.accessibleName(), state.capitalize())
                self.assertEqual(shell.coordinator.snapshot().source_state, state)
        self.assertEqual(shell.coordinator.snapshot(), before)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(fixture.APP.quit_requests, 0)

    def test_representative_icons_and_loading_wheels_animate_only_transitions(self):
        shell = self.make()
        before = shell.coordinator.snapshot()
        original = self.store.path.read_bytes()
        shell.show_settings()
        icons = {'running': 'Lightning', 'stopped': 'Stop', 'error': 'Warning',
                 'starting': 'Loading', 'stopping': 'Loading', 'retrying': 'Loading'}
        for state, icon in icons.items():
            with self.subTest(state=state), patch.object(
                    shell.coordinator, 'snapshot', return_value=replace(before, state=state)):
                shell.refresh()
                fixture.APP.processEvents()
                label = shell.dialog.runtime
                self.assertEqual(label.accessibleDescription(), icon + ' icon')
                first = label.grab().toImage()
                # Check rendered pixels, not private timer or lifecycle storage.
                QTest.qWait(110)
                second = label.grab().toImage()
                self.assertEqual(first == second, icon != 'Loading')
        for state, icon in (('ready', 'Check'), ('empty', 'Empty'), ('loading', 'Loading')):
            with self.subTest(source=state), patch.object(
                    shell.coordinator, 'snapshot', return_value=replace(before, source_state=state)):
                shell.refresh()
                label = shell.dialog.source
                fixture.APP.processEvents()
                self.assertEqual(label.accessibleDescription(), icon + ' icon')
                first = label.grab().toImage()
                QTest.qWait(110)
                self.assertEqual(first == label.grab().toImage(), icon != 'Loading')
        shell.dialog.close()
        self.assertEqual(shell.coordinator.snapshot(), before)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(fixture.APP.quit_requests, 0)
