"""Linux path preparation only; all filesystem state is test-owned."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mars_display.settings import Settings, SettingsStore, SettingsStoreError


class LinuxPathsTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def resolve(self, environment):
        # Import here so every rule gets its own RED before the helper exists.
        from mars_display.linux_paths import linux_settings_path
        with patch.object(os, "environ", environment):
            return linux_settings_path()

    def test_absolute_xdg_wins_without_requiring_home(self):
        for name in ("config", "config with spaces", "configuración"):
            for home in (None, "", "relative-private-home"):
                with self.subTest(name=name, home=home):
                    base = self.root / name
                    environment = {"XDG_CONFIG_HOME": str(base)}
                    if home is not None:
                        environment["HOME"] = home
                    self.assertEqual(self.resolve(environment), base / "MarsDisplay" / "settings.json")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unset_empty_relative_xdg_falls_back_to_absolute_home(self):
        for xdg in (None, "", "relative-private-config"):
            with self.subTest(xdg=xdg):
                environment = {"HOME": str(self.root / "home")}
                if xdg is not None:
                    environment["XDG_CONFIG_HOME"] = xdg
                self.assertEqual(self.resolve(environment),
                                 self.root / "home" / ".config" / "MarsDisplay" / "settings.json")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_home_fails_with_sanitized_error_without_writes(self):
        for home in (None, "", "relative-private-home", "/private\x00home", "/private\ud800home"):
            with self.subTest(case=repr(home)):
                environment = {"LOCALAPPDATA": str(self.root / "windows")}
                if home is not None:
                    environment["HOME"] = home
                with self.assertRaises(SettingsStoreError) as caught:
                    self.resolve(environment)
                self.assertEqual(str(caught.exception),
                                 "HOME is unavailable; provide an explicit settings path.")
                self.assertIsNone(caught.exception.__cause__)
                self.assertTrue(caught.exception.__suppress_context__)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_unusable_absolute_xdg_fails_without_disclosing_value(self):
        with self.assertRaises(SettingsStoreError) as caught:
            self.resolve({"XDG_CONFIG_HOME": str(self.root / "private\x00config"),
                          "HOME": str(self.root)})
        self.assertEqual(str(caught.exception),
                         "XDG_CONFIG_HOME is unavailable; provide an explicit settings path.")
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_localappdata_does_not_affect_either_linux_location(self):
        for local in (None, "", str(self.root / "windows")):
            for xdg in (None, str(self.root / "xdg")):
                with self.subTest(local=local, xdg=xdg):
                    environment = {"HOME": str(self.root / "home")}
                    if local is not None:
                        environment["LOCALAPPDATA"] = local
                    if xdg is not None:
                        environment["XDG_CONFIG_HOME"] = xdg
                    base = Path(xdg) if xdg else self.root / "home" / ".config"
                    self.assertEqual(self.resolve(environment), base / "MarsDisplay" / "settings.json")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_resolution_and_store_construction_are_passive(self):
        for environment in ({"HOME": str(self.root / "home")},
                            {"XDG_CONFIG_HOME": str(self.root / "xdg")}):
            path = self.resolve(environment)
            store = SettingsStore(path)
            self.assertEqual(store.path, path)
            self.assertIsNone(store.load())
            self.assertEqual(list(self.root.iterdir()), [])

    def test_resolved_store_roundtrip_and_adjacent_backups(self):
        for variable in ("HOME", "XDG_CONFIG_HOME"):
            with self.subTest(variable=variable):
                store = SettingsStore(self.resolve({variable: str(self.root / variable)}))
                original = Settings("https://mars.example/prefix", "panel-é")
                self.assertIsNone(store.save(original))
                self.assertEqual(store.load(), original)
                raw = store.path.read_bytes()
                v2 = Settings(original.mars_url, original.device_identity, 2)
                store.migrate_to_v2(v2, acknowledge_legacy_incompatibility=True)
                self.assertEqual(store.load(), v2)
                self.assertEqual(store.schema1_backup_path,
                                 store.path.with_name("settings.json.schema1-backup.json"))
                self.assertEqual(store.schema1_backup_path.read_bytes(), raw)
                self.assertEqual(SettingsStore(store.schema1_backup_path).load(), original)
                v2_raw = store.path.read_bytes()
                v3 = Settings(original.mars_url, original.device_identity, 3,
                              brightness_percent=40)
                store.migrate_to_v3(v3, acknowledge_legacy_incompatibility=True)
                self.assertEqual(store.load(), v3)
                self.assertEqual(store.pre_brightness_backup_path,
                                 store.path.with_name("settings.json.pre-brightness-backup.json"))
                self.assertEqual(store.pre_brightness_backup_path.read_bytes(), v2_raw)
                self.assertEqual(SettingsStore(store.pre_brightness_backup_path).load(), v2)
                store.restore_pre_brightness()
                self.assertEqual(store.load(), v2)
                store.restore_schema1()
                self.assertEqual(store.load(), original)
                self.assertEqual(store.path.read_bytes(), raw)
                self.assertEqual(set(store.path.parent.iterdir()),
                                 {store.path, store.schema1_backup_path, store.pre_brightness_backup_path})


if __name__ == "__main__":
    unittest.main()
