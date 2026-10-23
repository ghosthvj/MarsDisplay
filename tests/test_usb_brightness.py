"""Discrete native brightness with fake ports and owned local peers only."""
from dataclasses import replace
import threading
import time
import unittest
from unittest.mock import patch

from mars_display import usb_ipc as ipc, usb_protocol, usb_worker as worker
from mars_display.usb_transport import UsbError
import test_usb_ipc as ipc_tests
import test_usb_worker as worker_tests
import test_usb_transport as transport_tests

LEVELS = {20: '33000000006e', 40: '26400000006e', 60: '19800000006e',
          80: '0cc00000006e', 100: '00000000006e'}
INVALID = (True, False, 20.0, 60.0, '60', None, 0, -20, 21, 101, 256)


class CodecTests(unittest.TestCase):
    def test_all_exact_commands_and_integer_equivalence(self):
        for percent, expected in LEVELS.items():
            with self.subTest(percent=percent):
                self.assertEqual(int(255 - ((percent / 100) * 255)),
                                 255 - percent * 255 // 100)
                self.assertEqual(usb_protocol.encode_brightness(percent), bytes.fromhex(expected))

    def test_invalid_values(self):
        for value in INVALID:
            with self.subTest(value=value), self.assertRaises(ValueError):
                usb_protocol.encode_brightness(value)

    def test_ipc_fixed_shape_and_legacy_close(self):
        for kind, body in ((ipc.BRIGHTNESS, b'\x3c'), (ipc.CLOSE, b'')):
            peer = ipc_tests.BytesPeer()
            ipc.send_packet(peer, kind, 1, body, time.monotonic() + 1)
            self.assertEqual(ipc.receive_packet(ipc_tests.BytesPeer(bytes(peer.sent)),
                             time.monotonic() + 1), (kind, 1, body))
        for body in (b'', b'\x14\x28'):
            peer = ipc_tests.BytesPeer()
            with self.assertRaises(ValueError):
                ipc.send_packet(peer, ipc.BRIGHTNESS, 1, body, time.monotonic() + 1)
            self.assertEqual((peer.sent, peer.reads), (b'', []))
            header = ipc.HEADER.pack(b'MUSB', 1, ipc.BRIGHTNESS, 0, 1, len(body))
            reader = ipc_tests.BytesPeer(header + body)
            with self.assertRaises(ipc.ProtocolError):
                ipc.receive_packet(reader, time.monotonic() + 1)
            self.assertEqual(reader.data, body)


class WorkerTests(unittest.TestCase):
    start = worker_tests.WorkerTests.start
    request = worker_tests.WorkerTests.request

    def test_frames_and_all_levels_share_one_open_exact_order(self):
        c, p, e, r, t = self.start()
        self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
        frame = worker_tests.FRAME
        self.assertEqual(self.request(c, ipc.FRAME, 2, ipc.encode_frame(frame)), worker.OK)
        for seq, level in enumerate(LEVELS, 3):
            self.assertEqual(self.request(c, ipc.BRIGHTNESS, seq, bytes([level])), worker.OK)
        self.assertEqual(self.request(c, ipc.FRAME, 8, ipc.encode_frame(frame)), worker.OK)
        self.assertEqual(self.request(c, ipc.CLOSE, 9), worker.OK)
        t.join(1)
        packets = list(usb_protocol.encode_portrait(frame))
        self.assertEqual(p.writes, packets + [bytes.fromhex(x) for x in LEVELS.values()] + packets)
        self.assertEqual((p.opens, p.closes, r), (1, 1, [0]))
        self.assertEqual(e.count('inventory'), 8)

    def test_invalid_and_before_open_have_no_serial_effects(self):
        for opened, level in ((False, 60), (True, 0), (True, 21), (True, 255)):
            with self.subTest(opened=opened, level=level):
                c, p, e, r, t = self.start()
                if opened:
                    self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
                prior = list(e)
                self.assertEqual(self.request(c, ipc.BRIGHTNESS, 2 if opened else 1,
                                             bytes([level])), worker.INVALID)
                t.join(1)
                self.assertEqual((p.writes, e, r), ([], prior, [1]))
                self.assertEqual((p.opens, p.closes), (1, 1) if opened else (0, 0))

    def test_identity_change_prevents_write(self):
        for changed in (replace(worker_tests.DEVICE, device='COM6'),
                        replace(worker_tests.DEVICE, serial_number='foreign')):
            c, p, e, r, t = self.start([(worker_tests.DEVICE,), (changed,)])
            self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
            self.assertEqual(self.request(c, ipc.BRIGHTNESS, 2, b'\x3c'), worker.IDENTITY_ERROR)
            t.join(1)
            self.assertEqual((p.writes, p.opens, p.closes, r), ([], 1, 1, [1]))

    def test_short_write_and_drain_failure_never_retry(self):
        for mode, status in (('short', worker.WRITE_ERROR), ('drain', worker.DRAIN_ERROR)):
            c, p, e, r, t = self.start(failure=mode)
            self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
            if mode == 'short':
                def short(data):
                    p.writes.append(data)
                    return len(data) - 1
                p.write = short
            self.assertEqual(self.request(c, ipc.BRIGHTNESS, 2, b'\x3c'), status)
            t.join(1)
            self.assertEqual((p.writes, p.opens, p.closes, r),
                             ([bytes.fromhex(LEVELS[60])], 1, 1, [1]))


class TransportTests(unittest.TestCase):
    make = transport_tests.TransportTests.make

    def test_invalid_no_effects_and_not_open(self):
        obj, children, _ = self.make()
        with self.assertRaises(UsbError) as raised:
            obj.set_brightness(60)
        self.assertEqual(raised.exception.phase, 'not open')
        self.assertEqual(children, [])
        obj.open()
        for value in INVALID:
            with self.subTest(value=value), self.assertRaises(ValueError):
                obj.set_brightness(value)
        self.assertTrue(obj.owned)
        self.assertEqual(children[0].port.writes, [])
        self.assertIsNone(obj.set_brightness(60))
        self.assertEqual(children[0].port.writes, [bytes.fromhex(LEVELS[60])])

    def test_timing_preserved_and_frames_unchanged(self):
        obj, children, _ = self.make()
        obj.open()
        obj.send(transport_tests.FRAME)
        detail = obj.last_send_timing
        with patch.object(obj, '_timing_clock', side_effect=AssertionError('brightness measured')):
            for level in LEVELS:
                self.assertIsNone(obj.set_brightness(level))
                self.assertIs(obj.last_send_timing, detail)
        obj.send(transport_tests.FRAME)
        packets = list(usb_protocol.encode_portrait(transport_tests.FRAME))
        self.assertEqual(children[0].port.writes,
                         packets + [bytes.fromhex(x) for x in LEVELS.values()] + packets)
        obj.close()
        self.assertEqual((len(children), children[0].port.opens, children[0].port.closes), (1, 1, 1))

    def test_timeout_drain_and_lost_reply_cleanup_uncertain(self):
        for mode in ('write', 'drain', 'lost'):
            with self.subTest(mode=mode):
                obj, children, _ = self.make(None if mode == 'lost' else mode,
                    budgets=ipc.Budgets(start=1, frame=0.15, close=0.1, reap=0.2))
                obj.open()
                if mode == 'lost':
                    original = children[0].port.write
                    def lost(data):
                        result = original(data)
                        children[0].kill()
                        return result
                    children[0].port.write = lost
                with self.assertRaises(UsbError) as raised:
                    obj.set_brightness(60)
                self.assertEqual(raised.exception.phase, 'brightness')
                self.assertTrue(raised.exception.delivery_uncertain)
                self.assertFalse(obj.owned)
                self.assertEqual((len(children), len(children[0].port.writes)), (1, 1))
                self.assertFalse(children[0].thread.is_alive())

    def test_cancel_overlap_and_close_cleanup(self):
        cancel = threading.Event()
        obj, children, _ = self.make('write', cancel=cancel)
        obj.open()
        outcomes = []
        def send():
            try:
                obj.set_brightness(60)
            except UsbError as error:
                outcomes.append(error)
        thread = threading.Thread(target=send)
        thread.start()
        try:
            deadline = time.monotonic() + 1
            while not children[0].port.writes and time.monotonic() < deadline:
                threading.Event().wait(0.005)
            self.assertEqual(len(children[0].port.writes), 1)
            for operation in (lambda: obj.set_brightness(80), lambda: obj.send(transport_tests.FRAME)):
                with self.assertRaises(UsbError) as raised:
                    operation()
                self.assertEqual(raised.exception.phase, 'busy')
            cancel.set()
            obj.close()
            thread.join(1)
            self.assertFalse(thread.is_alive())
            self.assertFalse(obj.owned)
            self.assertEqual(len(outcomes), 1)
            self.assertTrue(outcomes[0].delivery_uncertain)
            self.assertEqual(len(children[0].port.writes), 1)
        finally:
            cancel.set()
            children[0].kill()
            thread.join(1)

    def test_known_rejection_is_not_delivery_uncertain(self):
        obj, children, _ = self.make()
        obj.open()
        with patch.object(worker, '_resolve', side_effect=ValueError('changed')):
            with self.assertRaises(UsbError) as raised:
                obj.set_brightness(60)
        self.assertFalse(raised.exception.delivery_uncertain)
        self.assertFalse(obj.owned)
        self.assertEqual(children[0].port.writes, [])
