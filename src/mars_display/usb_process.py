"""Owned Windows helper lifetime; uncertain native ownership is never discarded."""
import ctypes
from ctypes import wintypes
import os
import re
import subprocess
import sys
import threading
import time

PREFIX = 'Local\\MarsDisplayUsbStart-'


class _Limits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', wintypes.DWORD), ('minimum', ctypes.c_size_t),
                ('maximum', ctypes.c_size_t), ('active', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                ('scheduling', wintypes.DWORD)]


class _IO(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class _Extended(ctypes.Structure):
    _fields_ = [('limits', _Limits), ('io', _IO), ('process_memory', ctypes.c_size_t),
                ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t),
                ('peak_job', ctypes.c_size_t)]


def _kernel():
    if os.name != 'nt':
        raise RuntimeError('Native Windows USB helper required')
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
        'SetInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        'CreateEventW': ([ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
        'OpenEventW': ([wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
        'AssignProcessToJobObject': ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
        'SetEvent': ([wintypes.HANDLE], wintypes.BOOL),
        'WaitForSingleObject': ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = arguments, result
    return api


def _nonce(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Invalid USB startup admission')


class WindowsGate:
    def __init__(self, nonce):
        _nonce(nonce)
        self.nonce, self.job, self.event = nonce, None, None
        self.api, self.assigned = None, False

    @property
    def closed(self):
        return self.job is None and self.event is None

    def open(self):
        if not self.closed:
            raise RuntimeError('USB gate already owns resources')
        self.assigned = False
        self.api = _kernel()
        self.job = self.api.CreateJobObjectW(None, None)
        if not self.job:
            self.job = None
            raise OSError('Cannot create USB ownership job')
        limits = _Extended()
        limits.limits.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise OSError('Cannot configure USB ownership job')
        ctypes.set_last_error(0)
        self.event = self.api.CreateEventW(None, True, False, PREFIX + self.nonce)
        if not self.event:
            self.event = None
            raise OSError('Cannot create USB startup event')
        if ctypes.get_last_error() == 183:
            raise OSError('USB startup admission already exists')

    def assign(self, child):
        if not self.api.AssignProcessToJobObject(self.job, int(child._handle)):
            raise OSError('Cannot assign owned USB child')
        self.assigned = True

    def release(self):
        if not self.assigned or not self.api.SetEvent(self.event):
            raise OSError('Cannot release owned USB child')

    def close_process(self, child):
        # Popen.Handle.Close marks itself closed before calling CloseHandle.
        # Close the still-owned raw handle first so failure remains retryable.
        handle = child._handle
        if not handle.closed:
            if not self.api.CloseHandle(int(handle)):
                raise OSError('Cannot close owned USB process handle')
            handle.closed = True

    def close(self):
        failed = False
        for name in ('event', 'job'):
            handle = getattr(self, name)
            if handle is not None:
                if self.api.CloseHandle(handle):
                    setattr(self, name, None)
                else:
                    failed = True
        if failed:
            raise OSError('USB native handle ownership remains uncertain')


def await_admission(nonce):
    """A manual/late worker cannot connect or enumerate before admission."""
    _nonce(nonce)
    api = _kernel()
    handle = api.OpenEventW(0x100000, False, PREFIX + nonce)
    if not handle:
        return False
    admitted = api.WaitForSingleObject(handle, 5000) == 0
    return bool(api.CloseHandle(handle)) and admitted


def worker_command(port, nonce):
    _nonce(nonce)
    arguments = ['--usb-worker', str(port), nonce]
    if getattr(sys, 'frozen', False):
        return [sys.executable, *arguments]
    return [sys.executable, '-m', 'mars_display.usb_worker', *arguments]


def launch_worker(port, nonce):
    return subprocess.Popen(worker_command(port, nonce), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            close_fds=True, shell=False,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


class OwnedWorker:
    """One retained creation attempt, child, startup event and native job.

    Popen itself may outlive a timeout. The launcher then remains owned and
    never releases a late child; repeated cleanup may establish certainty later.
    """
    def __init__(self, port, nonce, budgets, *, launcher=launch_worker, gate_factory=WindowsGate):
        self.port, self.nonce, self.budgets, self.launcher = port, nonce, budgets, launcher
        self.gate = gate_factory(nonce)
        self.cancel, self.ready = threading.Event(), threading.Event()
        self.child, self.thread, self.fault, self.reaped = None, None, False, False
        self.closed = False

    def start(self):
        if self.thread is not None:
            raise RuntimeError('USB creation attempt already owned')
        self.thread = threading.Thread(target=self._spawn, name='MarsDisplay USB launcher')
        self.thread.start()

    def _spawn(self):
        try:
            self.gate.open()
            if self.cancel.is_set():
                return
            self.child = self.launcher(self.port, self.nonce)
            self.gate.assign(self.child)
            if self.cancel.is_set():
                self.child.kill()
                self.child.wait(timeout=self.budgets.reap)
            else:
                self.gate.release()
        except BaseException:
            self.fault = True
            if self.child is not None:
                try:
                    self.child.kill()
                    self.child.wait(timeout=self.budgets.reap)
                except Exception:
                    pass  # Still retained; stop() must establish reap certainty.
        finally:
            self.ready.set()

    def wait_start(self, deadline, cancel):
        while not self.ready.is_set():
            if cancel.is_set():
                raise RuntimeError('USB startup cancelled')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('USB startup deadline exceeded')
            self.ready.wait(min(0.05, remaining))
        if self.fault or self.child is None:
            raise RuntimeError('USB child startup failed')

    def stop(self, deadline):
        self.cancel.set()
        if self.thread is not None:
            self.thread.join(max(0, deadline - time.monotonic()))
            if self.thread.is_alive():
                raise RuntimeError('USB creation attempt remains owned')
        if self.child is not None and not self.reaped:
            if self.child.poll() is None:
                try:
                    self.child.wait(timeout=min(0.1, max(0, deadline-time.monotonic()) / 2))
                except subprocess.TimeoutExpired:
                    self.child.kill()
            self.child.wait(timeout=max(0, deadline - time.monotonic()))
            self.reaped = True
        if self.child is not None:
            self.gate.close_process(self.child)
        self.gate.close()
        if not self.gate.closed:
            raise RuntimeError('USB native ownership remains uncertain')
        self.closed = True
