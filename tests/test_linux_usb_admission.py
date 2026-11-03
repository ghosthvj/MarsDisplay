"""Admission tests: no device or production worker is launched."""
import os
import socket
import sys
import threading
import time
import unittest
from unittest import mock

from mars_display import linux_usb_admission as admission
from mars_display import usb_ipc as ipc

NONCE = 'ab' * 32


class AdmissionTests(unittest.TestCase):
    def exchange(self, response):
        parent, child = socket.socketpair()
        outcome = []
        armed = threading.Event()

        def run():
            try:
                with mock.patch.object(admission, 'arm_parent_death', side_effect=lambda expected: armed.set()):
                    admission.await_admission(child.detach(), NONCE, os.getppid(), time.monotonic() + 1)
                outcome.append('admitted')
            except Exception as exc:
                outcome.append(exc)

        thread = threading.Thread(target=run)
        thread.start()
        try:
            self.assertEqual(ipc.receive_packet(parent, time.monotonic() + 1),
                             (ipc.HELLO, 0, bytes.fromhex(NONCE)))
            self.assertTrue(armed.is_set())
            self.assertEqual(outcome, [])  # READY alone is not admission.
            response(parent)
        finally:
            parent.close()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(child.fileno(), -1)
        return outcome

    def test_release(self):
        result = self.exchange(lambda sock: ipc.send_packet(
            sock, ipc.OPEN, 1, bytes.fromhex(NONCE), time.monotonic() + 1))
        self.assertEqual(result, ['admitted'])

    def test_wrong_nonce_malformed_truncated_and_eof(self):
        responses = [lambda sock: ipc.send_packet(sock, ipc.OPEN, 1, b'x' * 32, time.monotonic() + 1),
                     lambda sock: sock.sendall(b'bad!' * 12),
                     lambda sock: sock.sendall(b'MUSB'), lambda sock: None]
        for response in responses:
            with self.subTest(response=response):
                self.assertIsInstance(self.exchange(response)[0], ipc.ProtocolError)

    def test_deadline_even_with_peer_open(self):
        parent, child = socket.socketpair()
        try:
            with mock.patch.object(admission, 'arm_parent_death'):
                with self.assertRaises(TimeoutError):
                    admission.await_admission(child.detach(), NONCE, os.getppid(), time.monotonic() + .05)
        finally:
            parent.close()
            child.close()

    def test_bad_nonce_and_unconnected_socket_close_descriptor(self):
        for nonce in ('bad', NONCE):
            sock = socket.socket()
            fd = sock.detach()
            with self.subTest(nonce=nonce), self.assertRaises((ValueError, OSError)):
                admission.await_admission(fd, nonce, os.getppid(), time.monotonic() + 1)
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_platform_root_parent_and_prctl_guards(self):
        with mock.patch.object(admission.sys, 'platform', 'win32'):
            with self.assertRaises(RuntimeError):
                admission.arm_parent_death(123)
        for uid, euid in ((0, 1000), (1000, 0)):
            with mock.patch.object(admission.sys, 'platform', 'linux'), \
                    mock.patch.object(admission.os, 'getuid', return_value=uid, create=True), \
                    mock.patch.object(admission.os, 'geteuid', return_value=euid, create=True):
                with self.assertRaises(RuntimeError):
                    admission.arm_parent_death(123)
        for parents, result in (([124], 0), ([123, 124], 0), ([123], -1), ([123, 123], 0)):
            with mock.patch.object(admission.sys, 'platform', 'linux'), \
                    mock.patch.object(admission.os, 'getuid', return_value=1000, create=True), \
                    mock.patch.object(admission.os, 'geteuid', return_value=1000, create=True), \
                    mock.patch.object(admission.os, 'getppid', side_effect=parents), \
                    mock.patch.object(admission.signal, 'SIGKILL', 9, create=True), \
                    mock.patch.object(admission.ctypes, 'CDLL') as library:
                library.return_value.prctl.return_value = result
                if parents == [123, 123]:
                    admission.arm_parent_death(123)
                    self.assertEqual(library.return_value.prctl.call_args.args, (1, 9, 0, 0, 0))
                else:
                    with self.assertRaises((RuntimeError, OSError)):
                        admission.arm_parent_death(123)


if __name__ == '__main__':
    unittest.main()
