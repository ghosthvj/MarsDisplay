"""Validate the public native diagnostic's canonical image, never a USB device."""
import hashlib
import json
from pathlib import Path
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tools/windows-usb-probe"


class NativeProbeFixtureTests(unittest.TestCase):
    def test_frozen_image_and_payload_match_manifest(self):
        manifest = json.loads((FIXTURE / "pattern.json").read_text())
        payload = (FIXTURE / "pattern.rgb565").read_bytes()
        png = (FIXTURE / "pattern.png").read_bytes()
        self.assertEqual(len(payload), 307200)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest["payload_sha256"])
        self.assertEqual(hashlib.sha256(png).hexdigest(), manifest["png_sha256"])
        with Image.open(FIXTURE / "pattern.png") as image:
            self.assertEqual(image.size, (320, 480))
            pixels = list(image.convert("RGB").get_flattened_data())
        expected = bytearray()
        for r, g, b in pixels:
            value = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            expected.extend((value & 255, value >> 8))
        self.assertEqual(payload, bytes(expected))
        self.assertTrue({(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0), (255, 255, 255)} <= set(pixels))
        self.assertEqual(manifest["wire_bytes"], 307222)
        self.assertEqual(manifest["orientation_hex"], "00000000007964014001e00000000000")
        self.assertEqual(manifest["header_hex"], "000004fddfc5")
        self.assertEqual(manifest["payload_chunk_bytes"], 2560)
        self.assertIn("not byte-identical", manifest["limitations"])

    def test_frozen_rgb888_matches_the_canonical_png(self):
        raw = (FIXTURE / "pattern.rgb888").read_bytes()
        manifest = json.loads((FIXTURE / "rgb888-provenance.json").read_text())
        with Image.open(FIXTURE / "pattern.png") as image:
            self.assertEqual(raw, image.convert("RGB").tobytes())
        self.assertEqual(len(raw), 320 * 480 * 3)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest["rgb888_sha256"])
        self.assertEqual(manifest["png_sha256"], "d8efdd4339e8c16a8f2b7e1416ec83221403cf6bdc6571ee5ff146113f00cfbc")
        self.assertEqual(manifest["source_ref"], "0b92565c10996276af5b9ad61a7c85bfc26df327")


if __name__ == "__main__":
    unittest.main()
