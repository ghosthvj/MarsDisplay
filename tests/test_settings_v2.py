"""P4 public configuration transactions; all files are test-owned."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from mars_display.lifecycle import Coordinator, LifecycleError
from mars_display.settings import Settings, SettingsError, SettingsStore, SettingsStoreError

IDENTITY = 'usb:1a86:5722:USB35INCHIPSV2'
PROFILE = 'tus35-portrait-v1'
URL = 'https://mars.example/prefix'
ACK_ERROR = 'Schema 2 is incompatible with older binaries; explicit acknowledgement is required.'
NATIVE_START_ERROR = 'Native output is configured but is not enabled in this build. Select Simulation explicitly.'


def document(*, mode='simulated', profile=None, identity=None):
    return dict(schema_version=2, mars_url=URL, device_identity=identity,
                output_mode=mode, native_profile=profile)


class SettingsV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root/'settings.json'
        self.store = SettingsStore(self.path)
        self.legacy = b'{ "device_identity" : "legacy-id", "mars_url":"https://mars.example/prefix", "schema_version":1 }\n'

    def seed_legacy(self):
        self.path.write_bytes(self.legacy)

    def native(self):
        return Settings(**document(mode='native', profile=PROFILE, identity=IDENTITY))

    def test_schema2_exact_load_is_passive_and_does_not_rewrite(self):
        for value in (document(), document(mode='native',profile=PROFILE,identity=IDENTITY)):
            with self.subTest(mode=value['output_mode']):
                raw=json.dumps(value, separators=(',',':')).encode()
                self.path.write_bytes(raw)
                with patch('mars_display.devices.enumerate_devices') as inventory, patch('mars_display.usb_process.launch_worker') as launch:
                    loaded=self.store.load()
                self.assertEqual(loaded.schema_version,2)
                self.assertEqual(loaded.output_mode,value['output_mode'])
                self.assertEqual(loaded.native_profile,value['native_profile'])
                inventory.assert_not_called();launch.assert_not_called()
                self.assertEqual(self.path.read_bytes(),raw)
                self.assertEqual(list(self.root.iterdir()),[self.path])

    def test_legacy_identity_stays_simulated_and_save_stays_schema1(self):
        self.seed_legacy();loaded=self.store.load()
        self.assertEqual(loaded.output_mode,'simulated')
        self.assertIsNone(loaded.native_profile)
        self.assertEqual(self.path.read_bytes(),self.legacy)
        self.store.save(loaded)
        self.assertEqual(set(json.loads(self.path.read_bytes())),{'schema_version','mars_url','device_identity'})
        self.assertFalse(self.store.schema1_backup_path.exists())

    def test_invalid_schema2_combinations_preserve_original_without_effects(self):
        invalid=[document(mode='other'),document(mode=True),document(profile=PROFILE),
                 document(mode='native'),document(mode='native',profile=PROFILE),
                 document(mode='native',profile='unknown',identity=IDENTITY),
                 document(mode='native',profile=PROFILE,identity='unknown'),
                 document(profile=False),document()|{'unknown':True}]
        for value in invalid:
            with self.subTest(value=list(value)):
                raw=json.dumps(value).encode();self.path.write_bytes(raw)
                with self.assertRaises(SettingsError):self.store.load()
                self.assertEqual(self.path.read_bytes(),raw)
                self.assertEqual(list(self.root.iterdir()),[self.path])
        raw=b'{"schema_version":2,"mars_url":"https://mars.example","device_identity":null,"output_mode":"simulated","output_mode":"native","native_profile":null}'
        self.path.write_bytes(raw)
        with self.assertRaises(SettingsError):self.store.load()
        self.assertEqual(self.path.read_bytes(),raw)

    def test_unknown_existing_configuration_cannot_be_erased_by_save(self):
        for value in (dict(schema_version=1,mars_url=URL,device_identity=None,private_field='preserve'),
                      document()|{'schema_version':3},document()|{'future_field':True}):
            with self.subTest(version=value['schema_version']):
                raw=json.dumps(value).encode();self.path.write_bytes(raw)
                with self.assertRaises(SettingsError):self.store.save(Settings(URL))
                self.assertEqual(self.path.read_bytes(),raw)
                self.assertEqual(list(self.root.iterdir()),[self.path])

    def test_migration_requires_explicit_ack_and_preserves_exact_legacy(self):
        self.seed_legacy();target=self.native()
        for ack in (False,None,1,'yes'):
            with self.subTest(ack=ack),self.assertRaises(SettingsError) as error:
                self.store.migrate_to_v2(target,acknowledge_legacy_incompatibility=ack)
            self.assertEqual(str(error.exception),ACK_ERROR)
            self.assertEqual(self.path.read_bytes(),self.legacy)
            self.assertEqual(list(self.root.iterdir()),[self.path])
        self.assertIsNone(self.store.migrate_to_v2(target,acknowledge_legacy_incompatibility=True))
        self.assertEqual(self.store.load(),target)
        self.assertEqual(self.store.schema1_backup_path.read_bytes(),self.legacy)
        self.assertEqual(json.loads(self.path.read_bytes()),document(mode='native',profile=PROFILE,identity=IDENTITY))

    def test_plain_save_cannot_migrate_or_downgrade(self):
        self.seed_legacy()
        with self.assertRaises(SettingsError):self.store.save(self.native())
        self.assertEqual(self.path.read_bytes(),self.legacy)
        self.store.migrate_to_v2(self.native(),acknowledge_legacy_incompatibility=True)
        previous=self.path.read_bytes()
        with self.assertRaises(SettingsError):self.store.save(Settings(URL))
        self.assertEqual(self.path.read_bytes(),previous)
        self.assertEqual(self.store.schema1_backup_path.read_bytes(),self.legacy)

    def test_first_run_migration_has_old_readable_backup_and_simulated_edits(self):
        value=Settings(**document())
        self.store.migrate_to_v2(value,acknowledge_legacy_incompatibility=True)
        backup=SettingsStore(self.store.schema1_backup_path).load()
        self.assertEqual(backup,Settings(URL))
        changed=Settings(**(document()|{'mars_url':'https://other.example'}))
        self.store.save(changed)
        self.assertEqual(self.store.load(),changed)
        self.assertEqual(SettingsStore(self.store.schema1_backup_path).load(),Settings(URL))

    def test_export_and_restore_are_explicit_non_overwriting_recovery(self):
        self.seed_legacy();export=self.root/'legacy-export.json'
        self.store.export_schema1(export)
        self.assertEqual(export.read_bytes(),self.legacy)
        self.store.migrate_to_v2(self.native(),acknowledge_legacy_incompatibility=True)
        self.store.restore_schema1()
        self.assertEqual(self.path.read_bytes(),self.legacy)
        self.assertEqual(self.store.load(),Settings(URL,'legacy-id'))
        with self.assertRaises(SettingsStoreError):self.store.export_schema1(export)
        self.assertEqual(export.read_bytes(),self.legacy)
        self.assertEqual(self.path.read_bytes(),self.legacy)

    def test_failed_backup_publish_and_main_replace_preserve_original(self):
        self.seed_legacy();target=self.native()
        with patch('mars_display.settings.os.link',side_effect=OSError('private')):
            with self.assertRaises(SettingsStoreError):
                self.store.migrate_to_v2(target,acknowledge_legacy_incompatibility=True)
        self.assertEqual(self.path.read_bytes(),self.legacy)
        self.assertEqual(list(self.root.iterdir()),[self.path])
        with patch('mars_display.settings.os.replace',side_effect=OSError('private')):
            with self.assertRaises(SettingsStoreError):
                self.store.migrate_to_v2(target,acknowledge_legacy_incompatibility=True)
        self.assertEqual(self.path.read_bytes(),self.legacy)
        self.assertEqual(self.store.schema1_backup_path.read_bytes(),self.legacy)
        self.assertEqual(set(self.root.iterdir()),{self.path,self.store.schema1_backup_path})

    def test_conflicting_backup_and_unknown_restore_never_overwrite(self):
        self.seed_legacy();backup=self.store.schema1_backup_path
        backup.write_bytes(b'foreign backup')
        with self.assertRaises(SettingsStoreError):
            self.store.migrate_to_v2(self.native(),acknowledge_legacy_incompatibility=True)
        self.assertEqual(self.path.read_bytes(),self.legacy)
        self.assertEqual(backup.read_bytes(),b'foreign backup')
        backup.write_bytes(self.legacy)
        raw=json.dumps(document()|{'future':True}).encode();self.path.write_bytes(raw)
        with self.assertRaises(SettingsError):self.store.restore_schema1()
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual(backup.read_bytes(),self.legacy)

    def test_native_profile_requires_exact_string_type(self):
        class LooksLikeProfile:
            def __eq__(self, other):return True
        self.seed_legacy()
        with self.assertRaises(SettingsError):
            Settings(**document(mode='native',profile=LooksLikeProfile(),identity=IDENTITY))
        self.assertEqual(self.path.read_bytes(),self.legacy)
        self.assertEqual(list(self.root.iterdir()),[self.path])

    def test_external_unknown_edit_after_backup_is_not_erased(self):
        self.seed_legacy();target=self.native()
        unknown=json.dumps(document()|{'future_field':'preserve'}).encode()
        import os
        link=os.link
        def concurrent_edit(source,destination):
            link(source,destination)
            self.path.write_bytes(unknown)
        with patch('mars_display.settings.os.link',side_effect=concurrent_edit):
            with self.assertRaises(SettingsError):
                self.store.migrate_to_v2(target,acknowledge_legacy_incompatibility=True)
        self.assertEqual(self.path.read_bytes(),unknown)
        self.assertEqual(self.store.schema1_backup_path.read_bytes(),self.legacy)

    def test_migration_read_failure_is_sanitized_before_backup(self):
        self.seed_legacy();target=self.native()
        with patch('mars_display.settings.Path.read_bytes',side_effect=PermissionError('private path')):
            with self.assertRaises(SettingsStoreError) as error:
                self.store.migrate_to_v2(target,acknowledge_legacy_incompatibility=True)
        self.assertNotIn('private',str(error.exception))
        self.assertEqual(self.path.read_bytes(),self.legacy)
        self.assertEqual(list(self.root.iterdir()),[self.path])

    def test_native_start_rejects_before_resources_or_snapshot_changes(self):
        raw=json.dumps(document(mode='native',profile=PROFILE,identity=IDENTITY)).encode()
        self.path.write_bytes(raw);source,output=Mock(),Mock()
        coordinator=Coordinator(self.store,source,output)
        before=coordinator.snapshot()
        with patch('mars_display.lifecycle.enumerate_devices') as inventory,patch('mars_display.usb_process.launch_worker') as launch:
            with self.assertRaises(LifecycleError) as error:coordinator.start()
        self.assertEqual(str(error.exception),NATIVE_START_ERROR)
        source.assert_not_called();output.assert_not_called();inventory.assert_not_called();launch.assert_not_called()
        self.assertEqual(coordinator.snapshot(),before)
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual(list(self.root.iterdir()),[self.path])


if __name__=='__main__':unittest.main()
