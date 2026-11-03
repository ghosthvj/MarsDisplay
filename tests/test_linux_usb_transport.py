"""Linux composition with real owned children and fake serial only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from mars_display import linux_usb_transport as linux
from mars_display import usb_ipc as ipc
from mars_display.usb_transport import UsbError
from mars_display.usb_worker import IDENTITY
from mars_display.usb_protocol import encode_portrait, encode_brightness
from test_usb_worker import FRAME


class CompositionTests(unittest.TestCase):
    def test_source_vector_frozen_rejection_and_owner_adapter(self):
        nonce = 'ab' * 32
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(linux.worker_command(123, nonce, 9, 456, 789.0),
                [sys.executable, '-m', 'mars_display.linux_usb_worker',
                 '--linux-usb-worker', '123', nonce, '9', '456', '789.0'])
        with patch.object(sys, 'frozen', True, create=True):
            with self.assertRaises(RuntimeError):
                linux.worker_command(123, nonce, 9, 456, 789.0)
        gate, launcher = Mock(side_effect=AssertionError('Windows gate used')), Mock()
        with patch.object(linux, 'OwnedWorker') as owner:
            linux.owner_factory(123, nonce, ipc.Budgets(), launcher=launcher, gate_factory=gate)
            self.assertIs(owner.call_args.kwargs['launcher'], launcher)
            gate.assert_not_called()


class RealTransportTests(unittest.TestCase):
    def make(self, mode='normal'):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        report = Path(directory.name) / 'events'
        owners = []

        def launcher(*args):
            command = linux.worker_command(*args)
            return [sys.executable, '-B', str(Path(__file__).with_name('linux_usb_session_fixture.py')),
                    mode, str(report), *command[3:]]

        def owner(*args, **kwargs):
            value = linux.owner_factory(*args, **kwargs)
            owners.append(value)
            return value

        obj = linux.create_transport(IDENTITY, launcher=launcher,
            budgets=ipc.Budgets(start=1, frame=.3, close=.2, reap=.5))
        obj._owner_factory = owner

        def cleanup():
            for value in owners:
                value.stop(time.monotonic() + 3)
            obj.close()
        self.addCleanup(cleanup)
        return obj, owners, report

    def events(self, report):
        return [json.loads(line) for line in report.read_text().splitlines()] if report.exists() else []

    def assert_reaped(self, obj, owners):
        self.assertFalse(obj.owned)
        self.assertEqual(len(owners), 1)
        self.assertTrue(owners[0].closed)
        self.assertTrue(owners[0].reaped)
        self.assertFalse(owners[0].thread.is_alive())
        self.assertIsNotNone(owners[0].child.poll())

    def test_admitted_two_frames_brightness_and_idempotent_close(self):
        obj, owners, report = self.make()
        obj.open()
        obj.open()
        obj.send(FRAME)
        obj.send(FRAME)
        obj.set_brightness(60)
        obj.close()
        obj.close()
        self.assert_reaped(obj, owners)
        events = self.events(report)
        self.assertEqual([bytes.fromhex(value) for kind, value in events if kind == 'write'],
                         list(encode_portrait(FRAME) * 2) + [encode_brightness(60)])
        self.assertEqual(sum(kind == 'open' for kind, _ in events), 1)
        self.assertEqual(sum(kind == 'close' for kind, _ in events), 1)
        self.assertEqual(sum(kind == 'inventory' for kind, _ in events), 5)
        self.assertEqual([value for kind, value in events if kind == 'options'],
            [dict(port=None, baudrate=115200, bytesize=8, parity='N', stopbits=1,
                  rtscts=True, dsrdtr=False, write_timeout=3, timeout=1, exclusive=True)])

    def test_wrong_handshake_no_serial_or_inventory(self):
        obj, owners, report = self.make('nonce')
        with self.assertRaises(UsbError) as raised:
            obj.open()
        self.assertEqual(str(raised.exception), 'USB startup failed; no automatic retry.')
        self.assertFalse(raised.exception.delivery_uncertain)
        self.assert_reaped(obj, owners)
        self.assertEqual(self.events(report), [])

    def test_native_hangs_bounded_reaped_no_retry(self):
        for mode in ('open', 'write', 'drain', 'close'):
            with self.subTest(mode=mode):
                obj, owners, report = self.make(mode)
                started = time.monotonic()
                with self.assertRaises(UsbError) as raised:
                    obj.open()
                    if mode == 'close':
                        obj.close()
                    else:
                        obj.send(FRAME)
                self.assertLess(time.monotonic() - started, 2.5)
                self.assertEqual(raised.exception.delivery_uncertain, mode in ('write', 'drain'))
                self.assert_reaped(obj, owners)
                events = self.events(report)
                self.assertEqual(sum(kind == 'open' for kind, _ in events), 1)
                self.assertEqual(sum(kind == 'write' for kind, _ in events),
                                 1 if mode == 'write' else 122 if mode == 'drain' else 0)

    def test_concurrent_close_send_and_retained_cleanup(self):
        obj, owners, report = self.make('write')
        obj.open()
        outcomes = []

        def send():
            try:
                obj.send(FRAME)
            except UsbError as error:
                outcomes.append(error)
        thread = threading.Thread(target=send)
        thread.start()
        try:
            deadline = time.monotonic() + 2
            while not any(kind == 'write' for kind, _ in self.events(report)):
                self.assertLess(time.monotonic(), deadline, 'write barrier watchdog')
                time.sleep(.005)
            # Force uncertain cleanup without losing the actual owner reference.
            with patch.object(owners[0], 'stop', side_effect=RuntimeError('test uncertainty')):
                with self.assertRaises(UsbError):
                    obj.close()
                thread.join(2)
                self.assertFalse(thread.is_alive())
                self.assertTrue(obj.owned)
                with self.assertRaises(UsbError):
                    obj.open()
            obj.close()
            self.assert_reaped(obj, owners)
            self.assertEqual(len(outcomes), 1)
            self.assertTrue(outcomes[0].delivery_uncertain)
            self.assertTrue(outcomes[0].ownership_uncertain)
            self.assertEqual(sum(kind == 'write' for kind, _ in self.events(report)), 1)
        finally:
            owners[0].stop(time.monotonic() + 3)
            thread.join(3)


def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromTestCase(CompositionTests)
    if sys.platform == 'linux':
        suite.addTests(loader.loadTestsFromTestCase(RealTransportTests))
    return suite
