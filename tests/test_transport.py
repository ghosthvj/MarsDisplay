"""Public source tests; no browser, GUI, device, or third-party imports."""

from dataclasses import FrozenInstanceError
import unittest

from mars_display import RGBFrame, SimulatedTransport, Transport


class FrameTests(unittest.TestCase):
    def test_nominal_frames_preserve_rgb_and_timestamp(self):
        for width, height in ((320, 480), (480, 320)):
            with self.subTest(geometry=(width, height)):
                rgb = bytes((1, 2, 3)) * (width * height)
                frame = RGBFrame(width, height, rgb, 12.5)
                self.assertEqual((frame.width, frame.height), (width, height))
                self.assertIs(frame.rgb, rgb)
                self.assertEqual(frame.captured_at, 12.5)

    def test_frames_are_immutable(self):
        frame = RGBFrame(320, 480, bytes(320 * 480 * 3), 0.0)
        for field, value in (("width", 480), ("height", 320),
                             ("rgb", b""), ("captured_at", 1.0)):
            with self.subTest(field=field):
                with self.assertRaises(FrozenInstanceError):
                    setattr(frame, field, value)
                self.assertEqual((frame.width, frame.height, frame.captured_at),
                                 (320, 480, 0.0))
                self.assertEqual(frame.rgb, bytes(320 * 480 * 3))
        with self.assertRaises(TypeError):
            frame.rgb[0] = 1

    def test_invalid_frames_leave_transport_unchanged(self):
        transport = SimulatedTransport()
        transport.open()
        original = RGBFrame(320, 480, bytes(320 * 480 * 3), 0.0)
        transport.send(original)
        valid = dict(width=320, height=480, rgb=original.rgb, captured_at=1.0)
        cases = [
            ({"width": True}, TypeError, "width and height must be integers"),
            ({"height": 480.0}, TypeError, "width and height must be integers"),
            ({"width": "320"}, TypeError, "width and height must be integers"),
            ({"width": 0}, ValueError, "geometry must be 320x480 or 480x320"),
            ({"height": -480}, ValueError, "geometry must be 320x480 or 480x320"),
            ({"width": 320, "height": 320}, ValueError,
             "geometry must be 320x480 or 480x320"),
            ({"rgb": bytearray(original.rgb)}, TypeError, "rgb must be bytes"),
            ({"rgb": memoryview(original.rgb)}, TypeError, "rgb must be bytes"),
            ({"rgb": None}, TypeError, "rgb must be bytes"),
            ({"rgb": b""}, ValueError, "rgb length must equal width * height * 3"),
            ({"rgb": original.rgb[:-1]}, ValueError,
             "rgb length must equal width * height * 3"),
            ({"rgb": original.rgb + b"x"}, ValueError,
             "rgb length must equal width * height * 3"),
            ({"captured_at": True}, TypeError, "captured_at must be a number"),
            ({"captured_at": "now"}, TypeError, "captured_at must be a number"),
            *[({"captured_at": value}, ValueError,
               "captured_at must be finite and non-negative")
              for value in (-1, float("nan"), float("inf"), -float("inf"), 10**1000)],
        ]
        for changes, error, message in cases:
            with self.subTest(changes=changes.keys(), error_value=str(changes)[:80]):
                with self.assertRaises(error) as caught:
                    transport.send(RGBFrame(**(valid | changes)))
                self.assertEqual(str(caught.exception), message)
                self.assertIs(transport.latest_frame, original)
                self.assertEqual(transport.accepted_frames, 1)
                self.assertTrue(transport.is_open)
                self.assertEqual(transport.status, "simulated-open")


class TransportTests(unittest.TestCase):
    def assert_state(self, transport, opened, latest, count):
        self.assertEqual(transport.is_open, opened)
        self.assertEqual(transport.status,
                         "simulated-open" if opened else "simulated-closed")
        self.assertIs(transport.latest_frame, latest)
        self.assertEqual(transport.accepted_frames, count)

    def test_lifecycle_and_ordered_bounded_delivery(self):
        transport: Transport = SimulatedTransport()
        self.assert_state(transport, False, None, 0)
        for _ in range(2):
            self.assertIsNone(transport.open())
            self.assert_state(transport, True, None, 0)
        for index in range(1, 5):
            width, height = (320, 480) if index % 2 else (480, 320)
            frame = RGBFrame(width, height, bytes([index]) * (width * height * 3), index)
            self.assertIsNone(transport.send(frame))
            self.assert_state(transport, True, frame, index)
        for _ in range(2):
            self.assertIsNone(transport.close())
            self.assert_state(transport, False, frame, 4)
        transport.open()
        self.assert_state(transport, True, frame, 4)
        transport.send(frame)
        self.assert_state(transport, True, frame, 5)

    def test_closed_writes_never_change_state(self):
        transport = SimulatedTransport()
        frame = RGBFrame(320, 480, bytes(320 * 480 * 3), 0)
        for previously_opened in (False, True):
            if previously_opened:
                transport.open()
                transport.send(frame)
                transport.close()
            for rejected in (frame, None, b"invalid"):
                with self.subTest(previously_opened=previously_opened, rejected=type(rejected)):
                    with self.assertRaises(RuntimeError) as caught:
                        transport.send(rejected)
                    self.assertEqual(str(caught.exception), "simulated transport is closed")
                    self.assert_state(transport, False,
                                      frame if previously_opened else None,
                                      1 if previously_opened else 0)

    def test_open_transport_rejects_non_frames_without_changes(self):
        transport = SimulatedTransport()
        transport.open()
        frame = RGBFrame(320, 480, bytes(320 * 480 * 3), 0)
        for latest, count in ((None, 0), (frame, 1)):
            if latest is not None:
                transport.send(latest)
            for rejected in (None, b"rgb", object()):
                with self.subTest(latest=latest is not None, rejected=type(rejected)):
                    with self.assertRaises(TypeError) as caught:
                        transport.send(rejected)
                    self.assertEqual(str(caught.exception), "frame must be an RGBFrame")
                    self.assert_state(transport, True, latest, count)


if __name__ == "__main__":
    unittest.main()
