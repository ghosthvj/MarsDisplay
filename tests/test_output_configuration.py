"""P4 stopped transactions and explicit context composition, never native output."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

from mars_display.devices import USBSerialDescriptor
from mars_display.lifecycle import Coordinator, LifecycleError
from mars_display.settings import Settings, SettingsError, SettingsStore
from test_lifecycle import Source, Output, GateWait

IDENTITY='usb:1a86:5722:USB35INCHIPSV2'
PROFILE='tus35-portrait-v1'


def native(url='https://mars.example'):
    return Settings(url,IDENTITY,2,'native',PROFILE)


def device(port='COM5',serial='USB35INCHIPSV2'):
    return USBSerialDescriptor(port,0x1a86,0x5722,serial,None,None,None,None,None)


class OutputConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=SettingsStore(self.root/'settings.json')
        self.initial=Settings('https://mars.example','legacy-id');self.store.save(self.initial)
        self.controllers=[];self.sources=[];self.gates=[]

    def tearDown(self):
        for gate in self.gates:gate.set()
        for source in self.sources:source.release.set()
        for controller in self.controllers:
            controller.stop();self.assertTrue(controller.wait_stopped(2))

    def coordinator(self,**kwargs):
        source=Source(blocked=True);self.sources.append(source)
        controller=Coordinator(self.store,lambda _:source,Output,**kwargs)
        self.controllers.append(controller)
        return controller,source

    def test_context_freezes_one_settings_load_and_same_cancel_event(self):
        allow=Event();entered=Event();made=Event();self.gates.append(allow)
        source=Source();self.sources.append(source);seen=[];contexts=[];wait=GateWait()
        def source_factory(settings):
            seen.append(settings);entered.set()
            if not allow.wait(2):raise AssertionError('source factory not released')
            return source
        def output_factory(context):
            contexts.append(context);made.set();return Output()
        controller=Coordinator(self.store,source_factory,transport_context_factory=output_factory,wait=wait)
        self.controllers.append(controller)
        with patch.object(self.store,'load',wraps=self.store.load) as load:
            self.assertTrue(controller.start());self.assertTrue(entered.wait(1))
            self.store.save(Settings('https://changed.example'))
            allow.set();self.assertTrue(made.wait(1));self.assertTrue(wait.entered.wait(1))
            self.assertEqual(load.call_count,1)
        context=contexts[0]
        self.assertIs(context.settings,seen[0]);self.assertEqual(context.settings,self.initial)
        self.assertFalse(context.cancel.is_set())
        with self.assertRaises(FrozenInstanceError):context.settings=Settings('https://other.example')
        controller.stop();self.assertTrue(context.cancel.is_set())
        self.assertTrue(controller.wait_stopped(2))
        self.assertEqual(controller.snapshot().frames_sent,1)

    def test_context_typeerror_never_retries_with_another_arity(self):
        sizes=[];source=Source();self.sources.append(source)
        def output(*args):sizes.append(len(args));raise TypeError('private')
        def cancel_retry(cancel,seconds):cancel.set();return True
        controller=Coordinator(self.store,lambda _:source,transport_context_factory=output,wait=cancel_retry)
        self.controllers.append(controller);controller.start();self.assertTrue(controller.wait_stopped(2))
        self.assertEqual(sizes,[1]);self.assertEqual(controller.snapshot().frames_sent,0)
        self.assertEqual(controller.snapshot().failures,1)
        self.assertTrue(source.closed.is_set())

    def test_mixed_factory_paths_reject_before_any_resources(self):
        source,old,new=Mock(),Mock(),Mock()
        with self.assertRaises(TypeError) as error:
            Coordinator(self.store,source,old,transport_context_factory=new)
        self.assertEqual(str(error.exception),'Provide exactly one transport factory path.')
        source.assert_not_called();old.assert_not_called();new.assert_not_called()

    def test_native_save_resolves_fresh_identity_not_old_com(self):
        inventory=Mock(return_value=(device(),));controller,_=self.coordinator(inventory_provider=inventory)
        before=controller.snapshot()
        controller.migrate_settings(native(),acknowledge_legacy_incompatibility=True)
        self.assertEqual(inventory.call_count,1);self.assertEqual(controller.snapshot(),before)
        inventory.return_value=(device('COM8'),device('COM5','FOREIGN'))
        controller.save_settings(native('https://changed.example'))
        self.assertEqual(inventory.call_count,2)
        self.assertEqual(self.store.load(),native('https://changed.example'))
        self.assertNotIn('COM',self.store.path.read_text())
        self.assertEqual(controller.snapshot(),before)
        native_bytes=self.store.path.read_bytes();old_reader_export=self.root/'native-export.json'
        controller.export_schema1_settings(old_reader_export)
        self.assertEqual(SettingsStore(old_reader_export).load(),Settings('https://changed.example',IDENTITY))
        self.assertEqual(self.store.path.read_bytes(),native_bytes)
        self.assertEqual(inventory.call_count,2)
        controller.restore_schema1_settings()
        self.assertEqual(self.store.load(),self.initial)
        export=self.root/'export.json';controller.export_schema1_settings(export)
        self.assertEqual(SettingsStore(export).load(),self.initial)
        self.assertEqual(inventory.call_count,2)

    def test_missing_duplicate_unknown_foreign_selection_never_persists(self):
        cases=((),(device(),device('COM8')),(device('COM5','OTHER'),),
               (device(),device('com5','FOREIGN')))
        for observations in cases:
            with self.subTest(count=len(observations)):
                inventory=Mock(return_value=observations);controller,_=self.coordinator(inventory_provider=inventory)
                before=controller.snapshot();raw=self.store.path.read_bytes()
                with self.assertRaises(SettingsError) as error:
                    controller.migrate_settings(native(),acknowledge_legacy_incompatibility=True)
                self.assertEqual(str(error.exception),'Selected native screen is unavailable or ambiguous; refresh selection before saving.')
                self.assertEqual(self.store.path.read_bytes(),raw)
                self.assertFalse(self.store.schema1_backup_path.exists())
                self.assertEqual(controller.snapshot(),before);inventory.assert_called_once()

    def test_legacy_identity_and_unacknowledged_migration_do_not_enumerate(self):
        inventory=Mock();controller,_=self.coordinator(inventory_provider=inventory)
        controller.save_settings(Settings('https://changed.example',IDENTITY))
        self.assertEqual(self.store.load().schema_version,1)
        before=self.store.path.read_bytes()
        with self.assertRaises(SettingsError):controller.migrate_settings(native(),acknowledge_legacy_incompatibility=False)
        inventory.assert_not_called();self.assertEqual(self.store.path.read_bytes(),before)
        self.assertFalse(self.store.schema1_backup_path.exists())

    def test_all_configuration_operations_reject_running_and_stopping(self):
        inventory=Mock();controller,source=self.coordinator(inventory_provider=inventory)
        raw=self.store.path.read_bytes();controller.start();self.assertTrue(source.entered.wait(1))
        operations=(lambda:controller.save_settings(self.initial),
                    lambda:controller.migrate_settings(native(),acknowledge_legacy_incompatibility=True),
                    controller.restore_schema1_settings,
                    lambda:controller.export_schema1_settings(self.root/'blocked-export.json'))
        for stopping in (False,True):
            if stopping:controller.stop()
            for operation in operations:
                with self.subTest(stopping=stopping),self.assertRaises(LifecycleError) as error:operation()
                self.assertEqual(str(error.exception),'Settings can be saved only while stopped.')
                self.assertEqual(self.store.path.read_bytes(),raw)
                self.assertEqual(controller.snapshot().frames_sent,0)
        inventory.assert_not_called();self.assertFalse(self.store.schema1_backup_path.exists())
        self.assertFalse((self.root/'blocked-export.json').exists())

    def test_exit_requested_rejects_configuration_even_without_worker(self):
        inventory=Mock();controller,_=self.coordinator(inventory_provider=inventory)
        raw=self.store.path.read_bytes();controller.request_exit();before=controller.snapshot()
        operations=(lambda:controller.save_settings(self.initial),
                    lambda:controller.migrate_settings(native(),acknowledge_legacy_incompatibility=True),
                    controller.restore_schema1_settings,
                    lambda:controller.export_schema1_settings(self.root/'exit-export.json'))
        for operation in operations:
            with self.assertRaises(LifecycleError):operation()
            self.assertEqual(controller.snapshot(),before)
            self.assertEqual(self.store.path.read_bytes(),raw)
        self.assertTrue(before.exit_ready);inventory.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[self.store.path])

    def test_migration_serializes_start_then_native_admission_rejects(self):
        inventory=Mock(return_value=(device(),));source,output=Mock(),Mock()
        controller=Coordinator(self.store,source,output,inventory_provider=inventory)
        self.controllers.append(controller);entered=Event();allow=Event();done=Event();starting=Event()
        self.gates.append(allow);failures=[];order=[];original=self.store.migrate_to_v2
        def migration(*args,**kwargs):
            entered.set()
            if not allow.wait(2):raise AssertionError('migration not released')
            original(*args,**kwargs);order.append('migrated')
        def save_thread():
            try:controller.migrate_settings(native(),acknowledge_legacy_incompatibility=True)
            except Exception as error:failures.append(error)
        def start_thread():
            starting.set()
            try:controller.start()
            except LifecycleError:order.append('native rejected')
            except Exception as error:failures.append(error)
            finally:done.set()
        with patch.object(self.store,'migrate_to_v2',side_effect=migration):
            a=Thread(target=save_thread);b=Thread(target=start_thread)
            try:
                a.start();self.assertTrue(entered.wait(1));b.start();self.assertTrue(starting.wait(1))
                self.assertFalse(done.wait(0.05));source.assert_not_called();output.assert_not_called()
            finally:
                allow.set();a.join(2)
                if b.ident is not None:b.join(2)
            self.assertFalse(a.is_alive());self.assertFalse(b.is_alive())
        self.assertEqual(failures,[]);self.assertEqual(order,['migrated','native rejected'])
        self.assertEqual(controller.snapshot().frames_sent,0);self.assertFalse(controller.snapshot().worker_alive)
        source.assert_not_called();output.assert_not_called();self.assertEqual(self.store.load(),native())


if __name__=='__main__':unittest.main()
