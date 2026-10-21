"""Numeric diagnostics through public lifecycle snapshots; no USB or wall sleeps."""
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import tempfile
from threading import Event
import unittest

from mars_display.lifecycle import Coordinator, SourceSample
from mars_display.settings import Settings, SettingsStore
from test_lifecycle import Source, GateWait
from test_native_lifecycle import NativeOutput, FIRST, IDENTITY, PROFILE


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SettingsStore(Path(self.temp.name) / 'settings.json')
        self.store.save(Settings('https://mars.example'))
        self.native = Settings('https://mars.example', IDENTITY, 2, 'native', PROFILE)
        self.store.migrate_to_v2(self.native, acknowledge_legacy_incompatibility=True)
        self.controllers = []

    def tearDown(self):
        for controller in self.controllers:
            controller.stop()
            self.assertTrue(controller.wait_stopped(2))

    def make(self, *, fail_send=False, fail_read=False, simulated=False):
        clock, gate = Clock(), GateWait()
        class TimedSource(Source):
            def read(self):
                clock.advance(0.125 if not self.entered.is_set() else 0.375)
                if fail_read:
                    raise RuntimeError('private source')
                first = not self.entered.is_set()
                self.entered.set()
                return SourceSample('empty') if first else SourceSample('ready', FIRST)
        class TimedOutput(NativeOutput):
            def send(self, frame):
                clock.advance(0.25)
                if fail_send:
                    raise RuntimeError('private send')
                super().send(frame)
        source, output = TimedSource(), TimedOutput()
        waits = []
        def wait(cancel, seconds):
            waits.append(seconds)
            if len(waits) == 1:
                clock.advance(0.5)
                return False
            return gate(cancel, seconds)
        if simulated:
            self.store.save(replace(self.native, output_mode='simulated', native_profile=None))
        controller = Coordinator(self.store, lambda _: source,
            transport_context_factory=lambda _: output, wait=wait, diagnostic_clock=clock)
        self.controllers.append(controller)
        return controller, gate, output, clock

    def assert_stage(self, stage, count, latest, minimum, maximum, mean):
        self.assertEqual({f.name for f in fields(stage)},
                         {'count', 'latest', 'minimum', 'maximum', 'mean'})
        self.assertEqual((stage.count, stage.latest, stage.minimum, stage.maximum, stage.mean),
                         (count, latest, minimum, maximum, mean))
        self.assertTrue(all(type(getattr(stage, f.name)) in (int, float) for f in fields(stage)))
        with self.assertRaises(FrozenInstanceError):
            stage.count = 100

    def test_arithmetic_independent_counts_retention_reset_and_cancelled_wait(self):
        controller, gate, output, clock = self.make()
        raw = self.store.path.read_bytes()
        self.assertIsNone(controller.snapshot().native_timing)
        controller.start()
        self.assertTrue(gate.entered.wait(1))
        before = controller.snapshot()
        report = before.native_timing
        self.assertEqual({f.name for f in fields(report)}, {'source_read', 'host_send', 'cadence_wait',
                          'decode', 'identity', 'encode', 'write', 'drain', 'body_encode', 'exchange'})
        with self.assertRaises(FrozenInstanceError):
            report.source_read = None
        self.assert_stage(report.source_read, 2, .375, .125, .375, .25)
        self.assert_stage(report.host_send, 1, .25, .25, .25, .25)
        self.assert_stage(report.cadence_wait, 1, .5, .5, .5, .5)
        self.assertEqual(before.frames_sent, 1)
        self.assertIs(before.latest_frame, FIRST)
        self.assertFalse(controller.start())
        self.assertEqual(controller.snapshot().native_timing, report)
        clock.advance(9)
        controller.stop()
        self.assertTrue(controller.wait_stopped(2))
        self.assertEqual(controller.snapshot().native_timing, report)
        self.assertEqual(self.store.path.read_bytes(), raw)
        # Hold the next admitted session before read: reset is visible immediately.
        entered, release = Event(), Event()
        def held_open():
            entered.set()
            if not release.wait(2):
                raise AssertionError('open not released')
        output.open = held_open
        try:
            controller.start()
            self.assertTrue(entered.wait(1))
            reset = controller.snapshot().native_timing
            for field in fields(reset):
                self.assert_stage(getattr(reset, field.name), 0, 0, 0, 0, 0)
            self.assertEqual(controller.snapshot().frames_sent, 1)
        finally:
            controller.stop()
            release.set()
        self.assertTrue(controller.wait_stopped(2))
        self.assertEqual(report.source_read.count, 2)
        controller.save_settings(replace(self.native, output_mode='simulated', native_profile=None))
        controller.start()
        self.assertTrue(gate.entered.wait(1))
        self.assertIsNone(controller.snapshot().native_timing)

    def test_each_stage_aggregates_multiple_durations_including_zero(self):
        clock, gate = Clock(), GateWait()
        reads = iter((.125, .375, .25, .25))
        sends = iter((0, .5, .25, .25))
        waits = iter((.25, .75, .5))
        class TimedSource(Source):
            def read(self):
                clock.advance(next(reads))
                return SourceSample('ready', FIRST)
        class TimedOutput(NativeOutput):
            def send(self, frame):
                clock.advance(next(sends))
                super().send(frame)
        def wait(cancel, seconds):
            duration = next(waits, None)
            if duration is None:
                return gate(cancel, seconds)
            clock.advance(duration)
            return False
        output = TimedOutput()
        controller = Coordinator(self.store, lambda _: TimedSource(),
            transport_context_factory=lambda _: output, wait=wait, diagnostic_clock=clock)
        self.controllers.append(controller)
        controller.start()
        self.assertTrue(gate.entered.wait(1))
        status = controller.snapshot()
        self.assert_stage(status.native_timing.source_read, 4, .25, .125, .375, .25)
        self.assert_stage(status.native_timing.host_send, 4, .25, 0, .5, .25)
        self.assert_stage(status.native_timing.cadence_wait, 3, .5, .25, .75, .5)
        self.assertEqual((status.frames_sent, len(output.accepted)), (4, 4))
        self.assertIs(status.latest_frame, FIRST)

    def test_failed_send_is_not_timed_and_keeps_counter_and_preview(self):
        controller, _, output, _ = self.make(fail_send=True)
        raw = self.store.path.read_bytes()
        controller.start()
        self.assertTrue(controller.wait_stopped(2))
        status = controller.snapshot()
        self.assertEqual((status.state, status.frames_sent, status.retries, status.failures), ('error', 0, 0, 1))
        self.assertIsNone(status.latest_frame)
        self.assertEqual(status.error, 'Native delivery is uncertain; the previous host-accepted frame is retained. No resend.')
        self.assertEqual(status.native_timing.source_read.count, 2)
        self.assert_stage(status.native_timing.host_send, 0, 0, 0, 0, 0)
        self.assertEqual(output.accepted, [])
        controller.stop()
        self.assertEqual(controller.snapshot().native_timing, status.native_timing)
        self.assertEqual(self.store.path.read_bytes(), raw)

    def test_failed_source_is_not_timed(self):
        controller, _, _, _ = self.make(fail_read=True)
        controller.start()
        self.assertTrue(controller.wait_stopped(2))
        status = controller.snapshot()
        self.assertEqual((status.frames_sent, status.retries, status.failures), (0, 0, 1))
        self.assertEqual(status.error, 'Capture failed; native output was not retried.')
        for field in fields(status.native_timing):
            self.assert_stage(getattr(status.native_timing, field.name), 0, 0, 0, 0, 0)

    def test_simulation_keeps_behavior_without_reading_diagnostic_clock(self):
        self.store.save(replace(self.native, output_mode='simulated', native_profile=None))
        gate = GateWait()
        def forbidden():
            raise AssertionError('Simulation must not use diagnostic clock')
        # Construct through the same public seam, with an intentionally unusable clock.
        source = Source()
        controller = Coordinator(self.store, lambda _: source,
            transport_context_factory=lambda _: NativeOutput(), wait=gate, diagnostic_clock=forbidden)
        self.controllers.append(controller)
        controller.start()
        self.assertTrue(gate.entered.wait(1))
        status = controller.snapshot()
        self.assertEqual((status.state, status.frames_sent, status.failures), ('running', 1, 0))
        self.assertIsNone(status.native_timing)
        controller.stop()
        self.assertTrue(controller.wait_stopped(2))
        self.assertIsNone(controller.snapshot().native_timing)
