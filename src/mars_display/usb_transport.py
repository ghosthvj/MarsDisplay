"""Explicit owned persistent transport; admission is decided by validated context."""
from dataclasses import dataclass
import secrets
import socket
import threading
import time

from . import usb_ipc as ipc
from .usb_process import OwnedWorker, WindowsGate, launch_worker
from .usb_worker import IDENTITY, OK, WRITE_ERROR, DRAIN_ERROR, CLOSE_ERROR


@dataclass(frozen=True)
class SendTiming(ipc.WorkerTiming):
    """Last successful send in seconds; exchange INCLUDES helper stages."""
    body_encode: float
    exchange: float


class UsbError(RuntimeError):
    """Fixed diagnostic plus delivery/ownership uncertainty for future lifecycle use."""
    def __init__(self, phase, *, delivery_uncertain=False, ownership_uncertain=False):
        super().__init__('USB ' + phase + ' failed; no automatic retry.')
        self.phase = phase
        self.delivery_uncertain = delivery_uncertain
        self.ownership_uncertain = ownership_uncertain


class _Cancel:
    def __init__(self, internal, external):
        self.internal, self.external = internal, external
    def is_set(self):
        return self.internal.is_set() or (self.external is not None and self.external.is_set())


class UsbTransport:
    def __init__(self, identity, *, cancel=None, budgets=ipc.Budgets(),
                 launcher=launch_worker, gate_factory=WindowsGate, timing_clock=time.monotonic):
        if identity != IDENTITY:
            raise ValueError('An explicit supported USB identity is required')
        if not isinstance(budgets, ipc.Budgets):
            raise ValueError('Validated USB safety budgets are required')
        self.identity, self.budgets = identity, budgets
        self._launcher, self._gate_factory = launcher, gate_factory
        self._stopping = threading.Event()
        self._cancel = _Cancel(self._stopping, cancel)
        self._operation = threading.Lock()
        self._owner, self._channel, self._listener = None, None, None
        self._opened, self._request = False, 0
        self._timing_clock, self._last_send_timing = timing_clock, None

    @property
    def last_send_timing(self):
        """Immutable success detail; retained after failure/close, reset on fresh open."""
        return self._last_send_timing

    @property
    def owned(self):
        """True until all child/creation/channel/native cleanup is confirmed."""
        return self._owner is not None or self._channel is not None or self._listener is not None

    def _enter(self):
        if not self._operation.acquire(blocking=False):
            raise UsbError('busy')

    def _check(self, deadline):
        if self._cancel.is_set():
            raise ipc.Cancelled('USB operation cancelled')
        if time.monotonic() >= deadline:
            raise TimeoutError('USB operation deadline exceeded')

    def _dispose(self):
        # Caller owns the operation lock. Cleanup has one shared absolute budget.
        deadline = time.monotonic() + self.budgets.reap
        failed = False
        for name in ('_channel', '_listener'):
            channel = getattr(self, name)
            if channel is not None:
                try:
                    try:
                        channel.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass  # An idle listener/closed peer need not be connected.
                    channel.close()
                    setattr(self, name, None)
                except Exception:
                    failed = True  # Retain the reference; never report known closure.
        if self._owner is not None:
            try:
                self._owner.stop(deadline)
                if not failed:
                    self._owner = None
            except Exception:
                failed = True
        self._opened = False
        if failed:
            raise UsbError('cleanup', ownership_uncertain=True)

    def _fail(self, phase, uncertain):
        try:
            self._dispose()
        except Exception:
            raise UsbError(phase, delivery_uncertain=uncertain, ownership_uncertain=True) from None
        raise UsbError(phase, delivery_uncertain=uncertain) from None

    def _exchange(self, kind, body, deadline, *, cancel):
        self._request += 1
        ipc.send_packet(self._channel, kind, self._request, body, deadline, cancel=cancel)
        response, request, value = ipc.receive_packet(self._channel, deadline, cancel=cancel)
        if request != self._request:
            raise ipc.ProtocolError('Unexpected USB reply')
        if kind == ipc.TIMED_FRAME and response == ipc.TIMED_REPLY:
            return ipc.decode_timing(value)
        if kind == ipc.GROUPED_FRAME and response == ipc.GROUPED_REPLY:
            return ipc.decode_grouped_timing(value)
        if (response != ipc.REPLY or len(value) != 1 or value[0] > CLOSE_ERROR
                or (kind in (ipc.TIMED_FRAME, ipc.GROUPED_FRAME) and value[0] == OK)):
            raise ipc.ProtocolError('Unexpected USB reply')
        return value[0]

    def open(self):
        self._enter()
        try:
            if self._opened:
                return
            if self.owned:
                raise UsbError('cleanup required', ownership_uncertain=True)
            self._last_send_timing = None
            self._stopping.clear()
            deadline = time.monotonic() + self.budgets.start
            try:
                self._check(deadline)
                nonce = secrets.token_hex(32)
                self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                    self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                self._listener.bind(('127.0.0.1', 0))
                self._listener.listen(1)
                port = self._listener.getsockname()[1]
                self._owner = OwnedWorker(port, nonce, self.budgets,
                    launcher=self._launcher, gate_factory=self._gate_factory)
                self._owner.start()
                self._owner.wait_start(deadline, self._cancel)
                while self._channel is None:
                    self._check(deadline)
                    if self._owner.child.poll() is not None:
                        raise RuntimeError('USB worker exited during startup')
                    self._listener.settimeout(min(0.05, max(0.001, deadline-time.monotonic())))
                    try:
                        self._channel, peer = self._listener.accept()
                    except socket.timeout:
                        continue
                    if peer[0] != '127.0.0.1':
                        raise ipc.ProtocolError('Non-local USB peer')
                kind, request, token = ipc.receive_packet(self._channel, deadline, cancel=self._cancel)
                if (kind, request) != (ipc.HELLO, 0) or not secrets.compare_digest(token, bytes.fromhex(nonce)):
                    raise ipc.ProtocolError('Invalid USB peer admission')
                self._listener.close()
                self._listener = None
                self._request = 0
                if self._exchange(ipc.OPEN, self.identity.encode(), deadline, cancel=self._cancel) != OK:
                    raise RuntimeError('USB port admission failed')
                self._check(deadline)
                self._opened = True
            except BaseException:
                self._fail('startup', False)
        finally:
            self._operation.release()

    def send(self, frame):
        started = self._timing_clock()
        body = ipc.encode_frame(frame)  # Rejection has no channel/serial effects.
        body_encode = self._timing_clock() - started
        self._enter()
        try:
            if not self._opened:
                raise UsbError('not open')
            uncertain = True  # Lost/cancelled reply after submission cannot prove no writes.
            try:
                deadline = time.monotonic() + self.budgets.frame
                started = self._timing_clock()
                result = self._exchange(ipc.GROUPED_FRAME, body, deadline, cancel=self._cancel)
                exchange = self._timing_clock() - started
                if not isinstance(result, ipc.WorkerTiming):
                    uncertain = result in (WRITE_ERROR, DRAIN_ERROR, CLOSE_ERROR)
                    raise RuntimeError('USB frame failed')
                detail = SendTiming(result.decode, result.identity, result.encode,
                                    result.write, result.drain, body_encode, exchange, groups=result.groups)
                self._check(deadline)
                self._last_send_timing = detail
            except BaseException:
                self._fail('frame', uncertain)
        finally:
            self._operation.release()

    def close(self):
        deadline = time.monotonic() + self.budgets.close
        self._stopping.set()
        # Cancel wakes bounded socket waits. Never wait unboundedly for a caller
        # holding the lock, or race its in-progress process creation/assignment.
        if not self._operation.acquire(timeout=max(0, deadline-time.monotonic())):
            raise UsbError('close', ownership_uncertain=True)
        try:
            problem = False
            if self._opened and self._channel is not None:
                try:
                    problem = self._exchange(ipc.CLOSE, b'', deadline, cancel=None) != OK
                except BaseException:
                    problem = True
            self._dispose()
            if problem:
                raise UsbError('close')
        finally:
            self._operation.release()
