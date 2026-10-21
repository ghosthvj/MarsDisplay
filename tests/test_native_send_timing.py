"""Send details through public snapshots and test-owned native worker peers."""
import contextlib
from dataclasses import fields, replace
import io
import itertools
import struct
import unittest
from unittest.mock import patch

from mars_display import usb_ipc as ipc, usb_worker as worker
from mars_display.lifecycle import Coordinator, SourceSample
from mars_display.usb_transport import SendTiming
from test_lifecycle import Source, GateWait
from test_native_lifecycle import NativeOutput, FIRST
import test_native_timing as timing
import test_usb_transport as transport


STAGES = ('decode', 'identity', 'encode', 'write', 'drain', 'body_encode', 'exchange')


class SendTimingTests(unittest.TestCase):
    setUp = timing.TimingTests.setUp
    tearDown = timing.TimingTests.tearDown
    assert_stage = timing.TimingTests.assert_stage

    def test_real_transport_success_then_invalid_reply_retains_all_accepted_detail(self):
        for mode in ('failure', 'short', 'negative', 'nan', 'inf', 'wrong_request', 'wrong_kind', 'status'):
            with self.subTest(mode=mode):
                outputs, children, gates = [], [], []
                snapshots = []
                original_receive = ipc.receive_packet
                original_session = worker.run_session
                ticks = itertools.count()
                def receive(channel, *args, **kwargs):
                    kind, request, body = original_receive(channel, *args, **kwargs)
                    if kind == ipc.TIMED_REPLY and request == 3:
                        if mode == 'failure':
                            return ipc.REPLY, request, bytes([worker.WRITE_ERROR])
                        if mode == 'short':
                            body = b'\x00'
                        if mode in ('negative', 'nan', 'inf'):
                            value = -1 if mode == 'negative' else float(mode)
                            body = struct.pack('!B5d', 0, value, 0, 0, 0, 0)
                        if mode == 'wrong_request':
                            request += 1
                        if mode == 'wrong_kind':
                            kind = ipc.FRAME
                        if mode == 'status':
                            body = struct.pack('!B5d', 1, 0, 0, 0, 0, 0)
                    return kind, request, body
                def factory(context):
                    output, peers, handles = transport.TransportTests.make(
                        self, cancel=context.cancel, timing_clock=lambda: next(ticks))
                    outputs.append(output)
                    children.append(peers)
                    gates.append(handles)
                    return output
                def wait(cancel, seconds):
                    snapshots.append(controller.snapshot())
                    return False
                controller = Coordinator(self.store, lambda _: Source(
                    sample=SourceSample('ready', FIRST)), transport_context_factory=factory,
                    wait=wait, diagnostic_clock=lambda: 0)
                self.controllers.append(controller)
                raw = self.store.path.read_bytes()
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                     patch.object(ipc, 'receive_packet', side_effect=receive), \
                     patch.object(worker, 'run_session', side_effect=lambda *a, **kw:
                         original_session(*a, **kw, timing_clock=lambda: next(ticks))):
                    self.assertTrue(controller.start())
                    self.assertTrue(controller.wait_stopped(2))
                status = controller.snapshot()
                self.assertEqual((stdout.getvalue(), stderr.getvalue()), ('', ''))
                self.assertEqual((status.state, status.frames_sent, status.failures, status.retries),
                                 ('error', 1, 1, 0))
                self.assertEqual(status.error, 'Native delivery is uncertain; the previous host-accepted frame is retained. No resend.')
                self.assertIs(status.latest_frame, FIRST)
                self.assertEqual(len(snapshots), 1)
                for name in STAGES:
                    value = getattr(outputs[0].last_send_timing, name)
                    self.assert_stage(getattr(status.native_timing, name), 1, value, value, value, value)
                    self.assertEqual(getattr(status.native_timing, name),
                                     getattr(snapshots[0].native_timing, name))
                self.assertEqual(status.native_timing.host_send.count, 1)
                self.assertEqual(status.native_timing.source_read.count, 2)
                self.assertEqual(self.store.path.read_bytes(), raw)
                self.assertFalse(outputs[0].owned)
                self.assertFalse(children[0][0].thread.is_alive())
                self.assertTrue(gates[0][0].closed)
                self.assertEqual(len(children[0][0].port.writes), 244)
                controller.stop()
                self.assertEqual(controller.snapshot().native_timing, status.native_timing)

    def test_optional_details_and_independent_numeric_aggregates(self):
        for optional in ('absent', None, 'measured'):
            with self.subTest(optional=optional):
                gate = GateWait()
                class Output(NativeOutput):
                    def send(self, frame):
                        super().send(frame)
                        if optional == 'measured':
                            # Real measured zero must differ from unavailable detail.
                            self.last_send_timing = (SendTiming(*([0.] * 7)) if self.sends == 1
                                                     else SendTiming(*([.5] * 7)))
                output = Output()
                if optional is None:
                    output.last_send_timing = None
                def wait(cancel, seconds):
                    return gate(cancel, seconds) if output.sends == 2 else False
                controller = Coordinator(self.store, lambda _: Source(
                    sample=SourceSample('ready', FIRST)), transport_context_factory=lambda _: output,
                    wait=wait, diagnostic_clock=lambda: 0)
                self.controllers.append(controller)
                controller.start()
                self.assertTrue(gate.entered.wait(1))
                before = controller.snapshot()
                self.assertEqual((before.frames_sent, before.failures, before.retries), (2, 0, 0))
                self.assertIs(before.latest_frame, FIRST)
                self.assertEqual(len(fields(before.native_timing)), 10)
                for name in STAGES:
                    expected = (2, .5, 0, .5, .25) if optional == 'measured' else (0, 0, 0, 0, 0)
                    self.assert_stage(getattr(before.native_timing, name), *expected)
                self.assertFalse(controller.start())
                self.assertEqual(controller.snapshot().native_timing, before.native_timing)
                controller.stop()
                self.assertTrue(controller.wait_stopped(2))
                self.assertEqual(controller.snapshot().native_timing, before.native_timing)
                # An admitted native Start resets even if setup fails.
                output.fail_open = True
                controller.start()
                self.assertTrue(controller.wait_stopped(2))
                for field in fields(controller.snapshot().native_timing):
                    self.assert_stage(getattr(controller.snapshot().native_timing, field.name), 0, 0, 0, 0, 0)
                self.assertEqual(controller.snapshot().frames_sent, 2)
                controller.stop()
                controller.save_settings(replace(self.native, output_mode='simulated', native_profile=None))
                output.fail_open = False
                controller.start()
                self.assertTrue(gate.entered.wait(1))
                self.assertIsNone(controller.snapshot().native_timing)
                controller.stop()
                self.assertTrue(controller.wait_stopped(2))
                self.store.save(self.native)
