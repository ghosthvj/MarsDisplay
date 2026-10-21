"""Numeric send detail through bounded IPC and test-owned worker peers only."""
from dataclasses import FrozenInstanceError
import contextlib
import io
import struct
import threading
import time
import unittest
from unittest.mock import patch

from mars_display import usb_ipc as ipc, usb_worker as worker
from mars_display.usb_transport import UsbError
import test_usb_ipc as framing
import test_usb_transport as transport
import test_usb_worker as session


class TimingTests(unittest.TestCase):
    make = transport.TransportTests.make
    start = session.WorkerTests.start
    request = session.WorkerTests.request

    def test_fixed_wire_and_legacy_bytes(self):
        body = struct.pack('!B5d', 0, 1, 2, 3, 4, 5)
        detail = ipc.WorkerTiming(1, 2, 3, 4, 5)
        self.assertEqual(ipc.encode_timing(detail), body)
        self.assertEqual(ipc.decode_timing(body), detail)
        for kind, payload in ((ipc.TIMED_REPLY, body),
                (ipc.TIMED_FRAME, ipc.encode_frame(session.FRAME)),
                (ipc.FRAME, ipc.encode_frame(session.FRAME)),
                (ipc.OPEN, worker.IDENTITY.encode()), (ipc.CLOSE, b''),
                (ipc.REPLY, b'\x00')):
            peer = framing.BytesPeer()
            ipc.send_packet(peer, kind, 2, payload, time.monotonic()+1)
            expected = struct.pack('!4sBBHII', b'MUSB', 1, kind, 0, 2, len(payload))+payload
            self.assertEqual(peer.sent, expected)
            self.assertEqual(ipc.receive_packet(framing.BytesPeer(expected), time.monotonic()+1),
                             (kind, 2, payload))
        for kind, size in ((ipc.TIMED_FRAME, 1), (ipc.TIMED_REPLY, 1),
                           (ipc.TIMED_REPLY, 42), (ipc.TIMED_FRAME, 2**32-1)):
            peer = framing.BytesPeer(ipc.HEADER.pack(b'MUSB', 1, kind, 0, 2, size)+b'untouched')
            with self.assertRaises(ipc.ProtocolError):
                ipc.receive_packet(peer, time.monotonic()+1)
            self.assertEqual(peer.data, b'untouched')
            self.assertEqual(peer.sent, b'')
            outbound = framing.BytesPeer()
            with self.assertRaises(ValueError):
                ipc.send_packet(outbound, kind, 2, b'x', time.monotonic()+1)
            self.assertEqual((outbound.sent, outbound.reads), (b'', []))
        for body in (b'', b'\x00', struct.pack('!B5d', 1, 0, 0, 0, 0, 0),
                     *(struct.pack('!B5d', 0, value, 0, 0, 0, 0)
                       for value in (-1, float('nan'), float('inf')))):
            with self.assertRaises(ValueError):ipc.decode_timing(body)

    def test_worker_measures_five_stages_and_preserves_stream(self):
        ticks = iter(range(10))
        original = worker.run_session
        with patch.object(worker, 'run_session', side_effect=lambda *a, **kw:
                          original(*a, **kw, timing_clock=lambda: next(ticks))):
            c, p, events, results, thread = self.start()
            self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
            ipc.send_packet(c, ipc.TIMED_FRAME, 2, ipc.encode_frame(session.FRAME), time.monotonic()+1)
            kind, request, body = ipc.receive_packet(c, time.monotonic()+1)
            self.assertEqual((kind, request, body),
                (ipc.TIMED_REPLY, 2, struct.pack('!B5d', 0, 1, 1, 1, 1, 1)))
            self.assertEqual(self.request(c, ipc.CLOSE, 3), worker.OK)
            thread.join(1)
        self.assertEqual(results, [0])
        self.assertEqual((p.opens, p.closes), (1, 1))
        self.assertEqual(tuple(p.writes), session.encode_portrait(session.FRAME))
        self.assertEqual((len(p.writes), sum(map(len, p.writes))), (122, 307222))
        self.assertEqual(events[2:], ['inventory'])

    def test_timed_failure_has_only_legacy_status_and_no_retry(self):
        for failure, status, count in (('short', worker.WRITE_ERROR, 3),
                ('drain', worker.DRAIN_ERROR, 122), ('identity', worker.IDENTITY_ERROR, 0),
                ('frame', worker.INVALID, 0)):
            with self.subTest(failure=failure):
                snapshots = [(session.DEVICE,), ()] if failure == 'identity' else None
                c, p, _, results, thread = self.start(snapshots, failure)
                self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
                body = ipc.encode_frame(session.FRAME)
                if failure == 'frame':body = ipc.METADATA.pack(480, 320, 0)+session.FRAME.rgb
                self.assertEqual(self.request(c, ipc.TIMED_FRAME, 2, body), status)
                thread.join(1)
                self.assertEqual((results, p.opens, p.closes, len(p.writes)), ([1], 1, 1, count))

    def test_success_detail_is_frozen_retained_and_reset_on_fresh_open(self):
        ticks = iter((10, 12, 20, 25, 30))
        obj, children, _ = self.make(timing_clock=lambda: next(ticks))
        self.assertIsNone(obj.last_send_timing)
        obj.open()
        self.assertIsNone(obj.send(session.FRAME))
        detail = obj.last_send_timing
        self.assertEqual((detail.body_encode, detail.exchange), (2, 5))
        with self.assertRaises(FrozenInstanceError):detail.exchange = 0
        with self.assertRaises(AttributeError):obj.last_send_timing = None
        obj.open()
        self.assertIs(obj.last_send_timing, detail)
        with self.assertRaises(ValueError):obj.send(transport.RGBFrame(480, 320, session.FRAME.rgb, 0))
        self.assertEqual(len(children[0].port.writes), 122)
        self.assertIs(obj.last_send_timing, detail)
        obj.close()
        self.assertIs(obj.last_send_timing, detail)
        obj.open()
        self.assertIsNone(obj.last_send_timing)

    def test_deadline_and_uncertain_cleanup_retain_last_success(self):
        calls = []
        def diagnostic_clock():
            calls.append(None)
            if len(calls) == 8:
                time.sleep(0.12)  # Final sample cannot extend the operation deadline.
            return time.monotonic()
        obj, children, gates = self.make(timing_clock=diagnostic_clock,
            budgets=ipc.Budgets(start=1, frame=0.1, close=0.5, reap=0.2))
        obj.open();obj.send(session.FRAME)
        detail = obj.last_send_timing
        gates[0].fail_close = True
        with self.assertRaises(UsbError) as raised:obj.send(session.FRAME)
        self.assertTrue(raised.exception.ownership_uncertain)
        self.assertTrue(obj.owned)
        self.assertIs(obj.last_send_timing, detail)
        with self.assertRaises(UsbError):obj.open()
        self.assertIs(obj.last_send_timing, detail)
        self.assertEqual((len(children), len(children[0].port.writes)), (1, 244))
        gates[0].fail_close = False
        obj.close()
        self.assertFalse(obj.owned)
        self.assertIs(obj.last_send_timing, detail)

    def test_invalid_replies_and_final_cancel_never_publish(self):
        for mode in ('ordinary_ok', 'wrong_request', 'wrong_kind', 'status', 'short',
                     'negative', 'nan', 'inf', 'failure', 'cancel'):
            with self.subTest(mode=mode):
                cancel = threading.Event()
                obj, children, gates = self.make(cancel=cancel)
                obj.open();obj.send(session.FRAME)
                detail = obj.last_send_timing
                original = ipc.receive_packet
                def receive(channel, *a, **kw):
                    kind, request, body = original(channel, *a, **kw)
                    if kind != ipc.TIMED_REPLY:return kind, request, body
                    if mode == 'cancel':cancel.set()
                    if mode == 'ordinary_ok':return ipc.REPLY, request, b'\x00'
                    if mode == 'failure':return ipc.REPLY, request, bytes([worker.WRITE_ERROR])
                    if mode == 'wrong_request':request += 1
                    if mode == 'wrong_kind':kind = ipc.FRAME
                    if mode == 'short':body = b'\x00'
                    if mode == 'status':body = struct.pack('!B5d', 1, 0, 0, 0, 0, 0)
                    if mode in ('negative', 'nan', 'inf'):
                        value = -1 if mode == 'negative' else float(mode)
                        body = struct.pack('!B5d', 0, 0, 0, 0, 0, value)
                    return kind, request, body
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                     patch.object(ipc, 'receive_packet', side_effect=receive):
                    with self.assertRaises(UsbError) as raised:obj.send(session.FRAME)
                self.assertEqual(str(raised.exception), 'USB frame failed; no automatic retry.')
                self.assertEqual((stdout.getvalue(), stderr.getvalue()), ('', ''))
                self.assertIs(obj.last_send_timing, detail)
                self.assertFalse(obj.owned)
                self.assertTrue(gates[0].closed)
                self.assertFalse(children[0].thread.is_alive())
                self.assertEqual((len(children), len(children[0].port.writes)), (1, 244))


if __name__ == '__main__':unittest.main()
