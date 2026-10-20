"""Public pure-encoder contract; frozen fixtures are read before encoding."""

import hashlib
from pathlib import Path
import unittest

from mars_display import RGBFrame, SimulatedTransport


class PortraitEncoderTests(unittest.TestCase):
    def setUp(self):
        from mars_display.usb_protocol import encode_portrait
        self.encode = encode_portrait

    def assert_unchanged(self, frame, before):
        for field, value in zip(("width", "height", "rgb", "captured_at"), before):
            self.assertIs(getattr(frame, field), value)

    def test_canonical_exact_packets_order_and_immutable_result(self):
        root = Path(__file__).resolve().parents[1] / "tools/windows-usb-probe"
        rgb = (root / "pattern.rgb888").read_bytes()
        expected = (root / "pattern.rgb565").read_bytes()
        self.assertEqual(hashlib.sha256(rgb).hexdigest(),
                         "19edb4162586afb859c062b82a4c26b54d7329dc3303205628ad61ab1558ef40")
        self.assertEqual(hashlib.sha256(expected).hexdigest(),
                         "8cbbb7e39485e211548a4f3f448ca14eeb9358286e5eadf7079a324fdc97ed1d")
        frame = RGBFrame(320, 480, rgb, 12.5)
        before = (frame.width, frame.height, frame.rgb, frame.captured_at)
        packets = self.encode(frame)
        self.assertIs(type(packets), tuple)
        self.assertEqual(len(packets), 122)
        self.assertTrue(all(type(packet) is bytes for packet in packets))
        self.assertEqual(packets[0], bytes.fromhex("00 00 00 00 00 79 64 01 40 01 E0 00 00 00 00 00"))
        self.assertEqual(packets[1], bytes.fromhex("00 00 04 FD DF C5"))
        self.assertEqual([len(packet) for packet in packets[2:]], [2560] * 120)
        self.assertEqual(sum(map(len, packets)), 307222)
        for index, packet in enumerate(packets[2:]):
            self.assertEqual(packet, expected[index * 2560:(index + 1) * 2560])
        with self.assertRaises(TypeError):
            packets[0] = b""
        with self.assertRaises(TypeError):
            packets[2][0] = 0
        self.assertEqual(self.encode(frame), packets)
        self.assert_unchanged(frame, before)

    def test_primary_colors_and_truncation_boundaries_little_endian(self):
        vectors = [
            ((0, 0, 0), b"\x00\x00"), ((255, 255, 255), b"\xff\xff"),
            ((255, 0, 0), b"\x00\xf8"), ((0, 255, 0), b"\xe0\x07"),
            ((0, 0, 255), b"\x1f\x00"), ((7, 3, 7), b"\x00\x00"),
            ((8, 4, 8), b"\x21\x08"), ((247, 251, 247), b"\xde\xf7"),
            ((248, 252, 248), b"\xff\xff"),
        ]
        rgb = b"".join(bytes(pixel) for pixel, _ in vectors)
        expected = b"".join(word for _, word in vectors)
        frame = RGBFrame(320, 480, rgb + bytes(460800 - len(rgb)), 0)
        before = (frame.width, frame.height, frame.rgb, frame.captured_at)
        self.assertEqual(b"".join(self.encode(frame)[2:]),
                         expected + bytes(307200 - len(expected)))
        self.assert_unchanged(frame, before)

    def test_wrong_type_has_specific_error(self):
        for value in (None, b"rgb", object()):
            with self.subTest(type=type(value)):
                with self.assertRaises(TypeError) as caught:
                    self.encode(value)
                self.assertEqual(str(caught.exception), "frame must be an RGBFrame")

    def test_forged_frames_reuse_shared_validation_before_profile_check(self):
        valid = dict(width=320, height=480, rgb=bytes(460800), captured_at=0)
        cases = [
            ({"width": True}, TypeError, "width and height must be integers"),
            ({"height": 480.0}, TypeError, "width and height must be integers"),
            ({"width": 1}, ValueError, "geometry must be 320x480 or 480x320"),
            ({"rgb": bytearray(460800)}, TypeError, "rgb must be bytes"),
            ({"rgb": b""}, ValueError, "rgb length must equal width * height * 3"),
            ({"captured_at": True}, TypeError, "captured_at must be a number"),
            *[({"captured_at": value}, ValueError,
               "captured_at must be finite and non-negative")
              for value in (-1, float("nan"), float("inf"), 10**1000)],
            ({"width": 480, "height": 320, "rgb": b""}, ValueError,
             "rgb length must equal width * height * 3"),
        ]
        for changes, error, message in cases:
            with self.subTest(fields=tuple(changes), message=message):
                frame = object.__new__(RGBFrame)
                for field, value in (valid | changes).items():
                    object.__setattr__(frame, field, value)
                before = (frame.width, frame.height, frame.rgb, frame.captured_at)
                with self.assertRaises(error) as caught:
                    self.encode(frame)
                self.assertEqual(str(caught.exception), message)
                self.assert_unchanged(frame, before)

    def test_valid_landscape_rejected_without_changing_caller(self):
        frame = RGBFrame(480, 320, bytes(460800), 0)
        before = (frame.width, frame.height, frame.rgb, frame.captured_at)
        with self.assertRaises(ValueError) as caught:
            self.encode(frame)
        self.assertEqual(str(caught.exception), "portrait encoding requires 320x480 geometry")
        self.assert_unchanged(frame, before)

    def test_simulation_still_accepts_both_geometries_after_encoder_import(self):
        transport = SimulatedTransport()
        transport.open()
        for count, geometry in enumerate(((320, 480), (480, 320)), 1):
            frame = RGBFrame(*geometry, bytes(460800), 0)
            transport.send(frame)
            self.assertIs(transport.latest_frame, frame)
            self.assertEqual(transport.accepted_frames, count)
        transport.close()


if __name__ == "__main__":
    unittest.main()
