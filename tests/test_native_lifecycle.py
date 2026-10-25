"""P5 public lifecycle rules with fake outputs and real private IPC peers."""
import gc
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch
import weakref

from mars_display import app as application, usb_ipc as ipc
from mars_display.frames import RGBFrame
from mars_display.lifecycle import Coordinator, LifecycleError, SourceSample, StartContext
from mars_display.settings import Settings, SettingsStore
from mars_display.usb_transport import UsbError
from test_lifecycle import Source, GateWait
import test_usb_transport as transport_fixture

IDENTITY = 'usb:1a86:5722:USB35INCHIPSV2'
PROFILE = 'tus35-portrait-v1'
FIRST = RGBFrame(320,480,bytes(460800),1)
SECOND = RGBFrame(320,480,b'\xff'*460800,2)


class NativeOutput:
    def __init__(self, *, fail_open=False, fail_second=False, hold=False):
        self.owned = False
        self.fail_open, self.fail_second = fail_open, fail_second
        self.entered, self.release = Event(), Event()
        self.close_entered, self.close_release = Event(), Event()
        if not hold:
            self.release.set(); self.close_release.set()
        self.sends, self.accepted, self.closes = 0, [], 0

    def open(self):
        if self.fail_open:
            raise UsbError('startup')
        self.owned = True

    def send(self, frame):
        self.sends += 1; self.entered.set()
        if not self.release.wait(2):
            raise AssertionError('test send not released')
        if self.fail_second and self.sends == 2:
            raise UsbError('frame',delivery_uncertain=True)
        self.accepted.append(frame)

    def close(self):
        self.closes += 1; self.close_entered.set()
        if not self.close_release.wait(2):
            raise AssertionError('test close not released')
        self.owned = False


class NativeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = SettingsStore(Path(self.temp.name)/'settings.json')
        self.store.save(Settings('https://mars.example'))
        self.native = Settings('https://mars.example',IDENTITY,2,'native',PROFILE)
        self.store.migrate_to_v2(self.native,acknowledge_legacy_incompatibility=True)
        self.controllers, self.outputs, self.sources = [], [], []

    def tearDown(self):
        for output in self.outputs:
            output.release.set(); output.close_release.set()
        for source in self.sources: source.release.set()
        for controller in self.controllers:
            controller.stop(); self.assertTrue(controller.wait_stopped(2))

    def make(self, output, *, source=None, wait=None):
        self.outputs.append(output)
        source = source or Source(sample=SourceSample('ready',FIRST,True,False))
        self.sources.append(source); contexts=[]
        def factory(context):
            contexts.append(context); return output
        controller = Coordinator(self.store,lambda _:source,
            transport_context_factory=factory,wait=wait or GateWait())
        self.controllers.append(controller)
        return controller,contexts

    def test_composition_is_explicit_and_constructors_are_passive(self):
        cancel=Event();native=Mock();simulated=Mock()
        with patch.object(application,'UsbTransport',return_value=native,create=True) as usb, patch.object(application,'SimulatedTransport',return_value=simulated) as sim:
            self.assertIs(application.compose_transport(StartContext(self.native,cancel)),native)
            usb.assert_called_once_with(IDENTITY,cancel=cancel);sim.assert_not_called()
            self.assertIs(application.compose_transport(StartContext(Settings('https://mars.example',IDENTITY),cancel)),simulated)
            sim.assert_called_once_with();self.assertEqual(usb.call_count,1)

    def test_usb_error_has_structured_phase_not_message_parsing(self):
        error=UsbError('frame',delivery_uncertain=True)
        self.assertEqual(error.phase,'frame')
        self.assertTrue(error.delivery_uncertain);self.assertFalse(error.ownership_uncertain)

    def test_native_requires_context_factory_and_never_legacy_fallback(self):
        source,output=Mock(),Mock();controller=Coordinator(self.store,source,output)
        before=controller.snapshot();raw=self.store.path.read_bytes()
        with self.assertRaises(LifecycleError) as error:controller.start()
        self.assertEqual(str(error.exception),'Native output requires an explicit Start-context factory; no fallback was started.')
        source.assert_not_called();output.assert_not_called()
        self.assertEqual(controller.snapshot(),before);self.assertEqual(self.store.path.read_bytes(),raw)

    def test_only_confirmed_host_send_advances_frame_and_stop_ack_is_final(self):
        output=NativeOutput(hold=True);wait=GateWait();controller,_=self.make(output,wait=wait)
        controller.start();self.assertTrue(output.entered.wait(1))
        pending=controller.snapshot()
        self.assertEqual(pending.output_mode,'native');self.assertEqual(pending.frames_sent,0)
        self.assertIsNone(pending.latest_frame);self.assertEqual(pending.output_state,'native-open')
        returned=Event();stopper=Thread(target=lambda:(controller.stop(),returned.set()))
        stopper.start()
        try:self.assertTrue(returned.wait(0.1))
        finally:stopper.join(1)
        self.assertTrue(controller.snapshot().worker_alive)
        output.release.set();self.assertTrue(output.close_entered.wait(1))
        before_ack=controller.snapshot()
        self.assertEqual(before_ack.frames_sent,1);self.assertIs(before_ack.latest_frame,FIRST)
        self.assertEqual(before_ack.native_timing.source_read.count,1)
        self.assertEqual(before_ack.native_timing.host_send.count,1)
        self.assertEqual(before_ack.native_timing.cadence_wait.count,0)
        self.assertEqual(before_ack.state,'stopping')
        controller.request_exit();self.assertFalse(controller.snapshot().exit_ready)
        output.close_release.set();self.assertTrue(controller.wait_stopped(2))
        final=controller.snapshot()
        self.assertEqual((final.state,final.output_state,final.frames_sent),('stopped','native-closed',1))
        self.assertTrue(final.exit_ready);self.assertFalse(final.ownership_uncertain)
        controller.stop();self.assertEqual(controller.snapshot().frames_sent,1)
        self.assertEqual((output.sends,len(output.accepted),output.closes),(1,1,1))

    def test_native_prewrite_failure_has_zero_automatic_retries(self):
        output=NativeOutput(fail_open=True);wait=Mock()
        controller,contexts=self.make(output,wait=wait)
        controller.start();self.assertTrue(controller.wait_stopped(2))
        state=controller.snapshot()
        self.assertEqual((state.state,state.frames_sent,state.failures,state.retries),('error',0,1,0))
        self.assertEqual(state.failure_kind,'native-prewrite')
        self.assertFalse(state.delivery_uncertain);self.assertFalse(state.ownership_uncertain)
        self.assertEqual(len(contexts),1);self.assertEqual(output.sends,0);wait.assert_not_called()
        self.assertNotIn('private',state.error)
        controller.request_exit();self.assertTrue(controller.snapshot().exit_ready)

    def test_uncertain_second_send_retains_previous_frame_without_resend(self):
        class SequenceSource(Source):
            def __init__(self):super().__init__();self.index=0
            def read(self):
                self.index+=1
                return SourceSample('ready',FIRST if self.index==1 else SECOND,True,False)
        output=NativeOutput(fail_second=True)
        controller,contexts=self.make(output,source=SequenceSource(),wait=lambda cancel,seconds:False)
        controller.start();self.assertTrue(controller.wait_stopped(2));state=controller.snapshot()
        self.assertEqual((state.state,state.frames_sent,state.retries),('error',1,0))
        self.assertIs(state.latest_frame,FIRST)
        self.assertEqual(state.failure_kind,'native-delivery-uncertain')
        self.assertTrue(state.delivery_uncertain);self.assertFalse(state.ownership_uncertain)
        self.assertEqual((output.sends,len(output.accepted),len(contexts)),(2,1,1))
        self.assertEqual(state.native_timing.source_read.count,2)
        self.assertEqual(state.native_timing.host_send.count,1)
        self.assertEqual(state.native_timing.cadence_wait.count,1)
        controller.stop()
        self.assertEqual(controller.snapshot().native_timing,state.native_timing)

    def test_native_source_failure_stops_without_retrying_source_or_output(self):
        output=NativeOutput();source=Source(failure='read');wait=Mock()
        controller,contexts=self.make(output,source=source,wait=wait)
        controller.start();self.assertTrue(controller.wait_stopped(2));state=controller.snapshot()
        self.assertEqual((state.state,state.frames_sent,state.retries),('error',0,0))
        self.assertEqual(state.failure_kind,'native-source');self.assertFalse(state.delivery_uncertain)
        self.assertEqual(len(contexts),1);self.assertEqual(output.sends,0);wait.assert_not_called()
        self.assertNotIn('private',state.error);self.assertFalse(output.owned)

    def test_unexpected_native_send_failure_is_conservatively_uncertain(self):
        class FailedOutput(NativeOutput):
            def send(self,frame):
                self.sends+=1
                raise RuntimeError('private backend URL')
        output=FailedOutput();controller,contexts=self.make(output)
        controller.start();self.assertTrue(controller.wait_stopped(2));state=controller.snapshot()
        self.assertTrue(state.delivery_uncertain);self.assertFalse(state.ownership_uncertain)
        self.assertEqual((state.frames_sent,state.retries,output.sends,len(contexts)),(0,0,1,1))
        self.assertIsNone(state.latest_frame);self.assertNotIn('private',state.error)

    def test_real_transport_invalid_geometry_rejects_without_pixel_writes_or_retry(self):
        children=[];objects=[]
        invalid = RGBFrame(480,320,bytes(460800),0)
        object.__setattr__(invalid, 'height', 319)
        source=Source(sample=SourceSample('ready',invalid))
        self.sources.append(source)
        def factory(context):
            output,created,_=transport_fixture.TransportTests.make(self,cancel=context.cancel)
            objects.append(output);children.append(created);return output
        controller=Coordinator(self.store,lambda _:source,transport_context_factory=factory)
        self.controllers.append(controller);controller.start();self.assertTrue(controller.wait_stopped(2))
        state=controller.snapshot()
        self.assertEqual(state.failure_kind,'native-rejected')
        self.assertEqual(state.error,'Native output rejected the frame before submission; only validated 320x480 portrait or 480x320 landscape is supported.')
        self.assertEqual((state.frames_sent,state.retries), (0,0));self.assertIsNone(state.latest_frame)
        self.assertFalse(state.delivery_uncertain);self.assertFalse(state.ownership_uncertain)
        self.assertEqual(len(children[0]),1);self.assertEqual(children[0][0].port.writes,[])
        self.assertFalse(objects[0].owned);self.assertFalse(children[0][0].thread.is_alive())

    def test_real_transport_cancelled_send_keeps_uncertainty_after_stop_ack(self):
        writing=Event();children=[];objects=[];original=transport_fixture.Port.write
        def record(port,data):
            writing.set();return original(port,data)
        source=Source(sample=SourceSample('ready',FIRST));self.sources.append(source)
        def factory(context):
            output,created,_=transport_fixture.TransportTests.make(self,mode='write',cancel=context.cancel)
            objects.append(output);children.append(created);return output
        controller=Coordinator(self.store,lambda _:source,transport_context_factory=factory)
        self.controllers.append(controller)
        with patch.object(transport_fixture.Port,'write',new=record):
            controller.start();self.assertTrue(writing.wait(1));controller.stop()
            self.assertTrue(controller.wait_stopped(2))
        state=controller.snapshot()
        self.assertEqual(state.state,'stopped');self.assertTrue(state.delivery_uncertain)
        self.assertEqual(state.failure_kind,'native-delivery-uncertain');self.assertIsNotNone(state.error)
        self.assertFalse(state.ownership_uncertain)
        self.assertEqual((state.frames_sent,state.retries),(0,0));self.assertIsNone(state.latest_frame)
        self.assertEqual(len(children[0][0].port.writes),1);self.assertFalse(objects[0].owned)
        self.assertFalse(children[0][0].thread.is_alive())
        controller.request_exit();self.assertTrue(controller.snapshot().exit_ready)

    def test_real_transport_lost_close_ack_does_not_invent_owned_resources(self):
        children=[];gates=[];objects=[];wait=GateWait()
        source=Source(sample=SourceSample('ready',FIRST));self.sources.append(source)
        def factory(context):
            output,created,created_gates=transport_fixture.TransportTests.make(self,cancel=context.cancel)
            objects.append(output);children.append(created);gates.append(created_gates)
            return output
        controller=Coordinator(self.store,lambda _:source,transport_context_factory=factory,wait=wait)
        self.controllers.append(controller);receive=ipc.receive_packet
        def lost(channel,*args,**kwargs):
            packet=receive(channel,*args,**kwargs)
            if packet[0]==ipc.REPLY and packet[1]==3:raise ipc.ProtocolError('test lost CLOSE reply')
            return packet
        with patch.object(ipc,'receive_packet',side_effect=lost):
            controller.start();self.assertTrue(wait.entered.wait(1));controller.stop()
            self.assertTrue(controller.wait_stopped(2))
        state=controller.snapshot()
        self.assertEqual(state.failure_kind,'native-close');self.assertFalse(state.ownership_uncertain)
        self.assertFalse(objects[0].owned);self.assertEqual(len(children[0][0].port.writes),122)
        self.assertFalse(children[0][0].thread.is_alive())
        controller.request_exit();self.assertTrue(controller.snapshot().exit_ready)

    def test_real_transport_uncertain_cleanup_retains_lock_readiness(self):
        outputs=[];children=[];gates=[];wait=GateWait()
        source=Source(sample=SourceSample('ready',FIRST));self.sources.append(source)
        def factory(context):
            output,created,created_gates=transport_fixture.TransportTests.make(self,cancel=context.cancel)
            outputs.append(output);children.append(created);gates.append(created_gates)
            return output
        controller=Coordinator(self.store,lambda _:source,transport_context_factory=factory,wait=wait)
        self.controllers.append(controller);controller.start();self.assertTrue(wait.entered.wait(1))
        gates[0][0].fail_close=True;controller.stop();self.assertTrue(controller.wait_stopped(2))
        state=controller.snapshot()
        self.assertTrue(state.ownership_uncertain);self.assertTrue(outputs[0].owned)
        self.assertEqual(state.state,'error');self.assertEqual(state.frames_sent,1)
        self.assertEqual(state.source_state,'stopped')
        self.assertIsNone(state.live_connected);self.assertIsNone(state.data_stale)
        with self.assertRaises(LifecycleError):controller.start()
        with self.assertRaises(LifecycleError):controller.save_settings(self.native)
        report=state.native_timing
        controller.request_exit();controller.stop();self.assertFalse(controller.snapshot().exit_ready)
        self.assertEqual(controller.snapshot().native_timing,report)
        self.assertEqual(len(children[0]),1)

    def test_switch_to_simulation_does_not_report_previous_native_state(self):
        from mars_display.transport import SimulatedTransport
        wait=GateWait();entered=Event();allow=Event();output=NativeOutput();self.outputs.append(output)
        source=Source(sample=SourceSample('ready',FIRST));self.sources.append(source)
        def source_factory(settings):
            if settings.output_mode=='simulated':
                entered.set()
                if not allow.wait(2):raise AssertionError('source not released')
            return source
        controller=Coordinator(self.store,source_factory,
            transport_context_factory=lambda context:output if context.settings.output_mode=='native' else SimulatedTransport(),wait=wait)
        self.controllers.append(controller);controller.start();self.assertTrue(wait.entered.wait(1))
        controller.stop();self.assertTrue(controller.wait_stopped(2))
        controller.save_settings(Settings('https://mars.example',schema_version=2))
        try:
            controller.start();self.assertTrue(entered.wait(1));pending=controller.snapshot()
            self.assertEqual((pending.output_mode,pending.output_state),('simulated','simulated-closed'))
            self.assertEqual(pending.frames_sent,1);self.assertIs(pending.latest_frame,FIRST)
            self.assertIsNone(pending.native_timing)
        finally:allow.set()

    def test_operation_uncertainty_is_visible_until_cleanup_confirms_release(self):
        closing=Event();release=Event()
        class ClosingSource(Source):
            def close(self):
                closing.set()
                if not release.wait(2):raise AssertionError('cleanup not released')
                super().close()
        class FailedOutput(NativeOutput):
            def send(self,frame):raise UsbError('frame',delivery_uncertain=True,ownership_uncertain=True)
        output=FailedOutput();controller,_=self.make(output,source=ClosingSource())
        try:
            controller.start();self.assertTrue(closing.wait(1))
            self.assertTrue(controller.snapshot().ownership_uncertain)
        finally:release.set()
        self.assertTrue(controller.wait_stopped(2))
        self.assertFalse(controller.snapshot().ownership_uncertain)
        controller.request_exit();self.assertTrue(controller.snapshot().exit_ready)

    def test_unknown_cleanup_keeps_strong_resource_reference(self):
        references=[]
        class Unresolved(NativeOutput):
            def close(self):raise UsbError('cleanup',ownership_uncertain=True)
        source=Source(sample=SourceSample('ready',FIRST));self.sources.append(source);wait=GateWait()
        def factory(context):
            value=Unresolved();references.append(weakref.ref(value));return value
        controller=Coordinator(self.store,lambda _:source,transport_context_factory=factory,wait=wait)
        self.controllers.append(controller);controller.start();self.assertTrue(wait.entered.wait(1))
        controller.stop();self.assertTrue(controller.wait_stopped(2));gc.collect()
        self.assertIsNotNone(references[0]())
        self.assertTrue(controller.snapshot().ownership_uncertain)
        controller.request_exit();self.assertFalse(controller.snapshot().exit_ready)


if __name__=='__main__':unittest.main()
