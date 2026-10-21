"""Fixed profiles over real framing and test-owned fake ports."""
from dataclasses import replace
import hashlib
import io
import json
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from mars_display import usb_ipc as ipc, usb_worker as worker
from mars_display import usb_grouping_worker as child
from mars_display import usb_grouping_profile as profile
import test_usb_worker as session


class GroupingWorkerTests(unittest.TestCase):
    start = session.WorkerTests.start
    request = session.WorkerTests.request

    def start_profile(self, arm, **kwargs):
        original = worker.run_session
        encoder = profile.fixed_encoder(arm, profile.load_fixture())
        with patch.object(worker, 'run_session', side_effect=lambda *a, **kw:
                original(*a, **kw, encoder=encoder)):
            return self.start(**kwargs)

    def test_fixed_profiles_exact_same_stream_different_write_boundaries(self):
        streams = []
        for arm, count, size in [('A', 120, 2560), ('B', 60, 5120)]:
            c, port, events, results, thread = self.start_profile(arm)
            self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
            ipc.send_packet(c, ipc.GROUPED_FRAME, 2, ipc.encode_frame(session.FRAME), time.monotonic()+2)
            kind, request, body = ipc.receive_packet(c, time.monotonic()+2)
            self.assertEqual((kind, request), (ipc.GROUPED_REPLY, 2))
            self.assertIsNotNone(ipc.decode_grouped_timing(body).groups)
            self.assertEqual(self.request(c, ipc.CLOSE, 3), worker.OK)
            thread.join(1)
            self.assertEqual((results, port.opens, port.closes), ([0], 1, 1))
            self.assertEqual(list(map(len, port.writes)), [16, 6] + [size]*count)
            self.assertEqual(sum(map(len, port.writes)), 307222)
            streams.append(b''.join(port.writes))
        self.assertEqual(streams, [b''.join(session.encode_portrait(session.FRAME))]*2)

    def test_profiles_preserve_short_write_drain_and_identity_rejection(self):
        for arm in ('A', 'B'):
            for failure in ('short', 'drain', 'moved', 'duplicate'):
                snapshots = [(session.DEVICE,)]
                if failure == 'moved':
                    snapshots.append((replace(session.DEVICE, device='COM6'),))
                if failure == 'duplicate':
                    snapshots.append((session.DEVICE, session.DEVICE))
                c, port, _, results, thread = self.start_profile(arm, snapshots=snapshots,
                    failure=failure if failure in ('short', 'drain') else None)
                self.assertEqual(self.request(c, ipc.OPEN, 1, worker.IDENTITY.encode()), worker.OK)
                status = worker.WRITE_ERROR if failure == 'short' else worker.DRAIN_ERROR if failure == 'drain' else worker.IDENTITY_ERROR
                self.assertEqual(self.request(c, ipc.GROUPED_FRAME, 2, ipc.encode_frame(session.FRAME)), status)
                thread.join(1)
                self.assertEqual((results, port.opens, port.closes), ([1], 1, 1))
                self.assertEqual(len(port.writes), 3 if failure == 'short' else
                    (122 if arm == 'A' else 62) if failure == 'drain' else 0)

    def test_private_rejection_precedes_admission_socket_inventory_and_gui(self):
        good = ['--grouping-worker', 'A', 'COM5', '12345', 'a'*64]
        for args in ([], good + ['extra'], ['--usb-worker', *good[1:]],
                     [good[0], '5120', *good[2:]], [*good[:2], 'com5', *good[3:]],
                     [*good[:3], '0', good[4]], [*good[:4], 'bad']):
            with patch.object(child, 'await_admission') as admission, \
                    patch.object(child.socket, 'socket') as sock, \
                    patch.object(child, 'enumerate_devices') as inventory:
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    self.assertEqual(child.main(args), 2)
                self.assertEqual((out.getvalue(), err.getvalue()), ('', ''))
                admission.assert_not_called(); sock.assert_not_called(); inventory.assert_not_called()
        for name in ('mars_display.settings', 'mars_display.app', 'PySide6.QtCore', 'PySide6.QtWidgets'):
            with patch.dict(sys.modules, {name: object()}), patch.object(child, 'await_admission') as admission:
                self.assertEqual(child.main(good), 2)
                admission.assert_not_called()

    def test_not_admitted_never_connects_or_enumerates(self):
        with patch.object(child, 'await_admission', return_value=False), \
                patch.object(child.socket, 'socket') as sock, \
                patch.object(child, 'enumerate_devices') as inventory:
            self.assertEqual(child.main(['--grouping-worker', 'B', 'COM5', '12345', 'a'*64]), 2)
            sock.assert_not_called(); inventory.assert_not_called()

    def test_expected_com_revalidated_before_serial_open(self):
        for snapshot in ((replace(session.DEVICE, device='COM6'),), (session.DEVICE, session.DEVICE)):
            with patch.object(child, 'enumerate_devices', return_value=snapshot):
                with self.assertRaises(ValueError):
                    child.confirmed_inventory('COM5')

    def test_owned_source_child_bootstrap_with_real_ipc_and_only_fake_ports(self):
        from mars_display.usb_transport import UsbTransport
        # Python-only launcher/gate fixtures stand in for native Windows admission.
        # The fresh interpreter runs the actual private bootstrap, before Qt.
        script = '''import hashlib, json, sys
from mars_display import usb_grouping_worker as child
from mars_display.devices import USBSerialDescriptor
from mars_display import usb_worker
writes = []
class Port:
    out_waiting = 0
    def open(self): pass
    def write(self, packet):
        writes.append(packet)
        return len(packet)
    def close(self):
        print(json.dumps([list(map(len, writes)), hashlib.sha256(b''.join(writes)).hexdigest()]), flush=True)
original = child.run_session
def run(*args, **kwargs):
    return original(*args, **kwargs, port_factory=lambda **options: Port())
child.run_session = run
child.enumerate_devices = lambda: (USBSerialDescriptor('COM5',0x1a86,0x5722,'USB35INCHIPSV2',None,None,None,None,None),)
child.await_admission = lambda nonce: sys.stdin.readline() == nonce + '\\n'
raise SystemExit(child.main(sys.argv[1:]))
'''
        class Gate:
            closed = True
            def __init__(self, nonce): self.nonce = nonce
            def open(self): self.closed = False
            def assign(self, process): self.process = process
            def release(self):
                self.process.stdin.write(self.nonce + '\n')
                self.process.stdin.flush()
                self.process.stdin.close()
            def close_process(self, process): pass
            def close(self): self.closed = True
        for arm, count, size in [('A', 120, 2560), ('B', 60, 5120)]:
            children = []
            def launch(port, nonce):
                process = subprocess.Popen([sys.executable, '-B', '-c', script,
                    '--grouping-worker', arm, 'COM5', str(port), nonce],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                children.append(process)
                return process
            transport = UsbTransport(worker.IDENTITY, launcher=launch, gate_factory=Gate)
            try:
                transport.open()
                transport.send(profile.load_fixture())
                self.assertIsNotNone(transport.last_send_timing.groups)
                transport.close()
                self.assertFalse(transport.owned)
                self.assertEqual(len(children), 1)
                process = children[0]
                self.assertEqual(process.returncode, 0)
                self.assertEqual(process.stderr.read(), '')
                self.assertEqual(json.loads(process.stdout.read()), [[16, 6]+[size]*count,
                    hashlib.sha256(b''.join(session.encode_portrait(session.FRAME))).hexdigest()])
            finally:
                transport.close()
                for process in children:
                    process.stdout.close()
                    process.stderr.close()

    def test_frozen_fixed_resource_and_hash(self):
        with patch.object(profile.sys, 'frozen', True, create=True), \
                patch.object(profile.sys, '_MEIPASS', '/fixed-bundle', create=True), \
                patch.object(profile.Path, 'read_bytes', return_value=session.FRAME.rgb) as read:
            self.assertEqual(profile.load_fixture().rgb, session.FRAME.rgb)
            self.assertEqual(profile.fixture_path(), profile.Path('/fixed-bundle/grouping-pattern.rgb888'))
            read.assert_called_once_with()

    def test_normal_worker_cli_cannot_select_profile(self):
        with patch('mars_display.usb_process.await_admission') as admission:
            self.assertEqual(worker.main(['--grouping-worker', 'B', 'COM5', '12345', 'a'*64]), 2)
            self.assertEqual(worker.main(['--usb-worker', '12345', 'a'*64, 'B']), 2)
            admission.assert_not_called()


if __name__ == '__main__':
    unittest.main()
