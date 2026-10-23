"""Brightness persistence transactions use only test-owned temporary files."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mars_display import settings as module
from mars_display.settings import Settings, SettingsError, SettingsStore, SettingsStoreError

URL = 'https://mars.example/prefix'
ACK = 'Schema 3 is incompatible with older binaries; explicit acknowledgement is required.'


class SettingsV3Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = SettingsStore(self.root / 'settings.json')

    def target(self, level=100):
        return Settings(URL, None, 3, 'simulated', None, level)

    def seed(self, version=1):
        value = dict(schema_version=version, mars_url=URL, device_identity=None)
        if version == 2:
            value.update(output_mode='simulated', native_profile=None)
        raw = (json.dumps(value, separators=(', ', ': ')) + '\r\n').encode()
        self.store.path.write_bytes(raw)
        return raw

    def state(self):
        return {p.name: p.read_bytes() for p in self.root.iterdir()}

    def migrate(self, target=None):
        self.store.migrate_to_v3(target or self.target(), acknowledge_legacy_incompatibility=True)

    def test_exact_levels_roundtrip_and_schema3_keys(self):
        self.assertEqual(module.BRIGHTNESS_LEVELS, (20, 40, 60, 80, 100))
        self.migrate()
        for level in module.BRIGHTNESS_LEVELS:
            value = self.target(level)
            self.store.save(value)
            before = self.state()
            self.assertEqual(self.store.load(), value)
            self.assertEqual(self.state(), before)
            self.assertEqual(json.loads(self.store.path.read_bytes()), dict(
                schema_version=3, mars_url=URL, device_identity=None,
                output_mode='simulated', native_profile=None, brightness_percent=level))

    def test_invalid_levels_reject_load_save_and_migration_without_writes(self):
        self.migrate()
        for level in (True, False, 20.0, 100.0, '20', None, 0, 19, 21, 99, 101, [], {}):
            with self.subTest(level=level):
                before = self.state()
                with self.assertRaises(SettingsError):
                    self.store.save(self.target(level))
                self.assertEqual(self.state(), before)
                forged = self.target()
                object.__setattr__(forged, 'brightness_percent', level)
                for operation in (self.store.save, self.migrate):
                    with self.assertRaises(SettingsError):
                        operation(forged)
                    self.assertEqual(self.state(), before)
                data = json.loads(self.store.path.read_bytes())
                data['brightness_percent'] = level
                self.store.path.write_text(json.dumps(data))
                invalid = self.state()
                with self.assertRaises(SettingsError):
                    self.store.load()
                self.assertEqual(self.state(), invalid)
                self.store.path.write_bytes(before[self.store.path.name])

    def test_legacy_defaults_positional_contract_and_exact_serialization(self):
        for version in (1, 2):
            raw = self.seed(version)
            loaded = self.store.load()
            self.assertEqual(loaded.brightness_percent, 100)
            self.assertEqual(self.store.path.read_bytes(), raw)
            self.assertEqual(Settings(URL, None, version, 'simulated', None), loaded)
            if version == 2:
                self.store.schema1_backup_path.write_bytes(json.dumps(dict(
                    schema_version=1, mars_url=URL, device_identity=None)).encode())
            self.store.save(loaded)
            self.assertEqual(set(json.loads(self.store.path.read_bytes())), set(json.loads(raw)))
            before = self.state()
            for level in (20, 40, 60, 80):
                with self.assertRaises(SettingsError):
                    self.store.save(replace(loaded, brightness_percent=level))
                self.assertEqual(self.state(), before)

    def test_explicit_ack_target_and_no_implicit_version_changes(self):
        self.seed()
        for ack in (False, None, 1, 'yes'):
            before = self.state()
            with self.assertRaisesRegex(SettingsError, ACK):
                self.store.migrate_to_v3(self.target(), acknowledge_legacy_incompatibility=ack)
            self.assertEqual(self.state(), before)
        for value in (Settings(URL), Settings(URL, schema_version=2)):
            before = self.state()
            with self.assertRaises(SettingsError):
                self.migrate(value)
            self.assertEqual(self.state(), before)
        with self.assertRaises(SettingsError):
            self.store.save(self.target())
        self.migrate()
        before = self.state()
        for operation in (lambda: self.migrate(), lambda: self.store.save(Settings(URL)),
                          lambda: self.store.save(Settings(URL, schema_version=2))):
            with self.assertRaises(SettingsError):
                operation()
            self.assertEqual(self.state(), before)

    def test_v2_migration_refuses_schema3_without_misreporting_current_version(self):
        self.migrate()
        before = self.state()
        with self.assertRaisesRegex(SettingsError, '^Settings already use schema 3; use explicit Save\\.$'):
            self.store.migrate_to_v2(Settings(URL, schema_version=2),
                                     acknowledge_legacy_incompatibility=True)
        self.assertEqual(self.state(), before)

    def test_exact_original_recovery_from_both_versions(self):
        for version in (1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as root:
                self.store = SettingsStore(Path(root) / 'settings.json')
                original = self.seed(version)
                self.migrate(self.target(40))
                self.assertEqual(self.store.pre_brightness_backup_path.read_bytes(), original)
                self.assertEqual(self.store.schema1_backup_path.exists(), version == 1)
                self.store.save(self.target(60))
                self.store.restore_pre_brightness()
                self.assertEqual(self.store.path.read_bytes(), original)
                self.assertEqual(self.store.pre_brightness_backup_path.read_bytes(), original)

    def test_first_run_recovery_and_existing_schema1_backup_preserved(self):
        self.migrate()
        self.assertEqual(SettingsStore(self.store.pre_brightness_backup_path).load(), Settings(URL))
        self.store.restore_schema1()
        old = self.store.schema1_backup_path.read_bytes()
        self.store.migrate_to_v2(Settings(URL, schema_version=2), acknowledge_legacy_incompatibility=True)
        original = self.store.path.read_bytes()
        # A prior different brightness recovery point must never be overwritten.
        before = self.state()
        with self.assertRaises(SettingsStoreError):
            self.migrate()
        self.assertEqual(self.state(), before)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(self.store.schema1_backup_path.read_bytes(), old)

    def test_schema2_chain_keeps_earlier_schema1_recovery_and_export(self):
        old = self.seed()
        self.store.migrate_to_v2(Settings(URL, schema_version=2), acknowledge_legacy_incompatibility=True)
        v2 = self.store.path.read_bytes()
        self.migrate(self.target(20))
        self.assertEqual(self.store.schema1_backup_path.read_bytes(), old)
        self.assertEqual(self.store.pre_brightness_backup_path.read_bytes(), v2)
        export = self.root / 'export.json'
        self.store.export_schema1(export)
        self.assertEqual(SettingsStore(export).load(), Settings(URL))
        self.assertEqual(set(json.loads(export.read_bytes())), {'schema_version', 'mars_url', 'device_identity'})
        before = self.state()
        with self.assertRaises(SettingsStoreError):
            self.store.export_schema1(export)
        self.assertEqual(self.state(), before)
        self.store.restore_schema1()
        self.assertEqual(self.store.path.read_bytes(), old)

    def test_missing_invalid_conflicting_backups_reject_without_changes(self):
        self.seed()
        backup = self.store.pre_brightness_backup_path
        for raw in (b'bad', b'{}', json.dumps(dict(schema_version=1, mars_url='http://other', device_identity=None)).encode()):
            backup.write_bytes(raw)
            before = self.state()
            with self.assertRaises(SettingsStoreError):
                self.migrate()
            self.assertEqual(self.state(), before)
        backup.write_bytes(self.store.path.read_bytes())
        self.migrate()
        for raw in (b'bad', self.store.path.read_bytes()):
            backup.write_bytes(raw)
            before = self.state()
            for operation in (lambda: self.store.save(self.target(80)), self.store.restore_pre_brightness):
                with self.assertRaises(SettingsStoreError):
                    operation()
                self.assertEqual(self.state(), before)
        with tempfile.TemporaryDirectory() as root:
            store = SettingsStore(Path(root) / 'settings.json')
            store.path.write_bytes(self.store.path.read_bytes())
            before = store.path.read_bytes()
            with self.assertRaises(SettingsStoreError):
                store.save(self.target(80))
            self.assertEqual(store.path.read_bytes(), before)
            self.assertEqual(list(Path(root).iterdir()), [store.path])

    def test_malformed_unknown_current_is_never_repaired(self):
        self.migrate()
        valid = json.loads(self.store.path.read_bytes())
        cases = [b'bad', b'\xff', json.dumps(valid | {'unknown': 1}).encode(),
                 json.dumps({k: v for k, v in valid.items() if k != 'brightness_percent'}).encode(),
                 json.dumps(valid | {'schema_version': 4}).encode(),
                 json.dumps(valid | {'brightness_percent': 0}).encode(),
                 json.dumps(valid | {'output_mode': 'other'}).encode()]
        for raw in cases:
            self.store.path.write_bytes(raw)
            before = self.state()
            for operation in (self.store.load, self.migrate, self.store.restore_pre_brightness,
                              lambda: self.store.save(self.target())):
                with self.assertRaises(SettingsError):
                    operation()
                self.assertEqual(self.state(), before)

    def test_atomic_save_and_migration_failures(self):
        original = self.seed()
        with patch('mars_display.settings.os.link', side_effect=OSError('private')):
            with self.assertRaises(SettingsStoreError):
                self.migrate()
        self.assertEqual(self.state(), {'settings.json': original})
        with patch('mars_display.settings.os.replace', side_effect=OSError('private')):
            with self.assertRaises(SettingsStoreError):
                self.migrate()
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(self.store.pre_brightness_backup_path.read_bytes(), original)
        self.migrate()
        before = self.state()
        for operation in (lambda: self.store.save(self.target(20)), self.store.restore_pre_brightness):
            with patch('mars_display.settings.os.replace', side_effect=OSError('private')):
                with self.assertRaises(SettingsStoreError):
                    operation()
            self.assertEqual(self.state(), before)

    def test_external_edit_before_migration_or_restore_replacement_is_preserved(self):
        original = self.seed()
        link = os.link
        external = b'{"unknown":true}'
        def edit_after_backup(source, destination):
            link(source, destination)
            self.store.path.write_bytes(external)
        with patch('mars_display.settings.os.link', side_effect=edit_after_backup):
            with self.assertRaisesRegex(SettingsError, 'Settings changed during the operation'):
                self.migrate()
        self.assertEqual(self.store.path.read_bytes(), external)
        self.assertEqual(self.store.pre_brightness_backup_path.read_bytes(), original)
        self.store.path.write_bytes(original)
        self.migrate()
        read = Path.read_bytes
        def edit_after_read(path):
            raw = read(path)
            if path == self.store.pre_brightness_backup_path:
                self.store.path.write_bytes(external)
            return raw
        with patch('mars_display.settings.Path.read_bytes', edit_after_read):
            with self.assertRaisesRegex(SettingsError, 'Settings changed during the operation'):
                self.store.restore_pre_brightness()
        self.assertEqual(self.store.path.read_bytes(), external)
        self.assertEqual(self.store.pre_brightness_backup_path.read_bytes(), original)
