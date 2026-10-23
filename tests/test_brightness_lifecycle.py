"""Saved brightness intent stays separate from frame delivery and serial ownership."""
from dataclasses import replace
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from mars_display.lifecycle import Coordinator, LifecycleError, SourceSample
from mars_display.settings import Settings, SettingsError, SettingsStore
from mars_display.usb_transport import UsbError
from test_lifecycle import Source, GateWait
from test_native_lifecycle import NativeOutput, FIRST
from test_output_configuration import device, native


class BrightOutput(NativeOutput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.events = []
        self.fail_brightness = False
        self.brightness_done = Event()

    def open(self):
        super().open()
        self.events.append('open')

    def set_brightness(self, percent):
        self.events.append(('brightness', percent))
        if self.fail_brightness:
            raise UsbError('brightness', delivery_uncertain=True)
        self.brightness_done.set()

    def send(self, frame):
        self.events.append('frame-start')
        super().send(frame)
        self.events.append('frame-end')

    def close(self):
        super().close()
        self.events.append('close')


class FirstPassGateWait(GateWait):
    first_pass = False

    def __call__(self, cancel, seconds):
        if self.first_pass and not self.delays:
            self.delays.append(seconds)
            return False
        return super().__call__(cancel, seconds)


class BrightnessLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SettingsStore(Path(self.temp.name) / 'settings.json')
        self.store.save(Settings('https://mars.example'))
        self.store.migrate_to_v2(native(), acknowledge_legacy_incompatibility=True)
        self.original = self.store.path.read_bytes()
        self.output = BrightOutput()
        self.source = Source(sample=SourceSample('ready', FIRST))
        self.wait = FirstPassGateWait()
        self.controller = Coordinator(self.store, lambda _: self.source,
            transport_context_factory=lambda _: self.output,
            inventory_provider=lambda: (device(),), wait=self.wait)

    def tearDown(self):
        self.output.release.set()
        self.output.close_release.set()
        self.source.release.set()
        self.controller.stop()
        self.assertTrue(self.controller.wait_stopped(2))

    def enable(self):
        return self.controller.enable_brightness(acknowledge_legacy_incompatibility=True)

    def test_explicit_migration_and_stopped_selection_never_open_output(self):
        with self.assertRaises(SettingsError):
            self.controller.enable_brightness()
        self.assertEqual(self.store.path.read_bytes(), self.original)
        self.assertFalse(self.store.pre_brightness_backup_path.exists())
        saved = self.enable()
        self.assertEqual((saved.schema_version, saved.brightness_percent), (3, 100))
        for level in (100, 80, 60, 40, 20):
            self.assertEqual(self.controller.set_brightness(level).brightness_percent, level)
            self.assertEqual(SettingsStore(self.store.path).load().brightness_percent, level)
        self.assertEqual(self.output.events, [])
        self.assertEqual(self.controller.snapshot().frames_sent, 0)
        self.assertIsNone(self.controller.snapshot().brightness_applied)
        self.controller.restore_pre_brightness_settings()
        self.assertEqual(self.store.path.read_bytes(), self.original)

    def test_invalid_and_failed_save_leave_intent_data_and_counters_unchanged(self):
        self.enable()
        before = self.controller.snapshot()
        raw = self.store.path.read_bytes()
        backup = self.store.pre_brightness_backup_path.read_bytes()
        for value in (0, 25, 101, True, 20.0, '20'):
            with self.subTest(value=value), self.assertRaises(SettingsError):
                self.controller.set_brightness(value)
            self.assertEqual(self.controller.snapshot(), before)
            self.assertEqual(self.store.path.read_bytes(), raw)
            self.assertEqual(self.store.pre_brightness_backup_path.read_bytes(), backup)
        with patch.object(self.store, 'save', side_effect=SettingsError('Cannot save settings.')):
            with self.assertRaisesRegex(SettingsError, '^Cannot save settings\\.$'):
                self.controller.set_brightness(20)
        self.assertEqual(self.controller.snapshot(), before)
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(self.output.events, [])

    def test_live_changes_coalesce_after_complete_frame_on_one_connection(self):
        self.enable()
        self.output.release.clear()
        self.wait.first_pass = True
        self.controller.start()
        self.assertTrue(self.output.entered.wait(1))
        for level in (80, 60, 40, 20):
            self.controller.set_brightness(level)
        self.assertEqual(self.output.events, ['open', ('brightness', 100), 'frame-start'])
        self.output.release.set()
        self.assertTrue(self.wait.entered.wait(1))
        self.assertEqual(self.output.events, ['open', ('brightness', 100), 'frame-start',
            'frame-end', ('brightness', 20), 'frame-start', 'frame-end'])
        self.assertEqual(self.controller.snapshot().brightness_applied, 20)
        self.controller.stop()
        self.assertTrue(self.controller.wait_stopped(2))
        # Explicit Start always reloads the saved value, even if Stop won the race.
        self.output.entered.clear()
        self.wait = GateWait()
        other = Coordinator(self.store, lambda _: self.source,
            transport_context_factory=lambda _: self.output, wait=self.wait)
        try:
            other.start()
            self.assertTrue(self.wait.entered.wait(1))
            state = other.snapshot()
            self.assertEqual((state.brightness_requested, state.brightness_applied), (20, 20))
            self.assertEqual((state.frames_sent, state.native_timing.host_send.count), (1, 1))
            self.assertIs(state.latest_frame, FIRST)
        finally:
            other.stop()
            self.assertTrue(other.wait_stopped(2))
        first_end = self.output.events.index('frame-end')
        for index, event in enumerate(self.output.events):
            if event == ('brightness', 20):
                self.assertGreater(index, first_end)
        self.assertNotIn(('brightness', 80), self.output.events)
        self.assertNotIn(('brightness', 60), self.output.events)
        self.assertNotIn(('brightness', 40), self.output.events)

    def test_no_frame_still_applies_brightness_without_frame_accounting(self):
        self.enable()
        self.source.sample = SourceSample('loading')
        self.controller.start()
        self.assertTrue(self.wait.entered.wait(1))
        state = self.controller.snapshot()
        self.assertEqual(state.brightness_applied, 100)
        self.assertEqual((state.frames_sent, state.native_timing.host_send.count), (0, 0))
        self.assertIsNone(state.latest_frame)
        raw = self.store.path.read_bytes()
        with self.assertRaises(LifecycleError):
            self.controller.enable_brightness(acknowledge_legacy_incompatibility=True)
        self.controller.stop()
        with self.assertRaises(LifecycleError):
            self.controller.set_brightness(20)
        self.assertEqual(self.store.path.read_bytes(), raw)

    def test_uncertain_brightness_has_no_frame_retry_or_false_readback(self):
        self.enable()
        self.output.fail_brightness = True
        self.controller.start()
        self.assertTrue(self.controller.wait_stopped(2))
        state = self.controller.snapshot()
        self.assertEqual((state.frames_sent, state.retries, state.failures), (0, 0, 1))
        self.assertEqual(state.failure_kind, 'native-brightness-uncertain')
        self.assertIsNone(state.brightness_applied)
        self.assertTrue(state.delivery_uncertain)
        self.assertEqual(self.output.events, ['open', ('brightness', 100), 'close'])
        self.assertIn('Brightness', state.error)
        self.assertNotIn('frame', state.error)
        self.controller.request_exit()
        self.assertTrue(self.controller.snapshot().exit_ready)

    def test_external_settings_change_is_not_overwritten_by_live_control(self):
        self.enable()
        self.controller.start()
        self.assertTrue(self.wait.entered.wait(1))
        self.store.save(replace(self.store.load(), mars_url='https://changed.example'))
        raw = self.store.path.read_bytes()
        before = self.controller.snapshot()
        with self.assertRaisesRegex(LifecycleError, 'Settings changed'):
            self.controller.set_brightness(20)
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(self.controller.snapshot(), before)

    def test_exit_discards_pending_write_but_keeps_saved_intent(self):
        import hashlib

        self.enable()
        self.output.release.clear()
        self.controller.start()
        self.assertTrue(self.output.entered.wait(1))
        self.controller.set_brightness(20)
        digest = hashlib.sha256(self.store.path.read_bytes()).digest()
        self.controller.request_exit()
        with self.assertRaises(LifecycleError) as caught:
            self.controller.set_brightness(40)
        self.assertEqual(str(caught.exception),
                         'Brightness cannot change during stopping, error or Exit.')
        self.assertEqual(hashlib.sha256(self.store.path.read_bytes()).digest(), digest)
        self.output.release.set()
        self.assertTrue(self.controller.wait_stopped(2))
        self.assertEqual(self.output.events, [
            'open', ('brightness', 100), 'frame-start', 'frame-end', 'close'])
        self.assertEqual(self.store.load().brightness_percent, 20)
        self.assertTrue(self.controller.snapshot().exit_ready)

    def test_legacy_native_and_simulation_do_not_issue_brightness(self):
        self.controller.start()
        self.assertTrue(self.wait.entered.wait(1))
        self.assertEqual(self.output.events, ['open', 'frame-start', 'frame-end'])
        self.assertIsNone(self.controller.snapshot().brightness_requested)
        with self.assertRaises(LifecycleError):
            self.controller.set_brightness(20)
        self.controller.stop()
        self.assertTrue(self.controller.wait_stopped(2))
        self.controller.restore_schema1_settings()
        raw = self.store.path.read_bytes()
        with self.assertRaises(LifecycleError):
            self.controller.enable_brightness(acknowledge_legacy_incompatibility=True)
        self.assertEqual(self.store.path.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
