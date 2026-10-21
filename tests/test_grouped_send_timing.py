"""Grouped diagnostics through public framing and owned worker sockets."""
import struct
import time
import unittest
from unittest.mock import patch

from mars_display import usb_ipc as ipc, usb_worker as worker
import test_usb_ipc as framing
import test_usb_worker as session


class GroupedTimingTests(unittest.TestCase):
    start = session.WorkerTests.start
    request = session.WorkerTests.request

    def test_strict_fixed_extension_and_each_numeric_slot(self):
        detail = ipc.WorkerTiming(1, 2, 3, 4, 5, groups=ipc.WriteTiming(6, 7, 8))
        body = struct.pack('!B8d', 0, *range(1, 9))
        self.assertEqual(ipc.encode_grouped_timing(detail), body)
        self.assertEqual(ipc.decode_grouped_timing(body), detail)
        for kind, payload in ((ipc.GROUPED_REPLY, body),
                              (ipc.GROUPED_FRAME, ipc.encode_frame(session.FRAME))):
            peer = framing.BytesPeer()
            ipc.send_packet(peer, kind, 2, payload, time.monotonic()+1)
            self.assertEqual(ipc.receive_packet(framing.BytesPeer(peer.sent), time.monotonic()+1),
                             (kind, 2, payload))
            for size in (0, 1, len(payload)-1, len(payload)+1, 2**32-1):
                peer = framing.BytesPeer(ipc.HEADER.pack(b'MUSB', 1, kind, 0, 2, size)+b'untouched')
                with self.assertRaises(ipc.ProtocolError):
                    ipc.receive_packet(peer, time.monotonic()+1)
                self.assertEqual(peer.data, b'untouched')
        for slot in range(8):
            for value in (-1, float('nan'), float('inf'), -float('inf')):
                values = [0.] * 8
                values[slot] = value
                with self.assertRaises(ValueError):
                    ipc.decode_grouped_timing(struct.pack('!B8d', 0, *values))
        for payload in (body[:-1], body+b'x', bytes([1])+body[1:]):
            with self.assertRaises(ValueError):
                ipc.decode_grouped_timing(payload)

    def test_group_boundaries_preserve_exact_stream_and_options(self):
        ticks = iter((0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 15, 16, 17, 18))
        original = worker.run_session
        with patch.object(worker, 'run_session', side_effect=lambda *a, **kw:
                          original(*a, **kw, timing_clock=lambda: next(ticks))):
            c, port, events, results, thread = self.start()
            self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
            ipc.send_packet(c, ipc.GROUPED_FRAME, 2, ipc.encode_frame(session.FRAME), time.monotonic()+1)
            kind, request, body = ipc.receive_packet(c, time.monotonic()+1)
            self.assertEqual((kind, request), (ipc.GROUPED_REPLY, 2))
            self.assertEqual(ipc.decode_grouped_timing(body),
                             ipc.WorkerTiming(1, 1, 1, 10, 1, groups=ipc.WriteTiming(1, 2, 3)))
            self.assertEqual(self.request(c, ipc.CLOSE, 3), worker.OK)
            thread.join(1)
        self.assertEqual(results, [0])
        self.assertEqual((port.opens, port.closes, port.dtr, port.port), (1, 1, True, 'COM5'))
        self.assertEqual(tuple(port.writes), session.encode_portrait(session.FRAME))
        self.assertEqual((len(port.writes), sum(map(len, port.writes))), (122, 307222))
        self.assertEqual([len(packet) for packet in port.writes[2:]], [2560]*120)
        self.assertEqual(events, ['inventory', dict(port=None, baudrate=115200, bytesize=8,
            parity='N', stopbits=1, rtscts=True, dsrdtr=False, write_timeout=3, timeout=1), 'inventory'])

    def test_each_failed_group_has_only_status_cleanup_and_no_resend(self):
        for position in (1, 2, 3, 122):
            with self.subTest(position=position):
                original = session.Port.write
                def write(port, data):
                    result = original(port, data)
                    return result-1 if len(port.writes) == position else result
                with patch.object(session.Port, 'write', write):
                    c, port, _, results, thread = self.start()
                    self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
                    self.assertEqual(self.request(c, ipc.GROUPED_FRAME, 2,
                        ipc.encode_frame(session.FRAME)), worker.WRITE_ERROR)
                    thread.join(1)
                self.assertEqual((results, port.opens, port.closes, len(port.writes)),
                                 ([1], 1, 1, position))
