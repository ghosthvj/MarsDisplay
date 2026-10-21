"""Settings tests use isolated system-temp roots, never real user configuration."""

from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mars_display.settings import Settings, SettingsError, SettingsStore, SettingsStoreError


URL_ERROR = "MARS URL must be HTTP(S) with a valid host and port, without credentials, query, fragment, whitespace or control characters."
VERSION_ERROR = "Unsupported settings schema version; supported versions are 1 and 2."
SCHEMA_ERROR = "Settings must contain exactly schema_version, mars_url and device_identity."
LOAD_ERROR = "Cannot read settings; check file access and retry."
CORRUPT_ERROR = "Settings file is not valid JSON; correct it or explicitly save new settings."
SAVE_ERROR = "Cannot save settings; check directory access and retry. Previous settings were not replaced."


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir=tempfile.gettempdir())
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.path = self.root / "config" / "settings.json"
        self.store = SettingsStore(self.path)
        self.original = Settings("https://mars.example/prefix", "passive-device-id")

    def assert_error(self, error, message, operation):
        with self.assertRaises(error) as caught:
            operation()
        self.assertEqual(str(caught.exception), message)
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_first_run_and_windows_default_location_do_not_write(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.root)}, clear=True):
            default = SettingsStore()
            self.assertEqual(default.path, self.root / "MarsDisplay" / "settings.json")
            self.assertIsNone(default.load())
            self.assertFalse(default.path.parent.exists())
        self.assertIsNone(self.store.load())
        self.assertFalse(self.path.parent.exists())
        with patch.dict(os.environ, {}, clear=True):
            self.assert_error(SettingsStoreError,
                              "LOCALAPPDATA is unavailable; provide an explicit settings path.",
                              SettingsStore)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_valid_roundtrip_is_versioned_immutable_and_has_no_extra_options(self):
        for device in (None, "passive-device-id"):
            settings = Settings("https://mars.example/prefix", device)
            self.assertIsNone(self.store.save(settings))
            self.assertEqual(self.store.load(), settings)
            self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {
                "schema_version": 1, "mars_url": settings.mars_url,
                "device_identity": device,
            })
            for field, value in (("mars_url", "http://other"),
                                 ("device_identity", "other"), ("schema_version", 2)):
                with self.assertRaises(FrozenInstanceError):
                    setattr(settings, field, value)
                self.assertEqual(self.store.load(), settings)
            self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_base_prefix_and_complete_display_capture_urls(self):
        cases = {
            "http://localhost:8080": "http://localhost:8080/display",
            "https://mars.example/": "https://mars.example/display",
            "HTTPS://MARS.EXAMPLE/proxy/mars/": "https://mars.example/proxy/mars/display",
            "http://192.168.1.2:8000/proxy": "http://192.168.1.2:8000/proxy/display",
            "http://[::1]:8080/display": "http://[::1]:8080/display",
            "https://mars.example/prefix/display/": "https://mars.example/prefix/display",
            "https://mars.example/display": "https://mars.example/display",
            "https://mars.example/display-name": "https://mars.example/display-name/display",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                settings = Settings(url)
                self.assertEqual(settings.capture_url, expected)
                self.store.save(settings)
                self.assertEqual(self.store.load(), settings)
                self.assertEqual(self.store.load().capture_url, expected)

    def test_invalid_model_values_preserve_file_and_previous_settings(self):
        self.store.save(self.original)
        previous = self.path.read_bytes()
        cases = [
            ({"schema_version": True}, VERSION_ERROR),
            ({"schema_version": 1.0}, VERSION_ERROR),
            ({"schema_version": "1"}, VERSION_ERROR),
            ({"schema_version": 0}, VERSION_ERROR),
            ({"schema_version": 3}, VERSION_ERROR),
            *[({"device_identity": value},
               "Device identity must be null or a non-empty string without control characters.")
              for value in (False, 1, [], {}, "", "  ", "usb\nsecret", "usb\x7f", "usb\x85")],
        ]
        for changes, message in cases:
            with self.subTest(changes=changes):
                self.assert_error(SettingsError, message,
                                  lambda: self.store.save(Settings(**({
                                      "mars_url": self.original.mars_url,
                                  } | changes))))
                self.assertEqual(self.path.read_bytes(), previous)
                self.assertEqual(self.store.load(), self.original)
        self.assert_error(SettingsError, "Only validated Settings can be saved.",
                          lambda: self.store.save({"mars_url": "http://other"}))
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(self.store.load(), self.original)

    def test_url_rejection_preserves_bytes_and_settings(self):
        self.store.save(self.original)
        previous = self.path.read_bytes()
        invalid = [None, 1, True, [], "", "mars.example", "//mars.example",
                   "file:///display", "ftp://mars.example", "http:///display",
                   "http://user:private@mars.example", "https://user@mars.example",
                   "https://mars.example?token=private", "https://mars.example?",
                   "https://mars.example/#private", "https://mars.example/#",
                   "http://mars.example:bad", "http://mars.example:65536",
                   "http://mars.example:-1", "http://mars.example:",
                   "http://[::1", "http://bad host", "http://mars.example/space here",
                   " https://mars.example", "https://mars.example/\nprivate",
                   "https://mars.example/\x00", "https://mars.example/\x7f",
                   "https://mars.example/\x85", "https://mars.example/%0aprivate",
                   "https://mars.example/%7f", "http://mars.example\\@evil.example",
                   "http://bad_host", "http://-bad.example", "https://mars.example/%zz"]
        for url in invalid:
            with self.subTest(case=invalid.index(url)):
                self.assert_error(SettingsError, URL_ERROR,
                                  lambda: self.store.save(Settings(url)))
                self.assertEqual(self.path.read_bytes(), previous)
                self.assertEqual(self.store.load(), self.original)
                self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_malformed_schema_and_version_loads_are_non_destructive(self):
        self.path.parent.mkdir()
        valid = {"schema_version": 1, "mars_url": "http://mars.example", "device_identity": None}
        cases = [(b"{private", CORRUPT_ERROR), (b"\xff", CORRUPT_ERROR),
                 (b'{"schema_version":1,"schema_version":1,"mars_url":"http://mars.example","device_identity":null}', SCHEMA_ERROR)]
        for value in (None, [], "private", {}, valid | {"extra": True},
                      {key: item for key, item in valid.items() if key != "device_identity"}):
            cases.append((json.dumps(value).encode(), SCHEMA_ERROR))
        for version in (3, 0, True, 1.0, "1", None):
            cases.append((json.dumps(valid | {"schema_version": version}).encode(), VERSION_ERROR))
        cases.extend([
            (json.dumps(valid | {"mars_url": "http://user:private@host"}).encode(), URL_ERROR),
            (json.dumps(valid | {"device_identity": 42}).encode(),
             "Device identity must be null or a non-empty string without control characters."),
        ])
        for raw, message in cases:
            with self.subTest(message=message, case=cases.index((raw, message))):
                self.path.write_bytes(raw)
                self.assert_error(SettingsError, message, self.store.load)
                self.assertEqual(self.path.read_bytes(), raw)
                self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        # Repair requires an explicit save, never load or construction.
        self.store.save(self.original)
        self.assertEqual(self.store.load(), self.original)

    def test_failed_replacement_is_atomic_and_cleans_temporary_file(self):
        self.store.save(self.original)
        previous = self.path.read_bytes()
        replacement = Settings("http://other.example/display")

        def fail_replace(source, destination):
            self.assertEqual(Path(source).parent, self.path.parent)
            self.assertEqual(Path(destination), self.path)
            self.assertNotEqual(Path(source), self.path)
            self.assertEqual(self.path.read_bytes(), previous)
            self.assertEqual(json.loads(Path(source).read_text())["mars_url"], replacement.mars_url)
            raise OSError("private path details")

        with patch("mars_display.settings.os.replace", side_effect=fail_replace) as replace:
            self.assert_error(SettingsStoreError, SAVE_ERROR,
                              lambda: self.store.save(replacement))
            self.assertEqual(replace.call_count, 1)
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(self.store.load(), self.original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_read_and_temporary_write_failures_are_actionable_and_preserve_data(self):
        self.store.save(self.original)
        previous = self.path.read_bytes()
        with patch("mars_display.settings.Path.read_text", side_effect=PermissionError("private")):
            self.assert_error(SettingsStoreError, LOAD_ERROR, self.store.load)
        with patch("mars_display.settings.os.fsync", side_effect=OSError("private")):
            self.assert_error(SettingsStoreError, SAVE_ERROR,
                              lambda: self.store.save(Settings("http://other.example")))
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(self.store.load(), self.original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])


if __name__ == "__main__":
    unittest.main()
