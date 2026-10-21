"""Real Windows jobs/processes with test-owned fake ports; never real USB."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from mars_display import usb_ipc as ipc, usb_worker as worker
from mars_display.frames import RGBFrame
from mars_display.usb_process import WindowsGate
from mars_display.usb_protocol import encode_portrait
from mars_display.usb_transport import UsbTransport, UsbError

ROOT = Path(__file__).resolve().parents[1]
FRAME = RGBFrame(320,480,(ROOT/'tools/windows-usb-probe/pattern.rgb888').read_bytes(),0)


@unittest.skipUnless(os.name == 'nt', 'native Windows owned helper qualification required')
class NativeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='p3-native-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def launcher(self, mode, report):
        def launch(port, nonce):
            return subprocess.Popen([sys.executable, '-B', str(ROOT/'tests/usb_native_fixture.py'),
                'child', str(port), nonce, mode, str(report)], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return launch

    def test_native_persistent_port_exact_stream_and_confirmed_cleanup(self):
        report = self.root/'normal.jsonl'
        obj = UsbTransport(worker.IDENTITY, launcher=self.launcher('normal', report))
        try:
            obj.open(); obj.send(FRAME); obj.send(FRAME); obj.close()
            self.assertFalse(obj.owned)
        finally: obj.close()
        events = [json.loads(line) for line in report.read_text().splitlines()]
        self.assertEqual([e['op'] for e in events].count('open'),1)
        self.assertEqual([e['op'] for e in events].count('close'),1)
        self.assertEqual([e['op'] for e in events].count('write'),244)
        self.assertEqual(events[-1]['sha256'], hashlib.sha256(b''.join(encode_portrait(FRAME)*2)).hexdigest())

    def test_native_fake_open_write_drain_close_hangs_are_owned_and_finite(self):
        for mode in ('open','write','drain','close'):
            with self.subTest(mode=mode):
                report = self.root/(mode+'.jsonl')
                obj = UsbTransport(worker.IDENTITY, launcher=self.launcher(mode,report),
                    budgets=ipc.Budgets(start=5,frame=2,close=0.5,reap=2))
                start=time.monotonic()
                try:
                    with self.assertRaises(UsbError):
                        obj.open()
                        if mode == 'close': obj.close()
                        else: obj.send(FRAME)
                    self.assertFalse(obj.owned)
                    self.assertLess(time.monotonic()-start,8)
                finally: obj.close()
                events=[json.loads(line) for line in report.read_text().splitlines()]
                self.assertEqual([e['op'] for e in events].count('open'),1)
                self.assertEqual([e['op'] for e in events].count('write'),
                                 {'open':0,'write':1,'drain':122,'close':0}[mode])

    def test_native_closehandle_failure_is_retained_until_explicit_cleanup(self):
        report = self.root/'handles.jsonl'; gate = WindowsGate(secrets.token_hex(32))
        # Use the transport-generated nonce, not a fixture-defined admission token.
        def make_gate(nonce):
            gate.nonce = nonce
            return gate
        obj=UsbTransport(worker.IDENTITY, launcher=self.launcher('normal',report), gate_factory=make_gate)
        try:
            obj.open()
            with patch.object(gate.api, 'CloseHandle', return_value=False):
                with self.assertRaises(UsbError) as error: obj.close()
                self.assertTrue(error.exception.ownership_uncertain)
                self.assertTrue(obj.owned)
                with self.assertRaises(UsbError): obj.open()
            obj.close(); self.assertFalse(obj.owned)
        finally: obj.close()

    def test_native_closed_startup_gate_prevents_socket_and_port_effects(self):
        nonce=secrets.token_hex(32); report=self.root/'held.jsonl'
        gate=WindowsGate(nonce); gate.open(); child=None
        try:
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(0.3)
                child=self.launcher('normal',report)(listener.getsockname()[1],nonce)
                gate.assign(child)
                with self.assertRaises(socket.timeout): listener.accept()
                self.assertIsNone(child.poll()); self.assertFalse(report.exists())
                gate.close(); child.wait(timeout=2)
                self.assertFalse(report.exists())
                gate.close_process(child)
        finally:
            if child is not None:
                if child.poll() is None: child.kill()
                child.wait(timeout=2); gate.close_process(child)
            gate.close()


class SmokeGuardTests(unittest.TestCase):
    def helper(self):
        spec=importlib.util.spec_from_file_location('guarded_usb_smoke', ROOT/'packaging/usb_smoke.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_host_rejection_precedes_paths_environment_and_children(self):
        helper=self.helper()
        with patch.object(helper.os, 'name', 'posix'), patch.object(helper, '_environment') as environment, patch.object(helper.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'Native Windows'):
                helper.check(object(), object())
        environment.assert_not_called();run.assert_not_called()

    def test_missing_executable_creates_no_environment_or_child(self):
        helper=self.helper()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch.object(helper, 'require_host'), patch.object(helper, '_environment') as environment, patch.object(helper, '_launch') as launch:
                with self.assertRaises(ValueError):helper.check(root, root/'state')
            self.assertEqual(list(root.iterdir()), [])
            environment.assert_not_called();launch.assert_not_called()


if __name__ == '__main__': unittest.main()
