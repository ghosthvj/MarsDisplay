"""Passive device preparation; every descriptor is synthetic."""
import unittest
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import patch

from mars_display.devices import (
    DeviceInventoryError, DeviceSelectionError, enumerate_devices, select_device,
)
from mars_display.settings import Settings


def port(device="COM4", serial_number="Screen/A%:é", **changes):
    fields = dict(device=device, vid=0x1234, pid=0x00AB,
                  serial_number=serial_number, description="USB display",
                  location="1-2", manufacturer="Maker", product="Panel",
                  interface=None)
    fields.update(changes)
    return SimpleNamespace(**fields)


class DevicesTests(unittest.TestCase):
    def reject(self, inventory, identity, message):
        before = tuple(inventory)
        with self.assertRaises(DeviceSelectionError) as caught:
            select_device(inventory, identity)
        self.assertEqual(str(caught.exception), message)
        self.assertEqual(inventory, before)

    def test_default_backend_is_lazy_passive_and_excludes_links(self):
        with patch("serial.Serial.open", side_effect=AssertionError("open")), \
             patch("serial.Serial.write", side_effect=AssertionError("write")), \
             patch("serial.Serial", side_effect=AssertionError("active access")), \
             patch("serial.tools.list_ports.comports", return_value=[port()]) as backend:
            inventory = enumerate_devices()
            backend.assert_called_once_with(include_links=False)
            self.assertEqual(len(inventory), 1)
            self.assertEqual(inventory[0].device, "COM4")

    def test_usb_filtering_deterministic_frozen_metadata(self):
        records = [port("COM9"), port("COM2", "Other"), port(vid=None),
                   port(pid=None), port(vid=True), port(pid=65536),
                   port(vid=-1), port(device=None), port(device="bad\nport"),
                   SimpleNamespace(), port("COM3", description=None,
                       manufacturer="bad\ntext", product=42, interface="USB interface")]
        inventory = enumerate_devices(lambda: records)
        self.assertIsInstance(inventory, tuple)
        self.assertEqual(inventory, enumerate_devices(lambda: reversed(records)))
        self.assertEqual([item.device for item in inventory], ["COM2", "COM3", "COM9"])
        item = inventory[2]
        self.assertEqual((item.vid, item.pid, item.serial_number, item.description,
                          item.location, item.manufacturer, item.product, item.interface),
                         (0x1234, 0xAB, "Screen/A%:é", "USB display", "1-2", "Maker", "Panel", None))
        self.assertEqual((inventory[1].description, inventory[1].manufacturer,
                          inventory[1].product, inventory[1].interface),
                         (None, None, None, "USB interface"))
        with self.assertRaises(FrozenInstanceError):
            item.device = "COM99"
        records[0].device = "COM99"
        self.assertEqual(item.device, "COM9")

    def test_stable_identity_escaping_case_and_explicit_selection(self):
        inventory = enumerate_devices(lambda: [port(), port("COM5", "screen/A%:é")])
        identity = "usb:1234:00ab:Screen%2FA%25%3A%C3%A9"
        self.assertEqual(inventory[0].identity, identity)
        self.assertNotEqual(inventory[1].identity, identity)
        self.assertIs(select_device(inventory, identity), inventory[0])
        self.assertEqual(Settings("https://mars.example", identity).device_identity, identity)
        self.assertEqual(Settings("https://mars.example", "legacy opaque value").device_identity,
                         "legacy opaque value")

    def test_no_selection_unknown_or_com_identity_never_picks_first(self):
        inventory = enumerate_devices(lambda: [port()])
        for identity in (None, "", "  "):
            with self.subTest(identity=identity):
                self.reject(inventory, identity, "Select an explicit stable USB identity; no device was selected.")
        for identity in ("COM4", "legacy opaque value", "usb:1234:00ab:unknown", 42):
            with self.subTest(identity=identity):
                self.reject(inventory, identity, "Selected USB identity was not found; refresh inventory and select again.")
        self.reject((), inventory[0].identity,
                    "Selected USB identity was not found; refresh inventory and select again.")

    def test_missing_serial_is_unstable_and_duplicates_are_ambiguous(self):
        inventory = enumerate_devices(lambda: [port("COM1", None), port("COM2", ""),
                                               port("COM3", "bad\nserial"), port("COM4", " ")])
        self.assertEqual(tuple(item.identity for item in inventory), (None,) * 4)
        self.reject(inventory, "COM1",
                    "Selected USB identity was not found; refresh inventory and select again.")
        for records in ([port(), port("COM8")], [port(), port()]):
            ambiguous = enumerate_devices(lambda: records)
            self.assertEqual(len(ambiguous), 2)
            self.reject(ambiguous, ambiguous[0].identity,
                        "Selected USB identity is ambiguous; disconnect duplicates or identify the hardware before selecting.")

    def test_identity_follows_usb_serial_not_previous_com_occupant(self):
        old = enumerate_devices(lambda: [port()])
        current = enumerate_devices(lambda: [port("COM4", "unrelated"), port("COM18")])
        self.assertEqual(select_device(current, old[0].identity).device, "COM18")
        self.assertEqual(old[0].device, "COM4")
        old_occupant = tuple(item for item in current if item.device == "COM4")
        self.reject(old_occupant, old[0].identity,
                    "Selected USB identity was not found; refresh inventory and select again.")

    def test_backend_failure_is_sanitized_including_partial_iteration(self):
        def broken():
            yield port()
            raise OSError("private OS descriptor data")
        for provider in (broken, lambda: (_ for _ in ()).throw(OSError("secret"))):
            with self.subTest(provider=provider):
                with self.assertRaises(DeviceInventoryError) as caught:
                    enumerate_devices(provider)
                self.assertEqual(str(caught.exception),
                                 "Cannot list USB serial descriptors; check system device access and retry.")
                self.assertTrue(caught.exception.__suppress_context__)
        self.assertEqual(enumerate_devices(lambda: []), ())


if __name__ == "__main__":
    unittest.main()
