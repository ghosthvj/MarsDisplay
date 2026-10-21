"""Persistent worker through framed socket peers and explicit fake ports only."""
from dataclasses import replace
from pathlib import Path
import socket
import threading
import time
import unittest

from mars_display import usb_ipc as ipc, usb_worker as worker
from mars_display.devices import USBSerialDescriptor
from mars_display.frames import RGBFrame
from mars_display.usb_protocol import encode_portrait

DEVICE=USBSerialDescriptor('COM5',0x1a86,0x5722,'USB35INCHIPSV2',None,None,None,None,None)
FRAME=RGBFrame(320,480,(Path(__file__).parents[1]/'tools/windows-usb-probe/pattern.rgb888').read_bytes(),1.)
TOKEN=b'a'*32


class Port:
    def __init__(self, failure=None):
        self.failure,self.opens,self.closes,self.writes=failure,0,0,[]
        self.port=None;self.dtr=False
    def open(self):
        self.opens+=1
        if self.failure=='open':raise OSError('private detail')
    def write(self,data):
        self.writes.append(data)
        if len(self.writes)==3:
            if self.failure=='short':return len(data)-1
            if self.failure=='write':raise OSError('private detail')
        return len(data)
    @property
    def out_waiting(self):return 1 if self.failure=='drain' else 0
    def close(self):
        self.closes+=1
        if self.failure=='close':raise OSError('private detail')


class WorkerTests(unittest.TestCase):
    def start(self, snapshots=None, failure=None):
        client,server=socket.socketpair();port=Port(failure);events=[];results=[]
        snapshots=list(snapshots or [(DEVICE,),(DEVICE,),(DEVICE,)])
        now=[0.]
        def inventory():
            events.append('inventory')
            return snapshots.pop(0) if len(snapshots)>1 else snapshots[0]
        def factory(**options):
            events.append(options)
            self.assertTrue(port.dtr is False)
            return port
        def clock():return now[0]
        def sleep(seconds):now[0]+=seconds
        def execute():
            try:results.append(worker.run_session(server,TOKEN,inventory=inventory,port_factory=factory,clock=clock,sleep=sleep))
            finally:server.close()
        thread=threading.Thread(target=execute);thread.start()
        def cleanup():
            client.close();thread.join(2)
            self.assertFalse(thread.is_alive(),'owned test worker did not finish')
        self.addCleanup(cleanup)
        self.assertEqual(ipc.receive_packet(client,time.monotonic()+1),(ipc.HELLO,0,TOKEN))
        return client,port,events,results,thread

    def request(self, client, kind, seq, body=b''):
        ipc.send_packet(client,kind,seq,body,time.monotonic()+1)
        k,n,reply=ipc.receive_packet(client,time.monotonic()+1)
        self.assertEqual((k,n),(ipc.REPLY,seq))
        return reply[0]

    def test_two_frames_use_one_open_and_exact_packet_stream(self):
        client,port,events,results,thread=self.start()
        self.assertEqual(events,[])
        self.assertEqual(self.request(client,ipc.OPEN,1,worker.IDENTITY.encode()),worker.OK)
        self.assertEqual(self.request(client,ipc.FRAME,2,ipc.encode_frame(FRAME)),worker.OK)
        self.assertEqual(self.request(client,ipc.FRAME,3,ipc.encode_frame(FRAME)),worker.OK)
        self.assertEqual(self.request(client,ipc.CLOSE,4),worker.OK)
        thread.join(1);self.assertEqual(results,[0])
        self.assertEqual((port.opens,port.closes),(1,1))
        self.assertTrue(port.dtr);self.assertEqual(port.port,'COM5')
        self.assertEqual(tuple(port.writes),encode_portrait(FRAME)*2)
        self.assertEqual(events[0],'inventory');self.assertEqual(events[2:],['inventory','inventory'])
        self.assertEqual(events[1],dict(port=None,baudrate=115200,bytesize=8,parity='N',stopbits=1,rtscts=True,dsrdtr=False,write_timeout=3,timeout=1))

    def test_close_before_open_is_usb_free(self):
        c,p,e,r,t=self.start();self.assertEqual(self.request(c,ipc.CLOSE,1),worker.OK)
        t.join(1);self.assertEqual(r,[0]);self.assertEqual((p.opens,p.closes,p.writes,e),(0,0,[],[]))

    def test_missing_duplicate_foreign_and_unknown_identity_reject_before_open(self):
        for snapshot,identity in [((),worker.IDENTITY),((DEVICE,DEVICE),worker.IDENTITY),
                ((DEVICE,replace(DEVICE,device='com5',serial_number='foreign')),worker.IDENTITY),
                ((DEVICE,),'usb:1234:5678:foreign')]:
            with self.subTest(snapshot=snapshot,identity=identity):
                c,p,e,r,t=self.start([snapshot]);self.assertEqual(self.request(c,ipc.OPEN,1,identity.encode()),worker.IDENTITY_ERROR)
                t.join(1);self.assertEqual(r,[1]);self.assertEqual((p.opens,p.closes,p.writes),(0,0,[]))
                self.assertFalse(any(isinstance(item,dict) for item in e))

    def test_fresh_identity_and_invalid_frame_prevent_writes(self):
        for changed in ('identity','frame'):
            snapshots=[(DEVICE,), (replace(DEVICE,serial_number='foreign'),)] if changed=='identity' else [(DEVICE,)]
            c,p,e,r,t=self.start(snapshots);self.assertEqual(self.request(c,ipc.OPEN,1,worker.IDENTITY.encode()),worker.OK)
            body=ipc.encode_frame(FRAME)
            if changed=='frame':body=ipc.METADATA.pack(480,320,0)+FRAME.rgb
            expected=worker.IDENTITY_ERROR if changed=='identity' else worker.INVALID
            self.assertEqual(self.request(c,ipc.FRAME,2,body),expected)
            t.join(1);self.assertEqual(r,[1]);self.assertEqual((p.opens,p.closes,p.writes),(1,1,[]))

    def test_open_write_drain_close_failures_never_retry(self):
        for failure,status in [('open',worker.OPEN_ERROR),('short',worker.WRITE_ERROR),('write',worker.WRITE_ERROR),('drain',worker.DRAIN_ERROR),('close',worker.CLOSE_ERROR)]:
            with self.subTest(failure=failure):
                c,p,e,r,t=self.start(failure=failure)
                result=self.request(c,ipc.OPEN,1,worker.IDENTITY.encode())
                if failure=='open':self.assertEqual(result,status)
                else:
                    self.assertEqual(result,worker.OK)
                    if failure=='close':self.assertEqual(self.request(c,ipc.CLOSE,2),status)
                    else:self.assertEqual(self.request(c,ipc.FRAME,2,ipc.encode_frame(FRAME)),status)
                t.join(1);self.assertEqual(r,[1]);self.assertEqual((p.opens,p.closes),(1,1))
                expected=3 if failure in ('short','write') else 122 if failure=='drain' else 0
                self.assertEqual(len(p.writes),expected)

    def test_wrong_order_and_replayed_request_are_terminal(self):
        for kind,seq,body,prior in [(ipc.FRAME,1,ipc.encode_frame(FRAME),False),(ipc.OPEN,1,worker.IDENTITY.encode(),True)]:
            c,p,e,r,t=self.start()
            if prior:self.assertEqual(self.request(c,ipc.OPEN,1,worker.IDENTITY.encode()),worker.OK)
            self.assertEqual(self.request(c,kind,seq,body),worker.INVALID)
            t.join(1);self.assertEqual(r,[1]);self.assertEqual(p.writes,[])
            self.assertEqual((p.opens,p.closes),(1,1) if prior else (0,0))


if __name__=='__main__':unittest.main()
