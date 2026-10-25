"""Saved launch intent through public preference and Qt controls; no USB/browser."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from mars_display.lifecycle import LifecycleError
from mars_display.settings import Settings, SettingsError, SettingsStore
from mars_display.tray import create_shell
import test_tray as tray_fixture

APP, until = tray_fixture.APP, tray_fixture.until


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        from mars_display.startup_preferences import StartupPreferenceStore
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = SettingsStore(Path(self.temp.name)/'custom.json')
        self.settings.save(Settings('https://mars.example'))
        self.original = self.settings.path.read_bytes()
        self.preference = StartupPreferenceStore(self.settings.path)

    def test_missing_and_explicit_booleans_preserve_main_settings(self):
        self.assertEqual(self.preference.path.name, 'custom.json.startup.json')
        self.assertFalse(self.preference.load())
        self.assertFalse(self.preference.path.exists())
        for value in (True, False):
            self.preference.save(value)
            self.assertIs(self.preference.load(), value)
            self.assertEqual(self.settings.path.read_bytes(), self.original)

    def test_invalid_files_and_non_boolean_values_never_opt_in_or_repair(self):
        for raw in (b'broken', b'null', b'[]', b'{}', b'\xff',
                    b'{"start_capture_on_launch":1}', b'{"start_capture_on_launch":"true"}',
                    b'{"start_capture_on_launch":true,"extra":0}',
                    b'{"start_capture_on_launch":false,"start_capture_on_launch":true}'):
            with self.subTest(raw=raw):
                self.preference.path.write_bytes(raw)
                with self.assertRaises(SettingsError): self.preference.load()
                self.assertEqual(self.preference.path.read_bytes(), raw)
        before = self.preference.path.read_bytes()
        with patch.object(Path, 'read_text', side_effect=PermissionError):
            with self.assertRaises(SettingsError): self.preference.load()
        for value in (None, 1, 0, 'true'):
            with self.subTest(value=value), self.assertRaises(SettingsError):
                self.preference.save(value)
        self.assertEqual(self.preference.path.read_bytes(), before)
        self.assertEqual(self.settings.path.read_bytes(), self.original)

    def test_failed_atomic_save_preserves_preference_settings_and_backups(self):
        self.preference.save(False)
        backup = self.settings.schema1_backup_path
        backup.write_bytes(self.original)
        before = {p.name:p.read_bytes() for p in Path(self.temp.name).iterdir()}
        for operation in ('replace', 'fsync'):
            with self.subTest(operation=operation), patch('mars_display.settings.os.'+operation, side_effect=OSError):
                with self.assertRaises(SettingsError): self.preference.save(True)
            self.assertEqual({p.name:p.read_bytes() for p in Path(self.temp.name).iterdir()}, before)
            self.assertFalse(self.preference.load())


class CaptureOnLaunchTests(unittest.TestCase):
    setUp = tray_fixture.TrayTests.setUp
    tearDown = tray_fixture.TrayTests.tearDown
    make = tray_fixture.TrayTests.make

    def preference(self, raw=b'{"start_capture_on_launch":true}'):
        path = self.store.path.with_name(self.store.path.name+'.startup.json')
        path.write_bytes(raw)
        return path

    def test_default_remains_idle_and_does_not_create_preference(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        APP.processEvents()
        self.assertFalse(shell.dialog.start_on_launch.isChecked())
        self.assertEqual(shell.dialog.start_on_launch.text(), 'Start capture when MarsDisplay opens')
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertFalse(self.store.path.with_name(self.store.path.name+'.startup.json').exists())

    def test_false_preference_remains_idle(self):
        path = self.preference(b'{"start_capture_on_launch":false}')
        before = path.read_bytes()
        self.make()
        APP.processEvents()
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(path.read_bytes(), before)

    def test_corrupt_preference_is_idle_without_repair(self):
        path = self.preference(b'{"start_capture_on_launch":"true"}')
        before = path.read_bytes()
        shell = self.make()
        APP.processEvents()
        self.assertFalse(self.session.opened.is_set())
        self.assertFalse(shell.dialog.start_on_launch.isChecked())
        self.assertEqual(path.read_bytes(), before)

    def test_saved_opt_in_runs_once_after_admission_and_never_restarts_after_stop(self):
        path = self.preference()
        before = path.read_bytes()
        shell = self.make(wait_override=lambda cancel, seconds: cancel.wait(0.01))
        self.assertFalse(self.session.opened.is_set())
        self.session.allow_open.set()
        self.session.allow_close.set()
        with patch.object(shell.coordinator, 'start', wraps=shell.coordinator.start) as start:
            until(lambda: shell.coordinator.snapshot().frames_sent > 0)
            start.assert_called_once_with()
            shell.stop_action.trigger()
            until(lambda: not shell.coordinator.snapshot().worker_alive)
            count = shell.coordinator.snapshot().frames_sent
            for _ in range(3): shell.refresh(); APP.processEvents()
            start.assert_called_once_with()
            self.assertEqual(shell.coordinator.snapshot().frames_sent, count)
        self.assertEqual(path.read_bytes(), before)

    def test_saved_native_opt_in_uses_normal_owned_transport(self):
        import test_usb_transport as native
        from mars_display.lifecycle import Coordinator
        from mars_display.settings import NATIVE_IDENTITY, NATIVE_PROFILE
        self.store.migrate_to_v2(Settings('https://mars.example', NATIVE_IDENTITY,
            2, 'native', NATIVE_PROFILE), acknowledge_legacy_incompatibility=True)
        original = self.store.path.read_bytes()
        self.preference()
        children = []
        def transport(context):
            output, created, _ = native.TransportTests.make(self, cancel=context.cancel)
            children.append(created)
            return output
        self.session.allow_open.set()
        self.session.allow_close.set()
        self.shell = create_shell(APP, self.store, lambda: Coordinator(
            self.store, lambda _: self.session, transport_context_factory=transport,
            wait=lambda cancel, seconds: cancel.wait(5)))
        self.assertEqual(children, [])
        until(lambda: self.shell.coordinator.snapshot().frames_sent == 1)
        self.shell.stop_action.trigger()
        until(lambda: not self.shell.coordinator.snapshot().worker_alive)
        state = self.shell.coordinator.snapshot()
        self.assertEqual((state.frames_sent, state.failures, state.retries), (1, 0, 0))
        self.assertEqual((len(children), len(children[0])), (1, 1))
        port = children[0][0].port
        self.assertEqual((port.opens, port.closes, len(port.writes)), (1, 1, 122))
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_manual_failed_start_consumes_pending_launch(self):
        self.preference()
        shell = self.make()
        with patch.object(shell.coordinator, 'start', side_effect=LifecycleError('Start denied.')) as start:
            shell.start_action.trigger()
            for _ in range(3): APP.processEvents(); shell.refresh()
            start.assert_called_once_with()
        self.assertFalse(self.session.opened.is_set())

    def test_stop_cancels_pending_launch_through_enabled_control(self):
        self.preference()
        shell = self.make()
        self.assertTrue(shell.stop_action.isEnabled())
        shell.stop_action.trigger()
        APP.processEvents()
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)

    def test_disabling_preference_cancels_pending_launch(self):
        self.preference()
        shell = self.make()
        shell.dialog.start_on_launch.click()
        APP.processEvents()
        self.assertFalse(self.session.opened.is_set())
        self.assertFalse(shell.dialog.start_on_launch.isChecked())

    def test_automatic_start_failure_is_not_retried(self):
        self.preference()
        shell = self.make()
        with patch.object(shell.coordinator, 'start', side_effect=LifecycleError('Start denied.')) as start:
            for _ in range(3): APP.processEvents(); shell.refresh()
            start.assert_called_once_with()
        self.assertFalse(self.session.opened.is_set())

    def test_toggle_during_capture_changes_only_next_launch(self):
        shell = self.make()
        original = self.store.path.read_bytes()
        with patch.object(shell.coordinator, 'start', wraps=shell.coordinator.start) as start:
            shell.start_action.trigger()
            until(self.session.opened.is_set)
            self.assertTrue(shell.dialog.start_on_launch.isEnabled())
            shell.dialog.start_on_launch.click()
            shell.dialog.start_on_launch.click()
            start.assert_called_once_with()
            self.assertTrue(shell.coordinator.snapshot().worker_alive)
            self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_exit_cancels_pending_launch(self):
        self.preference()
        shell = self.make()
        shell.exit_action.trigger()
        APP.processEvents()
        self.assertFalse(self.session.opened.is_set())
        self.assertTrue(shell.coordinator.snapshot().exit_ready)

    def test_no_saved_configuration_or_duplicate_admission_never_starts(self):
        self.preference()
        shell = self.make(configured=False)
        APP.processEvents()
        self.assertFalse(shell.dialog.start_on_launch.isEnabled())
        self.assertFalse(self.session.opened.is_set())
        factory = Mock()
        self.assertIsNone(create_shell(APP, self.store, factory))
        APP.processEvents()
        factory.assert_not_called()
        self.assertFalse(self.store.path.exists())

    def test_unreadable_true_preference_is_passive_and_exit_refuses_toggle(self):
        self.store.save(Settings('https://mars.example'))
        preference = self.preference()
        before = (self.store.path.read_bytes(), preference.read_bytes())
        read = Path.read_text
        def guarded(path, *args, **kwargs):
            if path == preference: raise PermissionError('private path')
            return read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            shell = self.make(configured=False)
        APP.processEvents()
        self.assertFalse(self.session.opened.is_set())
        self.assertFalse(shell.dialog.start_on_launch.isChecked())
        self.assertEqual(shell.dialog.message.text(),
            'Cannot read startup preference. Automatic capture is disabled; '
            'change the option to save a valid preference.')
        shell.exit_action.trigger()
        self.assertFalse(shell.dialog.start_on_launch.isEnabled())
        shell.dialog.start_on_launch.click()
        shell.dialog.start_on_launch.setChecked(True)
        self.assertFalse(shell.dialog.start_on_launch.isChecked())
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual((self.store.path.read_bytes(), preference.read_bytes()), before)

    def test_cancel_reenable_is_next_launch_and_duplicate_does_not_read(self):
        preference = self.preference()
        shell = self.make()
        with patch('mars_display.startup_preferences.StartupPreferenceStore.load') as load:
            factory = Mock()
            self.assertIsNone(create_shell(APP, self.store, factory))
            load.assert_not_called()
            factory.assert_not_called()
        shell.stop_action.trigger()
        shell.dialog.start_on_launch.click()
        shell.dialog.start_on_launch.click()
        before = (self.store.path.read_bytes(), preference.read_bytes())
        for _ in range(3): APP.processEvents(); shell.refresh()
        self.assertTrue(shell.dialog.start_on_launch.isChecked())
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual((self.store.path.read_bytes(), preference.read_bytes()), before)

    def test_toggle_saves_next_launch_only_and_failed_save_rolls_back(self):
        from mars_display.startup_preferences import StartupPreferenceStore
        shell = self.make()
        original = self.store.path.read_bytes()
        shell.dialog.start_on_launch.click()
        preference = StartupPreferenceStore(self.store.path)
        self.assertTrue(preference.load())
        APP.processEvents()
        self.assertFalse(self.session.opened.is_set())
        self.assertEqual(shell.coordinator.snapshot().frames_sent, 0)
        with patch('mars_display.settings.os.replace', side_effect=OSError):
            shell.dialog.start_on_launch.click()
        self.assertTrue(shell.dialog.start_on_launch.isChecked())
        self.assertTrue(preference.load())
        shell.dialog.start_on_launch.click()
        self.assertFalse(preference.load())
        self.assertEqual(self.store.path.read_bytes(), original)
