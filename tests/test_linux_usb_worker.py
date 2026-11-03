"""Linux resolution and private entry guards; no native serial access."""
from dataclasses import replace
import contextlib
import io
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from mars_display import linux_usb_worker as linux
from mars_display import usb_ipc as ipc, usb_worker as shared
from mars_display.usb_protocol import encode_portrait, encode_brightness
from test_usb_worker import DEVICE, FRAME, Port, WorkerTests

DEVICE = replace(DEVICE, device='/dev/ttyACM0')


class LinuxSessionTests(WorkerTests):
    # Reuse the public packet harness, not the Windows test cases.
    def start(self, snapshots=None, failure=None, **options):
        return super().start(snapshots or [(DEVICE,)], failure,
            resolver=linux.resolve, **options)

    def test_resolution_rejections(self):
        for snapshot in ((), (DEVICE, DEVICE),
                (DEVICE, replace(DEVICE, serial_number='foreign')),
                (replace(DEVICE, serial_number='foreign'),),
                *((replace(DEVICE, device=name),) for name in
                  ('COM5', '/dev/ttyUSB0', '/dev/ttyACM', '/dev/ttyACM0/link'))):
            with self.subTest(snapshot=snapshot):
                c, p, events, results, thread = self.start([snapshot])
                self.assertEqual(self.request(c, ipc.OPEN, 1, shared.IDENTITY.encode()), shared.IDENTITY_ERROR)
                thread.join(1)
                self.assertEqual(results, [1])
                self.assertEqual((p.opens, p.closes, p.writes), (0, 0, []))
                self.assertFalse(any(isinstance(event, dict) for event in events))

    def test_fresh_checks_all_operations(self):
        for kind in (ipc.FRAME, ipc.TIMED_FRAME, ipc.GROUPED_FRAME, ipc.BRIGHTNESS):
            for snapshot in ((), (DEVICE, DEVICE), (replace(DEVICE, device='/dev/ttyACM1'),),
                             (replace(DEVICE, serial_number='foreign'),)):
                with self.subTest(kind=kind, snapshot=snapshot):
                    c, p, events, results, thread = self.start([(DEVICE,), snapshot])
                    self.assertEqual(self.request(c, ipc.OPEN, 1, shared.IDENTITY.encode()), shared.OK)
                    body = b'\x3c' if kind == ipc.BRIGHTNESS else ipc.encode_frame(FRAME)
                    self.assertEqual(self.request(c, kind, 2, body), shared.IDENTITY_ERROR)
                    thread.join(1)
                    self.assertEqual((results, p.opens, p.closes, p.writes), ([1], 1, 1, []))

    def test_post_open_mismatch_has_no_successful_open_reply(self):
        original = shared.run_session

        def session(*args, **options):
            options['port_factory'] = linux.serial_adapter(options['inventory'], options['port_factory'])
            return original(*args, **options)

        with patch.object(shared, 'run_session', side_effect=session):
            c, p, events, results, thread = self.start([(DEVICE,), ()])
            self.assertEqual(self.request(c, ipc.OPEN, 1, shared.IDENTITY.encode()), shared.OPEN_ERROR)
            thread.join(1)
            self.assertEqual((results, p.opens, p.closes, p.writes), ([1], 1, 1, []))

    def test_exact_stream(self):
        c, p, events, results, thread = self.start()
        self.assertEqual(self.request(c, ipc.OPEN, 1, shared.IDENTITY.encode()), shared.OK)
        for seq in (2, 3):
            self.assertEqual(self.request(c, ipc.FRAME, seq, ipc.encode_frame(FRAME)), shared.OK)
        self.assertEqual(self.request(c, ipc.BRIGHTNESS, 4, b'\x3c'), shared.OK)
        self.assertEqual(self.request(c, ipc.CLOSE, 5), shared.OK)
        thread.join(1)
        self.assertEqual(results, [0])
        self.assertEqual((p.opens, p.closes, p.port, p.dtr), (1, 1, DEVICE.device, True))
        self.assertEqual(p.writes, list(encode_portrait(FRAME) * 2) + [encode_brightness(60)])


class AdapterTests(unittest.TestCase):
    def test_exclusive_options_and_post_open_cleanup(self):
        options = dict(port=None, baudrate=115200, bytesize=8, parity='N', stopbits=1,
                       rtscts=True, dsrdtr=False, write_timeout=3, timeout=1)
        for snapshot, failure in (((DEVICE,), None), ((), None),
                ((replace(DEVICE, device='/dev/ttyACM1'),), None), ((DEVICE, DEVICE), None),
                ((DEVICE,), 'open')):
            with self.subTest(snapshot=snapshot, failure=failure):
                native = Port(failure)
                factory = Mock(return_value=native)
                port = linux.serial_adapter(lambda: snapshot, factory)(**options)
                factory.assert_called_once_with(**options, exclusive=True)
                port.port, port.dtr = DEVICE.device, True
                if snapshot == (DEVICE,) and failure is None:
                    port.open()
                    self.assertEqual(port.write(b'abc'), 3)
                    self.assertEqual(port.out_waiting, 0)
                else:
                    with self.assertRaises((ValueError, OSError)):
                        port.open()
                    self.assertEqual(native.closes, 1)
                    self.assertEqual(native.writes, [])
                port.close()
                self.assertEqual((native.opens, native.closes, native.port, native.dtr),
                                 (1, 1, DEVICE.device, True))


class GuardTests(unittest.TestCase):
    def args(self):
        return ['--linux-usb-worker', '12345', 'ab' * 32, '99', '123', str(time.monotonic() + 5)]

    def test_invalid_cli_quiet_no_resources(self):
        valid = self.args()
        cases = [[], ['--help'], valid + ['extra']]
        for index, values in ((0, ['--usb-worker']), (1, ['0', '65536', '-1', '01']),
                              (2, ['bad', 'AB' * 32]), (3, ['-1', 'x']),
                              (4, ['0', '1', 'x']), (5, ['nan', 'inf', '-1'])):
            for value in values:
                args = valid.copy()
                args[index] = value
                cases.append(args)
        cases.append(valid)  # No inherited descriptor / parent admission.
        with tempfile.TemporaryDirectory() as directory:
            for args in cases:
                result = subprocess.run([sys.executable, '-B', '-m', 'mars_display.linux_usb_worker', *args],
                    cwd=directory, env={**os.environ, 'PYTHONPATH': os.path.abspath('src')},
                    capture_output=True, timeout=3)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (2, b'', b''))
                self.assertEqual(os.listdir(directory), [])

    def test_host_root_import_and_admission_reject_before_effects(self):
        cases = [('platform', 'win32'), ('root', True), ('effective_root', True),
                 ('gui', True), ('parent', True), ('descriptor', True),
                 ('nonce', True), ('admission', True)]
        for frozen, (mode, value) in ((frozen, case) for frozen in (False, True) for case in cases):
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(mode=mode, frozen=frozen), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                    patch.object(linux.sys, 'platform', value if mode == 'platform' else 'linux'), \
                    patch.object(linux.os, 'getuid', return_value=0 if mode == 'root' else 1000, create=True), \
                    patch.object(linux.os, 'geteuid', return_value=0 if mode == 'effective_root' else 1000, create=True), \
                    patch.object(linux.sys, 'frozen', frozen, create=True), \
                    patch.dict(sys.modules, {name: module for name, module in sys.modules.copy().items()
                        if name not in ('mars_display.app', 'mars_display.settings', 'PySide6.QtCore',
                                        'PySide6.QtGui', 'PySide6.QtWidgets')}, clear=True), \
                    patch.object(linux.os, 'getppid', return_value=124 if mode == 'parent' else 123, create=True), \
                    patch.object(linux.os, 'fstat', side_effect=OSError() if mode == 'descriptor' else None), \
                    patch.object(linux, 'await_admission', side_effect=ValueError('private')) as admission, \
                    patch.object(linux.socket, 'socket') as channel, \
                    patch.object(linux, 'run_session') as session:
                if mode == 'gui':
                    sys.modules['mars_display.settings'] = Mock()
                inventory, factory = Mock(), Mock()
                args = self.args()
                if mode == 'nonce':
                    args[2] = 'bad'
                self.assertEqual(linux.main(args, inventory=inventory, port_factory=factory), 2)
                self.assertEqual((stdout.getvalue(), stderr.getvalue()), ('', ''))
                inventory.assert_not_called()
                factory.assert_not_called()
                channel.assert_not_called()
                session.assert_not_called()
                if mode != 'admission':
                    admission.assert_not_called()
                else:
                    admission.assert_called_once()

    def test_callable_admitted_source_and_simulated_frozen(self):
        # Mocked admission proves ordering only, not native frozen FD inheritance.
        forbidden = ('mars_display.app', 'mars_display.settings', 'PySide6.QtCore',
                     'PySide6.QtGui', 'PySide6.QtWidgets')
        for frozen in (False, True):
            events = []
            with self.subTest(frozen=frozen), \
                    patch.object(sys, 'platform', 'linux'), \
                    patch.object(sys, 'frozen', frozen, create=True), \
                    patch.object(os, 'getuid', return_value=1000, create=True), \
                    patch.object(os, 'geteuid', return_value=1000, create=True), \
                    patch.object(os, 'getppid', return_value=123, create=True), \
                    patch.object(os, 'fstat'), \
                    patch.dict(sys.modules, {name: module for name, module in sys.modules.copy().items()
                        if name not in forbidden}, clear=True), \
                    patch.object(linux, 'await_admission', side_effect=lambda *args: events.append('admitted')) as admission, \
                    patch.object(linux.socket, 'socket') as channel, \
                    patch.object(linux, 'run_session', side_effect=lambda *args, **kwargs: events.append('session') or 0) as session:
                channel.return_value.__enter__.return_value.connect.side_effect = lambda *args: events.append('connect')
                inventory, factory = Mock(), Mock()
                args = self.args()
                self.assertEqual(linux.main(args, inventory=inventory, port_factory=factory), 0)
                admission.assert_called_once_with(99, args[2], 123, float(args[5]))
                self.assertEqual(events, ['admitted', 'connect', 'session'])
                self.assertIs(session.call_args.kwargs['inventory'], inventory)
                inventory.assert_not_called()
                factory.assert_not_called()


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for cls in (AdapterTests, GuardTests):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    # Inherit only harness helpers; don't collect Windows expectations twice.
    for name in ('test_resolution_rejections', 'test_fresh_checks_all_operations',
                 'test_post_open_mismatch_has_no_successful_open_reply', 'test_exact_stream'):
        suite.addTest(LinuxSessionTests(name))
    return suite
