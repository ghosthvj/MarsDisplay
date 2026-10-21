"""Public persistent transport with owned, controllable test-only peers."""
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch
import threading
import time
import unittest

from mars_display import usb_ipc as ipc, usb_worker as worker
from mars_display.usb_transport import UsbTransport, UsbError
from mars_display.frames import RGBFrame
from mars_display.devices import USBSerialDescriptor

FRAME = RGBFrame(320, 480, (Path(__file__).parents[1]/'tools/windows-usb-probe/pattern.rgb888').read_bytes(), 0)
DEVICE = USBSerialDescriptor('COM5',0x1a86,0x5722,'USB35INCHIPSV2',None,None,None,None,None)


class Port:
    def __init__(self, killed, mode):
        self.killed, self.mode = killed, mode
        self.opens, self.closes, self.writes = 0, 0, []
    def block(self, stage):
        if self.mode == stage:
            if not self.killed.wait(2):
                raise TimeoutError('controlled fixture did not get killed')
            raise OSError('private backend details')
    def open(self):
        self.opens += 1
        self.block('open')
    def write(self, data):
        self.writes.append(data)
        self.block('write')
        return len(data)
    @property
    def out_waiting(self):
        return 1 if self.mode == 'drain' else 0
    def close(self):
        self.closes += 1
        self.block('close')


class Process:
    def __init__(self, port, nonce, mode):
        self.admitted = threading.Event()
        self.killed = threading.Event()
        self.mode, self.returncode, self.channel = mode, None, None
        self.port = Port(self.killed, mode)
        self.thread = threading.Thread(target=self.run, args=(port, nonce))
        self.thread.start()
    def run(self, port, nonce):
        try:
            if not self.admitted.wait(2) or self.killed.is_set():
                return
            with socket.socket() as channel:
                self.channel = channel
                channel.connect(('127.0.0.1', port))
                if self.mode == 'nonce':
                    ipc.send_packet(channel, ipc.HELLO, 0, b'x'*32, time.monotonic()+1)
                    self.killed.wait(1)
                else:
                    worker.run_session(channel, bytes.fromhex(nonce), inventory=lambda:(DEVICE,),
                        port_factory=lambda **opts:self.port,
                        budgets=ipc.Budgets(drain=0.05))
        finally:
            self.returncode = 0
    def poll(self):
        return self.returncode
    def kill(self):
        self.killed.set()
        self.admitted.set()
        if self.channel is not None:
            try:self.channel.shutdown(socket.SHUT_RDWR)
            except OSError:pass
    def wait(self, timeout):
        self.thread.join(timeout)
        if self.thread.is_alive():raise subprocess.TimeoutExpired('owned fixture', timeout)
        return self.returncode


class Gate:
    def __init__(self, nonce):
        self.closed, self.child, self.fail_close = True, None, False
    def open(self):self.closed = False
    def assign(self, child):self.child = child
    def release(self):self.child.admitted.set()
    def close_process(self, child):pass
    def close(self):
        if self.fail_close:raise OSError('controlled handle close failure')
        self.closed = True


class TransportTests(unittest.TestCase):
    def test_private_source_route_rejects_without_output_or_gui(self):
        for args in (['--badflag'], ['--usb-worker'],
                     ['--usb-worker', '0', 'a'*64],
                     ['--usb-worker', '12345', 'bad']):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, '-B', '-m',
                    'mars_display.usb_worker', *args], input='', capture_output=True,
                    text=True, timeout=3)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (2, '', ''))

    def test_source_frozen_vectors_and_windowed_streams(self):
        from mars_display import usb_process
        nonce = 'a'*64
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(usb_process.worker_command(12345, nonce),
                [sys.executable, '-m', 'mars_display.usb_worker', '--usb-worker', '12345', nonce])
        with patch.object(sys, 'frozen', True, create=True), patch.object(subprocess, 'Popen') as launch:
            usb_process.launch_worker(12345, nonce)
            self.assertEqual(launch.call_args.args[0],
                [sys.executable, '--usb-worker', '12345', nonce])
            for name in ('stdin', 'stdout', 'stderr'):
                self.assertEqual(launch.call_args.kwargs[name], subprocess.DEVNULL)
            self.assertFalse(launch.call_args.kwargs['shell'])
            self.assertTrue(launch.call_args.kwargs['close_fds'])

    def make(self, mode=None, cancel=None, budgets=None, launcher_delay=None,
             timing_clock=time.monotonic):
        children, gates = [], []
        def launch(port, nonce):
            if launcher_delay is not None:
                if not launcher_delay.wait(2):raise RuntimeError('fixture wait exceeded')
            child = Process(port, nonce, mode)
            children.append(child)
            return child
        def gate(nonce):
            value = Gate(nonce);gates.append(value);return value
        obj = UsbTransport(worker.IDENTITY, cancel=cancel,
            budgets=budgets or ipc.Budgets(start=1, frame=1, close=0.5, reap=0.2),
            launcher=launch, gate_factory=gate, timing_clock=timing_clock)
        def cleanup():
            if launcher_delay is not None:launcher_delay.set()
            for value in gates:value.fail_close = False
            try:
                obj.close()
            finally:
                for child in children:
                    child.kill()
                    child.wait(1)
        self.addCleanup(cleanup)
        return obj, children, gates

    def test_one_owned_child_two_frames_idempotent_close_and_explicit_reopen(self):
        obj, children, gates = self.make()
        self.assertFalse(obj.owned);self.assertEqual((children,gates),([],[]))
        self.assertIsNone(obj.open());self.assertIsNone(obj.open())
        self.assertTrue(obj.owned)
        self.assertIsNone(obj.send(FRAME));self.assertIsNone(obj.send(FRAME))
        self.assertIsNone(obj.close());self.assertIsNone(obj.close())
        self.assertFalse(obj.owned);self.assertEqual(len(children),1)
        self.assertEqual((children[0].port.opens,children[0].port.closes,len(children[0].port.writes)),(1,1,244))
        self.assertIsNone(obj.open());self.assertEqual(len(children),2);obj.close()

    def test_invalid_frame_has_no_new_port_or_ipc_effects(self):
        obj, children, _ = self.make();obj.open()
        port=children[0].port
        with self.assertRaises(ValueError):obj.send(RGBFrame(480,320,FRAME.rgb,0))
        self.assertEqual((port.opens,port.closes,port.writes),(1,0,[]))
        self.assertTrue(obj.owned);obj.send(FRAME)
        self.assertEqual(len(port.writes),122)

    def test_unknown_identity_constructor_and_pre_cancel_never_spawn(self):
        calls=[]
        with self.assertRaises(ValueError):UsbTransport('foreign',launcher=lambda *a:calls.append(a))
        cancel=threading.Event();cancel.set();obj, children, gates=self.make(cancel=cancel)
        with self.assertRaises(UsbError):obj.open()
        self.assertEqual((children,gates),([],[]));self.assertFalse(obj.owned)

    def test_nonce_mismatch_never_opens_port(self):
        obj,children,_=self.make('nonce')
        with self.assertRaises(UsbError):obj.open()
        self.assertFalse(obj.owned)
        self.assertEqual((children[0].port.opens,children[0].port.writes),(0,[]))

    def test_open_write_drain_close_hangs_finish_and_reap_without_resend(self):
        for mode in ('open','write','drain','close'):
            with self.subTest(mode=mode):
                budgets=ipc.Budgets(start=0.1,frame=0.2,close=0.05,reap=0.2)
                obj,children,_=self.make(mode,budgets=budgets)
                start=time.monotonic()
                with self.assertRaises(UsbError) as raised:
                    obj.open()
                    if mode=='close':obj.close()
                    else:obj.send(FRAME)
                self.assertLess(time.monotonic()-start,0.8)
                self.assertFalse(obj.owned)
                self.assertFalse(children[0].thread.is_alive())
                self.assertEqual(len(children),1)
                self.assertLessEqual(len(children[0].port.writes),122)
                self.assertEqual(raised.exception.delivery_uncertain,mode in ('write','drain'))

    def test_cancel_inflight_and_concurrent_send_have_no_queue(self):
        cancel=threading.Event();obj,children,_=self.make('write',cancel=cancel)
        obj.open();outcomes=[]
        def send():
            try:obj.send(FRAME)
            except UsbError as error:outcomes.append(error)
        t=threading.Thread(target=send);t.start()
        try:
            deadline=time.monotonic()+1
            while not children[0].port.writes and time.monotonic()<deadline:
                threading.Event().wait(0.005)
            with self.assertRaises(UsbError):obj.send(FRAME)
            cancel.set();obj.close();t.join(1)
            self.assertFalse(t.is_alive());self.assertFalse(obj.owned)
            self.assertEqual(len(outcomes),1);self.assertTrue(outcomes[0].delivery_uncertain)
            self.assertEqual(len(children[0].port.writes),1)
        finally:cancel.set();children[0].kill();t.join(1)

    def test_failed_handle_close_retains_ownership_and_rejects_reopen(self):
        obj,children,gates=self.make();obj.open();gates[0].fail_close=True
        with self.assertRaises(UsbError) as raised:obj.close()
        self.assertTrue(raised.exception.ownership_uncertain);self.assertTrue(obj.owned)
        with self.assertRaises(UsbError):obj.open()
        self.assertEqual(len(children),1)
        gates[0].fail_close=False;obj.close();self.assertFalse(obj.owned)

    def test_late_spawn_stays_gated_owned_and_is_cleaned_before_io(self):
        release=threading.Event()
        obj,children,gates=self.make(launcher_delay=release,
            budgets=ipc.Budgets(start=0.02,reap=0.02,close=0.1))
        with self.assertRaises(UsbError) as raised:obj.open()
        self.assertTrue(raised.exception.ownership_uncertain);self.assertTrue(obj.owned)
        release.set();obj.close()
        self.assertFalse(obj.owned);self.assertEqual(len(children),1)
        self.assertEqual((children[0].port.opens,children[0].port.writes),(0,[]))


if __name__=='__main__':unittest.main()
