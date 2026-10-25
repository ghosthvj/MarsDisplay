"""Native orientation follows frames; all serial ports and settings are isolated."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from mars_display import usb_ipc as ipc, usb_protocol as protocol, usb_worker as worker
from mars_display.frames import RGBFrame
from mars_display.lifecycle import Coordinator, SourceSample
from mars_display.settings import NATIVE_IDENTITY, NATIVE_PROFILE, Settings, SettingsStore
from test_lifecycle import GateWait, Source
import test_usb_transport as transport
import test_usb_worker as session

LANDSCAPE = RGBFrame(480, 320, session.FRAME.rgb, 2)
ORIENTATION = bytes.fromhex('00 00 00 00 00 79 66 01 E0 01 40 00 00 00 00 00')
HEADER = bytes.fromhex('00 00 07 7D 3F C5')


class NativeLandscapeTests(unittest.TestCase):
    start = session.WorkerTests.start
    request = session.WorkerTests.request

    def test_encoder_exact_landscape_corners_row_order_and_immutable_input(self):
        rgb, expected = bytearray(460800), bytearray(307200)
        for x, y, color, word in ((0, 0, b'\xff\x00\x00', b'\x00\xf8'),
                (479, 0, b'\x00\xff\x00', b'\xe0\x07'),
                (0, 319, b'\x00\x00\xff', b'\x1f\x00'),
                (479, 319, b'\xff\xff\x00', b'\xe0\xff'),
                (1, 1, b'\x08\x04\x08', b'\x21\x08')):
            pixel = y * 480 + x
            rgb[pixel*3:pixel*3+3] = color
            expected[pixel*2:pixel*2+2] = word
        frame = RGBFrame(480, 320, bytes(rgb), 12.5)
        before = (frame.width, frame.height, frame.rgb, frame.captured_at)
        packets = protocol.encode_native(frame)
        self.assertIs(type(packets), tuple)
        self.assertTrue(all(type(packet) is bytes for packet in packets))
        self.assertEqual(packets[:2], (ORIENTATION, HEADER))
        self.assertEqual([len(p) for p in packets[2:]], [3840]*80)
        self.assertEqual(sum(map(len, packets)), 307222)
        self.assertEqual(b''.join(packets[2:]), bytes(expected))
        self.assertEqual((frame.width, frame.height, frame.rgb, frame.captured_at), before)
        self.assertEqual(protocol.encode_native(session.FRAME), protocol.encode_portrait(session.FRAME))

    def test_landscape_rgb_ramp_matches_independent_row_major_reference(self):
        import struct

        rgb = bytes(range(256)) * 1800
        frame = RGBFrame(480, 320, rgb, 0)
        packets = protocol.encode_native(frame)
        expected = b''.join(
            struct.pack('<H', (r // 8) * 2048 + (g // 4) * 32 + b // 8)
            for r, g, b in zip(rgb[::3], rgb[1::3], rgb[2::3])
        )
        self.assertEqual(packets[:2], (ORIENTATION, HEADER))
        self.assertEqual(list(map(len, packets[2:])), [3840] * 80)
        self.assertEqual(b''.join(packets[2:]), expected)
        with self.assertRaisesRegex(
                ValueError, '^portrait encoding requires 320x480 geometry$'):
            protocol.encode_portrait(frame)

    def test_native_encoder_revalidates_forged_frames(self):
        for field, value in (('width', True), ('width', 640), ('rgb', b''),
                             ('rgb', bytearray(460800)), ('captured_at', float('nan'))):
            with self.subTest(field=field):
                frame = RGBFrame(480, 320, LANDSCAPE.rgb, 2)
                object.__setattr__(frame, field, value)
                with self.assertRaises((TypeError, ValueError)):
                    protocol.encode_native(frame)
                self.assertIs(getattr(frame, field), value)
        with self.assertRaisesRegex(TypeError, '^frame must be an RGBFrame$'):
            protocol.encode_native(None)

    def test_codec_roundtrips_both_orientations_without_changing_wire_shape(self):
        for frame in (session.FRAME, LANDSCAPE):
            with self.subTest(geometry=(frame.width, frame.height)):
                body = ipc.encode_frame(frame)
                self.assertEqual(body, ipc.METADATA.pack(frame.width, frame.height, frame.captured_at)+frame.rgb)
                self.assertEqual(len(body), 460812)
                self.assertEqual(ipc.decode_frame(body), frame)

    def test_all_worker_frame_kinds_switch_orientation_in_one_owned_session(self):
        frames = (LANDSCAPE, LANDSCAPE, session.FRAME, LANDSCAPE)
        for kind, reply_kind in ((ipc.FRAME, ipc.REPLY),
                (ipc.TIMED_FRAME, ipc.TIMED_REPLY), (ipc.GROUPED_FRAME, ipc.GROUPED_REPLY)):
            with self.subTest(kind=kind):
                c, port, _, results, thread = self.start()
                self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
                for seq, frame in enumerate(frames, 2):
                    body = ipc.METADATA.pack(frame.width, frame.height, frame.captured_at)+frame.rgb
                    ipc.send_packet(c, kind, seq, body, time.monotonic()+1)
                    response, request, reply = ipc.receive_packet(c, time.monotonic()+1)
                    self.assertEqual((response, request, reply[0]), (reply_kind, seq, worker.OK))
                    if kind == ipc.TIMED_FRAME:
                        self.assertIsNone(ipc.decode_timing(reply).groups)
                    elif kind == ipc.GROUPED_FRAME:
                        self.assertIsNotNone(ipc.decode_grouped_timing(reply).groups)
                self.assertEqual(self.request(c, ipc.CLOSE, 6), worker.OK)
                thread.join(1)
                self.assertEqual(results, [0])
                self.assertEqual((port.opens, port.closes), (1, 1))
                self.assertEqual(tuple(port.writes), sum((protocol.encode_native(f) for f in frames), ()))

    def test_landscape_failed_packet_closes_without_resend_or_success_timing(self):
        for position in (1, 2, 3, 82):
            with self.subTest(position=position):
                original = session.Port.write
                def short_write(port, data):
                    size = original(port, data)
                    return size-1 if len(port.writes) == position else size
                with patch.object(session.Port, 'write', short_write):
                    c, port, _, results, thread = self.start()
                    self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
                    body = ipc.METADATA.pack(480, 320, 2)+LANDSCAPE.rgb
                    self.assertEqual(self.request(c, ipc.GROUPED_FRAME, 2, body), worker.WRITE_ERROR)
                    thread.join(1)
                self.assertEqual((results, port.opens, port.closes, len(port.writes)), ([1], 1, 1, position))

    def test_legacy_saved_profiles_follow_frames_without_rewriting_settings(self):
        for version in (2, 3):
            with self.subTest(schema=version), tempfile.TemporaryDirectory() as directory:
                store = SettingsStore(Path(directory)/'settings.json')
                settings = Settings('https://mars.example', NATIVE_IDENTITY, version,
                                    'native', NATIVE_PROFILE, 60 if version == 3 else 100)
                migrate = store.migrate_to_v2 if version == 2 else store.migrate_to_v3
                migrate(settings, acknowledge_legacy_incompatibility=True)
                before = store.path.read_bytes()
                files_before = {p.name: p.read_bytes() for p in Path(directory).iterdir()}
                frames = iter((LANDSCAPE, LANDSCAPE, session.FRAME, LANDSCAPE))
                class SequenceSource(Source):
                    def read(self):
                        return SourceSample('ready', next(frames), True, False)
                source, wait, outputs, children = SequenceSource(), GateWait(), [], []
                waits = []
                def cadence(cancel, seconds):
                    waits.append(seconds)
                    return wait(cancel, seconds) if len(waits) == 4 else False
                def factory(context):
                    output, created, _ = transport.TransportTests.make(self, cancel=context.cancel)
                    outputs.append(output)
                    children.append(created)
                    return output
                controller = Coordinator(store, lambda _: source, transport_context_factory=factory, wait=cadence)
                try:
                    controller.start()
                    self.assertTrue(wait.entered.wait(2), controller.snapshot())
                finally:
                    controller.stop()
                    self.assertTrue(controller.wait_stopped(2))
                state = controller.snapshot()
                self.assertEqual((state.state, state.frames_sent, state.failures, state.retries), ('stopped', 4, 0, 0))
                self.assertIs(state.latest_frame, LANDSCAPE)
                self.assertEqual(state.native_timing.host_send.count, 4)
                self.assertFalse(state.delivery_uncertain or state.ownership_uncertain)
                self.assertEqual((store.load(), store.path.read_bytes()), (settings, before))
                self.assertEqual({p.name: p.read_bytes() for p in Path(directory).iterdir()}, files_before)
                self.assertEqual(len(children), 1)
                self.assertEqual(len(children[0]), 1)
                port = children[0][0].port
                expected = [protocol.encode_brightness(60)] if version == 3 else []
                for frame in (LANDSCAPE, LANDSCAPE, session.FRAME, LANDSCAPE):
                    expected.extend(protocol.encode_native(frame))
                self.assertEqual(port.writes, expected)
                self.assertEqual((port.opens, port.closes), (1, 1))
                self.assertFalse(outputs[0].owned or children[0][0].thread.is_alive())
                self.assertTrue(source.closed.is_set())
