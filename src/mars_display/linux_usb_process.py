"""Isolated Linux owner; no default production launcher or platform admission.

The explicit launcher builds argv from (port, nonce, control_fd, parent_pid,
absolute_deadline). This owner alone calls Popen, with only the control socket
in pass_fds and DEVNULL streams. A future source/frozen launcher must enter
linux_usb_admission before touching inventory, production IPC or serial.
"""
import os
import socket
import subprocess
import threading
import time

from . import usb_ipc as ipc
from .linux_usb_admission import validate_nonce


class OwnedWorker:
    """One persistent creating thread owns creation, release, kill and reap.

    wait_start registers external cancellation before any release; without
    registration the supervisor waits only until its startup deadline or stop.
    Cancellation and release serialize under _lock. Release-first cancellation
    may permit effects before termination. A timed-out Popen remains owned;
    a late result is killed/reaped, never released. stop's deadline bounds its
    wait, not kernel cleanup: an uncertain attempt keeps its supervisor alive
    and remains retryable. Never signal a saved raw PID.
    """
    def __init__(self, port, nonce, budgets, *, launcher):
        validate_nonce(nonce)
        if not isinstance(budgets, ipc.Budgets) or not callable(launcher):
            raise ValueError('Validated USB budgets and explicit launcher required')
        self.port, self.nonce, self.budgets, self.launcher = port, nonce, budgets, launcher
        self._lock = threading.Lock()
        self._registration = threading.Condition(self._lock)
        self.cancel, self.ready = threading.Event(), threading.Event()
        self.child = self.thread = self.control = self.child_endpoint = None
        self.fault = None
        self.released = self.reaped = self.closed = False
        self._external = None

    def start(self):
        with self._lock:
            if self.thread is not None or self.closed:
                raise RuntimeError('USB creation attempt already owned or closed')
            self.deadline = time.monotonic() + self.budgets.start
            self.thread = threading.Thread(target=self._supervise, name='MarsDisplay Linux USB supervisor')
            try:
                self.thread.start()
            except BaseException:
                self.thread = None
                self.closed = True
                raise

    def _check_locked(self):
        if self._external is not None and self._external.is_set():
            self.cancel.set()
        if self.cancel.is_set():
            raise ipc.Cancelled('USB startup cancelled')
        if time.monotonic() >= self.deadline:
            self.cancel.set()
            raise TimeoutError('USB startup deadline exceeded')

    def _supervise(self):
        try:
            with self._lock:
                self._check_locked()
            self.control, self.child_endpoint = socket.socketpair()
            fd = self.child_endpoint.fileno()
            command = self.launcher(self.port, self.nonce, fd, os.getpid(), self.deadline)
            with self._lock:
                self._check_locked()
            try:
                self.child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    close_fds=True, pass_fds=(fd,), shell=False)
            finally:
                self.child_endpoint.close()
                self.child_endpoint = None
            with self._lock:
                self._check_locked()
            token = bytes.fromhex(self.nonce)
            if ipc.receive_packet(self.control, self.deadline, cancel=self.cancel) != (ipc.HELLO, 0, token):
                raise ipc.ProtocolError('Invalid USB startup readiness')
            with self._registration:
                while self._external is None:
                    self._check_locked()
                    self._registration.wait(min(ipc.POLL, max(0, self.deadline - time.monotonic())))
                self._check_locked()
                # Tiny bounded frame on an otherwise empty stream. Keep lock-held
                # send bounded too; a failed/partial send cannot grant admission.
                ipc.send_packet(self.control, ipc.OPEN, 1, token,
                                min(self.deadline, time.monotonic() + ipc.POLL))
                self.released = True
            self.ready.set()  # Notification is NOT creator-thread exit.
            while not self.cancel.wait(ipc.POLL):
                if self.child.poll() is not None:
                    break
        except BaseException as exc:
            with self._lock:
                self.fault = exc
                self.cancel.set()
        finally:
            self.ready.set()
            # Remain the creating thread until confirmed reap, even when cleanup
            # raises or callers abandon their wait. All references stay retained.
            while not self.closed:
                # Each resource is independent: a failed endpoint close must
                # never starve kill/reap (including the post-Popen duplicate).
                for name in ('child_endpoint', 'control'):
                    channel = getattr(self, name)
                    if channel is not None:
                        try:
                            channel.close()
                            setattr(self, name, None)
                        except BaseException:
                            pass  # Retain this endpoint and retry it next pass.
                try:
                    if self.child is not None and not self.reaped:
                        if self.child.poll() is None:
                            self.child.kill()
                        self.child.wait(timeout=self.budgets.reap)
                        self.reaped = True
                except BaseException:
                    pass  # Keep the creating thread alive through confirmed reap.
                self.closed = (self.child_endpoint is None and self.control is None
                               and (self.child is None or self.reaped))
                if not self.closed:
                    time.sleep(ipc.POLL)

    def wait_start(self, deadline, cancel):
        ipc._validate_deadline(deadline)
        while True:
            with self._lock:
                self._external = cancel
                self._registration.notify_all()
                if cancel.is_set():
                    self.cancel.set()  # Propagate into protected owner state.
                    raise ipc.Cancelled('USB startup cancelled')
                if time.monotonic() >= deadline:
                    self.cancel.set()
                    raise TimeoutError('USB startup deadline exceeded')
                if self.ready.is_set():
                    if self.fault is not None:
                        raise self.fault
                    if not self.released:
                        raise RuntimeError('USB child startup failed')
                    return
            self.ready.wait(min(ipc.POLL, max(0, deadline - time.monotonic())))

    def stop(self, deadline):
        ipc._validate_deadline(deadline)
        if not self._lock.acquire(timeout=max(0, deadline - time.monotonic())):
            raise RuntimeError('USB creation attempt remains owned')
        try:
            self.cancel.set()
            self._registration.notify_all()
            thread = self.thread
            if thread is None:
                self.closed = True
        finally:
            self._lock.release()
        if thread is not None:
            thread.join(max(0, deadline - time.monotonic()))
            if thread.is_alive() or not self.closed:
                raise RuntimeError('USB creation attempt remains owned')
