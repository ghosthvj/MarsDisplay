"""Public bounded IPC rules; no native ports or application state."""
import socket
import struct
import threading
import time
import unittest

from mars_display.frames import RGBFrame
from mars_display import usb_ipc as ipc


class BytesPeer:
    def __init__(self, data=b''):
        self.data, self.sent, self.reads = data, bytearray(), []
    def settimeout(self, seconds):
        pass
    def recv(self, size):
        self.reads.append(size)
        value, self.data = self.data[:min(size, 7)], self.data[min(size, 7):]
        return value
    def send(self, data):
        size = min(11, len(data))
        self.sent.extend(data[:size])
        return size


class IPCTests(unittest.TestCase):
    def test_exact_header_fragmented_roundtrip(self):
        peer = BytesPeer()
        ipc.send_packet(peer, ipc.OPEN, 7, b'identity', time.monotonic()+1)
        expected = struct.pack('!4sBBHII', b'MUSB', 1, ipc.OPEN, 0, 7, 8)+b'identity'
        self.assertEqual(bytes(peer.sent), expected)
        reader = BytesPeer(expected)
        self.assertEqual(ipc.receive_packet(reader, time.monotonic()+1), (ipc.OPEN, 7, b'identity'))
        self.assertFalse(reader.data)

    def test_invalid_outbound_input_has_zero_writes(self):
        for kind, seq, body in [(99,1,b''),(ipc.CLOSE,1,b'x'),(ipc.REPLY,1,b''),
                                 (ipc.HELLO,0,b'x'),(ipc.OPEN,True,b'id'),
                                 (ipc.OPEN,-1,b'id'),(ipc.OPEN,1,b'x'*129),
                                 (ipc.FRAME,1,b'x')]:
            with self.subTest(kind=kind,seq=seq):
                peer=BytesPeer()
                with self.assertRaises((ValueError, TypeError)):
                    ipc.send_packet(peer,kind,seq,body,time.monotonic()+1)
                self.assertEqual(peer.sent, b'')
                self.assertEqual(peer.reads, [])

    def test_bad_headers_reject_before_body_allocation(self):
        for magic,version,kind,flags,length in [(b'NOPE',1,ipc.OPEN,0,1),
                (b'MUSB',2,ipc.OPEN,0,1),(b'MUSB',1,99,0,1),
                (b'MUSB',1,ipc.OPEN,1,1),(b'MUSB',1,ipc.FRAME,0,2**32-1)]:
            peer=BytesPeer(struct.pack('!4sBBHII',magic,version,kind,flags,1,length)+b'untouched')
            with self.subTest(magic=magic,version=version,kind=kind,length=length), self.assertRaises(ipc.ProtocolError):
                ipc.receive_packet(peer,time.monotonic()+1)
            self.assertEqual(peer.data,b'untouched')
            self.assertLessEqual(max(peer.reads),16)

    def test_truncated_eof_and_pre_cancel_never_write(self):
        peer=BytesPeer(b'MUSB')
        with self.assertRaises(ipc.ProtocolError):
            ipc.receive_packet(peer,time.monotonic()+1)
        cancel=threading.Event();cancel.set(); peer=BytesPeer()
        with self.assertRaises(ipc.Cancelled):
            ipc.send_packet(peer,ipc.CLOSE,1,b'',time.monotonic()+1,cancel=cancel)
        self.assertEqual(peer.sent,b'')

    def test_stalled_read_and_write_have_total_deadlines(self):
        for direction in ('read','write'):
            a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close)
            a.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,1024)
            b.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024)
            if direction == 'write':
                # SO_SNDBUF alone does not bound the peer's Windows receive queue.
                # Establish actual backpressure before timing the public operation.
                fill_deadline, filled = time.monotonic()+2, 0
                while True:
                    remaining = fill_deadline-time.monotonic()
                    self.assertGreater(remaining, 0, 'Could not establish socket backpressure')
                    self.assertLess(filled, 16*1024*1024, 'Socket backpressure fill exceeded cap')
                    a.settimeout(min(0.05, remaining))
                    try:
                        sent = a.send(b'x'*65536)
                    except socket.timeout:
                        break
                    self.assertGreater(sent, 0)
                    filled += sent
            start=time.monotonic()
            with self.subTest(direction=direction), self.assertRaises(TimeoutError):
                if direction=='read':ipc.receive_packet(a,start+0.05)
                else:ipc.send_packet(a,ipc.FRAME,1,b'x'*ipc.FRAME_BYTES,start+0.05)
            self.assertLess(time.monotonic()-start,0.5)

    def test_nonfinite_or_missing_send_deadlines_reject_without_io(self):
        for deadline in (None, True, float('nan'), float('inf')):
            with self.subTest(deadline=deadline):
                peer = BytesPeer()
                with self.assertRaises(ValueError):
                    ipc.send_packet(peer, ipc.CLOSE, 1, b'', deadline)
                self.assertEqual((peer.sent, peer.reads), (b'', []))
        for deadline in (True, float('nan'), float('inf')):
            with self.subTest(deadline=deadline):
                peer = BytesPeer()
                with self.assertRaises(ValueError):
                    ipc.receive_packet(peer, deadline)
                self.assertEqual((peer.sent, peer.reads), (b'', []))

    def test_frame_codec_keeps_metadata_and_rejects_landscape(self):
        frame=RGBFrame(320,480,b'\x00'*460800,123.5)
        body=ipc.encode_frame(frame)
        self.assertEqual(body[:12],struct.pack('!HHd',320,480,123.5))
        self.assertEqual(len(body),460812)
        self.assertEqual(ipc.decode_frame(body),frame)
        with self.assertRaises(ValueError):ipc.encode_frame(RGBFrame(480,320,frame.rgb,0))
        for body in (body[:-1],struct.pack('!HHd',320,480,float('nan'))+frame.rgb,
                     struct.pack('!HHd',480,320,0)+frame.rgb):
            with self.subTest(length=len(body)), self.assertRaises(ValueError):ipc.decode_frame(body)


if __name__=='__main__':unittest.main()
