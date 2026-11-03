"""Application Stop boundaries with owned fake peers; no physical USB."""
from dataclasses import replace
from functools import partial
from threading import Event
import time
import unittest
from unittest.mock import Mock, patch

from mars_display import app, linux_usb_transport
from mars_display.lifecycle import Coordinator, SourceSample, StartContext
from mars_display.usb_protocol import encode_portrait, encode_brightness
from test_lifecycle import Source
import test_native_lifecycle as native_fixture
import test_usb_transport as fixture


class GracefulStopTests(unittest.TestCase):
    setUp = native_fixture.NativeLifecycleTests.setUp
    tearDown = native_fixture.NativeLifecycleTests.tearDown

    def compose(self, context, sessions):
        def factory(identity, **options):
            output, children, gates = fixture.TransportTests.make(
                self, finish_inflight_on_cancel=True, **options)
            sessions.append((output, children, gates))
            return output
        return app.compose_transport(context, native_factory=factory)

    def test_both_application_factories_enable_graceful_stop(self):
        context = StartContext(self.native, Event())
        with patch.object(app, 'UsbTransport') as windows:
            app.compose_transport(context)
            self.assertTrue(windows.call_args.kwargs.get('finish_inflight_on_cancel', False))
            self.assertIs(windows.call_args.kwargs['cancel'], context.cancel)
        with patch.object(linux_usb_transport, 'UsbTransport') as linux:
            app.compose_transport(context, native_factory=partial(
                linux_usb_transport.create_transport, finish_inflight_on_cancel=True))
            self.assertTrue(linux.call_args.kwargs.get('finish_inflight_on_cancel', False))
            self.assertIs(linux.call_args.kwargs['cancel'], context.cancel)
            self.assertIs(linux.call_args.kwargs['owner_factory'], linux_usb_transport.owner_factory)

    def test_stop_finishes_admitted_command_and_restart_uses_fresh_session(self):
        original_write = fixture.Port.write
        original_drain = fixture.Port.out_waiting.fget
        for stage in ('pixels', 'drain', 'brightness'):
            with self.subTest(stage=stage):
                sessions, sources = [], []
                entered, release = Event(), Event()
                def pause():
                    entered.set()
                    if not release.wait(2):
                        raise AssertionError('command barrier was not released')
                def write(port, data):
                    count = original_write(port, data)
                    if ((stage == 'pixels' and len(port.writes) == 3)
                            or (stage == 'brightness' and len(port.writes) == 1)):
                        pause()
                    return count
                def drain(port):
                    if stage == 'drain':
                        pause()
                    return original_drain(port)
                def source_factory(settings):
                    source = Source(sample=SourceSample('ready', fixture.FRAME if not sources else native_fixture.SECOND))
                    sources.append(source)
                    self.sources.append(source)
                    return source
                controller = Coordinator(self.store, source_factory,
                    transport_context_factory=lambda context: self.compose(context, sessions))
                self.controllers.append(controller)
                if stage == 'brightness':
                    self.store.migrate_to_v3(replace(self.native, schema_version=3,
                        brightness_percent=60), acknowledge_legacy_incompatibility=True)
                raw = self.store.path.read_bytes()
                with patch.object(fixture.Port, 'write', new=write), patch.object(
                        fixture.Port, 'out_waiting', new=property(drain)):
                    for index in range(2):
                        entered.clear()
                        release.clear()
                        try:
                            self.assertTrue(controller.start())
                            self.assertTrue(entered.wait(1))
                            if index:
                                controller.request_exit()
                            else:
                                controller.stop()
                                self.assertFalse(controller.start())
                            self.assertEqual(controller.snapshot().state, 'stopping')
                            self.assertFalse(controller.snapshot().exit_ready)
                        finally:
                            release.set()
                        self.assertTrue(controller.wait_stopped(2))
                        state = controller.snapshot()
                        self.assertEqual(state.state, 'stopped')
                        self.assertIsNone(state.error)
                        self.assertIsNone(state.failure_kind)
                        self.assertFalse(state.delivery_uncertain)
                        self.assertFalse(state.ownership_uncertain)
                        self.assertEqual((state.failures, state.retries), (0, 0))
                        output, children, _ = sessions[index]
                        frame = fixture.FRAME if not index else native_fixture.SECOND
                        expected = ([encode_brightness(60)] if stage == 'brightness'
                                    else list(encode_portrait(frame)))
                        self.assertEqual(children[0].port.writes, expected)
                        self.assertEqual(len(children), 1)
                        self.assertFalse(output.owned)
                        self.assertFalse(children[0].thread.is_alive())
                        self.assertTrue(sources[index].closed.is_set())
                        self.assertEqual(state.frames_sent, 0 if stage == 'brightness' else index + 1)
                        self.assertEqual(state.latest_frame, None if stage == 'brightness' else frame)
                        self.assertEqual(state.brightness_applied, 60 if stage == 'brightness' else None)
                        self.assertEqual(self.store.path.read_bytes(), raw)
                self.assertTrue(controller.snapshot().exit_ready)
                self.assertEqual(len(sessions), 2)
                self.assertIsNot(sessions[0][0], sessions[1][0])

    def test_stop_before_command_admission_has_no_writes_or_false_success(self):
        for operation in ('send', 'set_brightness'):
            with self.subTest(operation=operation):
                sessions = []
                source = Source()
                self.sources.append(source)
                def factory(context):
                    output = self.compose(context, sessions)
                    original = getattr(output, operation)
                    def cancel_before_admission(value):
                        controller.stop()
                        return original(value)
                    setattr(output, operation, cancel_before_admission)
                    return output
                controller = Coordinator(self.store, lambda settings: source,
                    transport_context_factory=factory)
                self.controllers.append(controller)
                if operation == 'set_brightness':
                    self.store.migrate_to_v3(replace(self.native, schema_version=3),
                        acknowledge_legacy_incompatibility=True)
                raw = self.store.path.read_bytes()
                controller.start()
                self.assertTrue(controller.wait_stopped(2))
                state = controller.snapshot()
                self.assertEqual(state.state, 'stopped')
                self.assertIsNone(state.error)
                self.assertEqual((state.frames_sent, state.failures, state.retries), (0, 0, 0))
                self.assertIsNone(state.latest_frame)
                self.assertIsNone(state.brightness_applied)
                self.assertFalse(state.delivery_uncertain)
                self.assertFalse(state.ownership_uncertain)
                output, children, _ = sessions[0]
                self.assertIsNone(output.last_send_timing)
                self.assertEqual(children[0].port.writes, [])
                self.assertFalse(output.owned)
                self.assertEqual(self.store.path.read_bytes(), raw)

    def test_typed_cancellation_without_stop_is_not_suppressed(self):
        from mars_display.usb_transport import UsbCancelled
        source = Source()
        self.sources.append(source)
        output = Mock(owned=False)
        output.send.side_effect = UsbCancelled()
        controller = Coordinator(self.store, lambda settings: source,
            transport_context_factory=lambda context: output)
        self.controllers.append(controller)
        controller.start()
        self.assertTrue(controller.wait_stopped(2))
        state = controller.snapshot()
        self.assertEqual((state.state, state.frames_sent, state.failures), ('error', 0, 1))
        self.assertEqual(state.failure_kind, 'native-prewrite')
        self.assertFalse(state.delivery_uncertain)

    def test_stop_does_not_hide_a_real_transfer_failure(self):
        from mars_display.usb_transport import UsbError
        source = Source()
        self.sources.append(source)
        output = Mock(owned=False)
        def fail(frame):
            controller.stop()
            raise UsbError('frame', delivery_uncertain=True)
        output.send.side_effect = fail
        controller = Coordinator(self.store, lambda settings: source,
            transport_context_factory=lambda context: output)
        self.controllers.append(controller)
        controller.start()
        self.assertTrue(controller.wait_stopped(2))
        state = controller.snapshot()
        self.assertEqual((state.frames_sent, state.failures, state.retries), (0, 1, 0))
        self.assertTrue(state.delivery_uncertain)
        self.assertEqual(state.error,
            'Native delivery is uncertain; the previous host-accepted frame is retained. No resend.')


class GracefulSafetyTests(unittest.TestCase):
    def make(self, *args, **options):
        return fixture.TransportTests.make(self, *args, finish_inflight_on_cancel=True, **options)

    test_forced_close_interrupts = fixture.TransportTests.test_cancel_inflight_and_concurrent_send_have_no_queue
    test_deadlines_reap_without_resend = fixture.TransportTests.test_open_write_drain_close_hangs_finish_and_reap_without_resend
    test_uncertain_cleanup_blocks_reopen = fixture.TransportTests.test_failed_handle_close_retains_ownership_and_rejects_reopen

    def test_cancelled_start_still_has_no_effects(self):
        from mars_display.usb_transport import UsbError
        cancel = Event()
        cancel.set()
        output, children, gates = self.make(cancel=cancel)
        with self.assertRaises(UsbError) as raised:
            output.open()
        self.assertEqual(raised.exception.phase, 'startup')
        self.assertFalse(raised.exception.delivery_uncertain)
        self.assertFalse(output.owned)
        self.assertEqual((children, gates), ([], []))

    def test_stop_after_reply_keeps_confirmed_command_success(self):
        from mars_display import usb_ipc as ipc
        receive = ipc.receive_packet
        for operation in ('send', 'set_brightness'):
            with self.subTest(operation=operation):
                cancel = Event()
                output, children, _ = self.make(cancel=cancel)
                output.open()
                def stop_on_reply(*args, **kwargs):
                    packet = receive(*args, **kwargs)
                    if packet[0] in (ipc.GROUPED_REPLY, ipc.REPLY) and packet[1] == 2:
                        cancel.set()
                    return packet
                with patch.object(ipc, 'receive_packet', side_effect=stop_on_reply):
                    result = getattr(output, operation)(fixture.FRAME if operation == 'send' else 60)
                self.assertIsNone(result)
                self.assertTrue(cancel.is_set())
                output.close()
                self.assertFalse(output.owned)
                expected = list(encode_portrait(fixture.FRAME)) if operation == 'send' else [encode_brightness(60)]
                self.assertEqual(children[0].port.writes, expected)

    def test_repeated_rejection_preserves_session_and_prior_timing(self):
        from mars_display.usb_transport import UsbCancelled
        cancel = Event()
        output, children, _ = self.make(cancel=cancel)
        output.open()
        output.send(fixture.FRAME)
        timing = output.last_send_timing
        writes = tuple(children[0].port.writes)
        cancel.set()
        for method, value in ((output.send, fixture.FRAME), (output.set_brightness, 60)) * 2:
            with self.assertRaises(UsbCancelled) as caught:
                method(value)
            error = caught.exception
            self.assertEqual(str(error), 'USB cancelled failed; no automatic retry.')
            self.assertEqual((error.phase, error.delivery_uncertain,
                              error.ownership_uncertain), ('cancelled', False, False))
            self.assertIs(output.last_send_timing, timing)
            self.assertEqual(tuple(children[0].port.writes), writes)
            self.assertTrue(output.owned)
            self.assertTrue(children[0].thread.is_alive())
        output.close()
        self.assertFalse(output.owned)
        self.assertFalse(children[0].thread.is_alive())

    def test_stop_during_stalled_command_keeps_deadline_and_uncertainty(self):
        from mars_display import usb_ipc as ipc
        from mars_display.usb_transport import UsbCancelled, UsbError
        for operation, value in (('send', fixture.FRAME), ('set_brightness', 60)):
            with self.subTest(operation=operation):
                cancel = Event()
                output, children, _ = self.make(
                    mode='write', cancel=cancel,
                    budgets=ipc.Budgets(start=1, frame=.15, close=.1, reap=.3))
                output.open()
                original = fixture.Port.write
                def stop_then_stall(port, data):
                    cancel.set()
                    return original(port, data)
                started = time.monotonic()
                with patch.object(fixture.Port, 'write', stop_then_stall):
                    with self.assertRaises(UsbError) as caught:
                        getattr(output, operation)(value)
                self.assertNotIsInstance(caught.exception, UsbCancelled)
                phase = 'frame' if operation == 'send' else 'brightness'
                self.assertEqual(str(caught.exception),
                                 'USB ' + phase + ' failed; no automatic retry.')
                self.assertTrue(caught.exception.delivery_uncertain)
                self.assertFalse(caught.exception.ownership_uncertain)
                self.assertLess(time.monotonic() - started, .9)
                self.assertEqual(len(children[0].port.writes), 1)
                self.assertIsNone(output.last_send_timing)
                self.assertFalse(output.owned)
                self.assertFalse(children[0].thread.is_alive())
