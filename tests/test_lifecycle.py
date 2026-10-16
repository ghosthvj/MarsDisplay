"""Public lifecycle contracts, synchronized without timing sleeps."""

from pathlib import Path
import tempfile
from threading import Event, get_ident
import unittest

from mars_display.frames import RGBFrame
from mars_display.settings import Settings, SettingsError, SettingsStore
from mars_display.transport import SimulatedTransport
from mars_display.lifecycle import Coordinator, LifecycleError, SourceSample


FRAME = RGBFrame(320, 480, bytes(320 * 480 * 3), 0)
PRIVATE = "https://private.example/secret"


class Source:
    def __init__(self, sample=None, failure=None, blocked=False, cleanup_error=False):
        self.sample = sample or SourceSample("ready", FRAME, live_connected=True, data_stale=False)
        self.failure = failure
        self.blocked = blocked
        self.cleanup_error = cleanup_error
        self.entered = Event()
        self.release = Event()
        self.calls = []
        self.closed = Event()

    def record(self, name):
        self.calls.append((name, get_ident()))

    def open(self):
        self.record("open")
        if self.failure == "open":
            raise RuntimeError(PRIVATE)

    def read(self):
        self.record("read")
        self.entered.set()
        if self.blocked and not self.release.wait(2):
            raise AssertionError("test capture was not released")
        if self.failure == "read":
            raise RuntimeError(PRIVATE)
        return self.sample

    def close(self):
        self.record("close")
        self.closed.set()
        if self.cleanup_error:
            raise RuntimeError(PRIVATE)


class Output(SimulatedTransport):
    def __init__(self, failure=None):
        super().__init__()
        self.failure = failure
        self.calls = []

    def record(self, name):
        self.calls.append((name, get_ident()))
        if self.failure == name:
            raise RuntimeError(PRIVATE)

    def open(self):
        self.record("open")
        super().open()

    def send(self, frame):
        self.record("send")
        super().send(frame)

    def close(self):
        self.record("close")
        super().close()


class GateWait:
    """Hold the worker at its next delay until cancellation."""
    def __init__(self):
        self.entered = Event()
        self.delays = []

    def __call__(self, cancel, seconds):
        self.delays.append(seconds)
        self.entered.set()
        if not cancel.wait(2):
            raise AssertionError("test delay was not cancelled")
        return True


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SettingsStore(Path(self.temp.name) / "settings.json")
        self.controllers = []
        self.sources = []
        self.outputs = []

    def tearDown(self):
        for source in self.sources:
            source.release.set()
        for controller in self.controllers:
            controller.stop()
            self.assertTrue(controller.wait_stopped(2))

    def make(self, source=None, output=None, wait=None, configured=True, factory=None,
             output_factory=None):
        if configured:
            self.store.save(Settings("https://mars.example"))
        source = source or Source()
        output = output or Output()
        self.sources.append(source)
        self.outputs.append(output)
        self.created = []

        def source_factory(settings):
            self.created.append(("source", get_ident(), settings.capture_url))
            return factory(settings) if factory else source

        def transport_factory():
            self.created.append(("transport", get_ident(), None))
            return output_factory() if output_factory else output

        controller = Coordinator(self.store, source_factory, transport_factory,
                                 wait=wait or GateWait())
        self.controllers.append(controller)
        return controller

    def test_initial_stopped_missing_settings_and_no_autostart(self):
        c = self.make(configured=False)
        self.assertEqual(c.snapshot().state, "stopped")
        self.assertEqual(self.created, [])
        with self.assertRaisesRegex(LifecycleError, "^Configure a MARS URL before starting\\.$"):
            c.start()
        self.assertFalse(c.snapshot().worker_alive)
        c.save_settings(Settings("https://mars.example"))
        self.assertEqual(self.created, [])
        self.assertEqual(c.snapshot().state, "stopped")

    def test_duplicate_start_worker_affinity_and_exit_cleanup(self):
        gate = GateWait()
        c = self.make(wait=gate)
        ui_thread = get_ident()
        self.assertTrue(c.start())
        self.assertTrue(gate.entered.wait(2))
        self.assertFalse(c.start())
        self.assertEqual(len(self.created), 2)
        before = c.snapshot()
        self.assertEqual((before.state, before.frames_sent), ("running", 1))
        self.assertEqual(before.output_state, "simulated-open")
        self.assertGreater(gate.delays[0], 0)
        self.assertLessEqual(gate.delays[0], 1)
        c.request_exit()
        self.assertTrue(c.wait_stopped(2))
        after = c.snapshot()
        self.assertTrue(after.exit_requested)
        self.assertTrue(after.exit_ready)
        self.assertEqual(after.state, "stopped")
        self.assertEqual(after.output_state, "simulated-closed")
        ids = {entry[1] for entry in self.created}
        ids.update(t for _, t in self.sources[0].calls + self.outputs[0].calls)
        self.assertEqual(len(ids), 1)
        self.assertNotIn(ui_thread, ids)
        self.assertEqual([n for n, _ in self.sources[0].calls], ["open", "read", "close"])
        self.assertEqual([n for n, _ in self.outputs[0].calls], ["open", "send", "close"])
        with self.assertRaisesRegex(LifecycleError, "^Exit has been requested\\.$"):
            c.start()

    def test_stop_blocked_capture_no_ack_or_send_before_cleanup(self):
        source = Source(blocked=True)
        c = self.make(source=source)
        c.start()
        self.assertTrue(source.entered.wait(2))
        c.stop()  # must return while read is blocked; never close on caller thread
        self.assertEqual(c.snapshot().state, "stopping")
        self.assertFalse(c.wait_stopped(0))
        self.assertFalse(source.closed.is_set())
        self.assertFalse(c.start())
        source.release.set()
        self.assertTrue(c.wait_stopped(2))
        self.assertEqual(c.snapshot().frames_sent, 0)
        self.assertEqual(self.outputs[0].accepted_frames, 0)
        self.assertEqual(len(self.created), 2)
        self.assertEqual(c.snapshot().state, "stopped")

    def test_stop_waits_for_owned_cleanup_before_acknowledgement(self):
        source = Source()
        closing = Event()
        release_cleanup = Event()
        self.addCleanup(release_cleanup.set)
        original_close = source.close

        def close():
            closing.set()
            if not release_cleanup.wait(2):
                raise AssertionError("test cleanup was not released")
            original_close()

        source.close = close
        gate = GateWait()
        c = self.make(source=source, wait=gate)
        c.start()
        self.assertTrue(gate.entered.wait(2))
        c.request_exit()
        self.assertTrue(closing.wait(2))
        self.assertEqual(c.snapshot().state, "stopping")
        self.assertFalse(c.snapshot().exit_ready)
        self.assertFalse(c.wait_stopped(0))
        release_cleanup.set()
        self.assertTrue(c.wait_stopped(2))
        self.assertTrue(c.snapshot().exit_ready)
        self.assertEqual(c.snapshot().frames_sent, 1)
        self.assertEqual(self.outputs[0].accepted_frames, 1)
        self.assertEqual(len(self.created), 2)

    def test_stop_cancels_retry_without_reconnect(self):
        gate = GateWait()
        c = self.make(source=Source(failure="read"), wait=gate)
        c.start()
        self.assertTrue(gate.entered.wait(2))
        self.assertEqual(c.snapshot().state, "retrying")
        self.assertTrue(self.sources[0].closed.is_set())
        c.stop()
        self.assertTrue(c.wait_stopped(2))
        self.assertEqual(gate.delays, [1])
        self.assertEqual(len(self.created), 2)
        self.assertEqual(c.snapshot().frames_sent, 0)
        self.assertEqual(c.snapshot().state, "stopped")

    def test_exact_retry_exhaustion_explicit_restart_and_error_stop(self):
        delays = []
        c = self.make(source=Source(failure="read"),
                      wait=lambda cancel, seconds: delays.append(seconds) or cancel.is_set())
        c.start()
        self.assertTrue(c.wait_stopped(2))
        snap = c.snapshot()
        self.assertEqual(delays, [1, 2, 4, 8, 16])
        self.assertEqual(len(self.created), 12)
        self.assertEqual((snap.state, snap.retries, snap.failures), ("error", 5, 6))
        self.assertEqual(snap.error, "Recovery exhausted; check MARS and output, then Start.")
        self.assertEqual((snap.source_state, snap.output_state), ("error", "simulated-closed"))
        self.assertTrue(c.start())
        self.assertTrue(c.wait_stopped(2))
        self.assertEqual(delays, [1, 2, 4, 8, 16] * 2)
        c.stop()
        self.assertEqual(c.snapshot().state, "stopped")
        self.assertIsNone(c.snapshot().error)

    def test_partial_resources_cleaned_on_setup_read_and_write_errors(self):
        for phase in ("source_factory", "open", "read", "output_factory", "output_open", "send"):
            with self.subTest(phase=phase):
                source = Source(failure=phase if phase in {"open", "read"} else None)
                output = Output(failure={"output_open": "open", "send": "send"}.get(phase))
                gate = GateWait()

                def failing_factory(*args):
                    raise RuntimeError(PRIVATE)

                c = self.make(source=source, output=output, wait=gate,
                              factory=failing_factory if phase == "source_factory" else None,
                              output_factory=failing_factory if phase == "output_factory" else None)
                c.start()
                self.assertTrue(gate.entered.wait(2))
                snap = c.snapshot()
                self.assertEqual(snap.frames_sent, 0)
                self.assertEqual(snap.failures, 1)
                self.assertNotIn(PRIVATE, str(snap))
                self.assertEqual(snap.error, "Capture or output failed; retrying.")
                if phase != "source_factory":
                    self.assertTrue(source.closed.is_set())
                if phase in {"output_open", "send", "read"}:
                    # Source open precedes output construction; read follows output open.
                    self.assertEqual(output.calls[-1][0], "close")
                if phase == "send":
                    self.assertEqual((snap.source_state, snap.output_state), ("ready", "error"))
                c.stop()
                self.assertTrue(c.wait_stopped(2))

    def test_cleanup_failure_is_latched_and_both_resources_closed(self):
        for resource in ("source", "output"):
            with self.subTest(resource=resource):
                gate = GateWait()
                source = Source(cleanup_error=resource == "source")
                output = Output(failure="close" if resource == "output" else None)
                c = self.make(source=source, output=output, wait=gate)
                c.start()
                self.assertTrue(gate.entered.wait(2))
                c.request_exit()
                self.assertTrue(c.wait_stopped(2))
                snap = c.snapshot()
                self.assertEqual(snap.state, "error")
                self.assertEqual(snap.error, "Cleanup failed; restart the application before starting again.")
                self.assertFalse(snap.exit_ready)
                self.assertEqual(source.calls[-1][0], "close")
                self.assertEqual(output.calls[-1][0], "close")
                c.stop()
                self.assertEqual(c.snapshot().state, "error")

    def test_cleanup_failure_prevents_retry_and_restart(self):
        c = self.make(source=Source(failure="read", cleanup_error=True))
        c.start()
        self.assertTrue(c.wait_stopped(2))
        self.assertEqual(c.snapshot().state, "error")
        self.assertEqual(len(self.created), 2)
        with self.assertRaisesRegex(LifecycleError, "^Cleanup failed; restart the application before starting again\\.$"):
            c.start()
        with self.assertRaisesRegex(LifecycleError, "^Settings can be saved only while stopped\\.$"):
            c.save_settings(Settings("https://other.example"))

    def test_independent_empty_stale_status_and_retained_frame(self):
        samples = [SourceSample("ready", FRAME, True, False),
                   SourceSample("empty", live_connected=False, data_stale=True),
                   SourceSample("loading"), SourceSample("error")]
        source = Source()
        observed = []
        c = None

        def wait(cancel, seconds):
            observed.append(c.snapshot())
            if len(observed) == len(samples):
                return cancel.wait(2)
            source.sample = samples[len(observed)]
            return cancel.is_set()

        source.sample = samples[0]
        done = Event()
        original_wait = wait

        def signalled_wait(cancel, seconds):
            if len(observed) == 3:
                done.set()
            return original_wait(cancel, seconds)

        # Install via a new controller rather than altering coordinator internals.
        c = self.make(source=source, wait=signalled_wait)
        c.start()
        self.assertTrue(done.wait(2))
        c.stop()
        self.assertTrue(c.wait_stopped(2))
        self.assertEqual([s.source_state for s in observed], ["ready", "empty", "loading", "error"])
        self.assertTrue(all(s.output_state == "simulated-open" for s in observed))
        self.assertEqual((observed[1].live_connected, observed[1].data_stale), (False, True))
        self.assertIsNone(observed[2].live_connected)
        self.assertTrue(all(s.frames_sent == 1 and s.latest_frame == FRAME for s in observed))
        self.assertEqual(c.snapshot().failures, 0)

    def test_success_resets_consecutive_retry_budget(self):
        gate = GateWait()
        reads = 0
        delays = []
        source = Source()

        def read():
            nonlocal reads
            reads += 1
            if reads in (1, 3):
                raise RuntimeError(PRIVATE)
            return SourceSample("empty")

        source.read = read

        def wait(cancel, seconds):
            if reads in (1, 3):
                delays.append(seconds)
                return False
            if reads == 2:
                return False
            return gate(cancel, seconds)

        c = self.make(source=source, wait=wait)
        c.start()
        self.assertTrue(gate.entered.wait(2))
        self.assertEqual(delays, [1, 1])
        self.assertEqual(c.snapshot().retries, 2)
        self.assertEqual(c.snapshot().failures, 2)
        self.assertIsNone(c.snapshot().error)
        c.stop()
        self.assertTrue(c.wait_stopped(2))

    def test_stopped_only_save_and_invalid_input_preserve_bytes(self):
        source = Source(blocked=True)
        c = self.make(source=source)
        original = self.store.path.read_bytes()
        with self.assertRaisesRegex(SettingsError, "^Only validated Settings can be saved\\.$"):
            c.save_settings(object())
        self.assertEqual(self.store.path.read_bytes(), original)
        c.start()
        self.assertTrue(source.entered.wait(2))
        for stop in (False, True):
            if stop:
                c.stop()
            with self.assertRaisesRegex(LifecycleError, "^Settings can be saved only while stopped\\.$"):
                c.save_settings(Settings("https://other.example", "opaque-device"))
            self.assertEqual(self.store.path.read_bytes(), original)
        source.release.set()
        self.assertTrue(c.wait_stopped(2))
        c.save_settings(Settings("https://other.example", "opaque-device"))
        self.assertEqual(self.store.load(), Settings("https://other.example", "opaque-device"))
        self.assertEqual(c.snapshot().state, "stopped")
        self.assertEqual(c.snapshot().frames_sent, 0)

    def test_non_ready_frame_rejected_without_delivery(self):
        with self.assertRaisesRegex(ValueError, "^Only ready source samples may contain a frame\\.$"):
            SourceSample("loading", FRAME)


if __name__ == "__main__":
    unittest.main()
