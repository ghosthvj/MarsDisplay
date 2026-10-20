"""One owned child, Windows kill-on-close job, and a finite named start gate.

The random environment marker prevents accidental entry; it is not an
authentication boundary against the local account owner. No persistent IPC.
"""
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

MARKER = 'MARS_PYTHON_USB_PROBE_WORKER'


def consume_marker(environment=None):
    environment = os.environ if environment is None else environment
    marker = environment.pop(MARKER, None)
    return marker if isinstance(marker, str) and re.fullmatch('[0-9a-f]{32}', marker) else None


def launch_vector(frozen, executable, entrypoint):
    return [executable] if frozen else [executable, '-B', str(entrypoint)]


def wait_owned(child, timeout):
    """Wait only for the supplied Popen; timeout kills and finitely reaps it."""
    try:
        code = child.wait(timeout=max(0, timeout))
        return code if code in range(9) else 7
    except subprocess.TimeoutExpired:
        try:
            child.kill()
            child.wait(timeout=2)
        except Exception:
            return 7
        return 8


def _api():
    """Declare Win32 ABI lazily, with fixed-width DWORD even on other hosts."""
    import ctypes as c
    from ctypes import wintypes as w
    api = c.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([c.c_void_p, w.LPCWSTR], w.HANDLE),
        'CreateEventW': ([c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE),
        'OpenEventW': ([c.c_uint32, w.BOOL, w.LPCWSTR], w.HANDLE),
        'SetInformationJobObject': ([w.HANDLE, c.c_int, c.c_void_p, c.c_uint32], w.BOOL),
        'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
        'SetEvent': ([w.HANDLE], w.BOOL),
        'WaitForSingleObject': ([w.HANDLE, c.c_uint32], c.c_uint32),
        'CloseHandle': ([w.HANDLE], w.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = arguments, result
    return c, api


def _gate_name(marker):
    return 'Local\\MarsPythonUSBProbe-' + marker


def await_gate(marker):
    if os.name != 'nt':
        return False
    try:
        _, api = _api()
        event = api.OpenEventW(0x00100000, False, _gate_name(marker))
        if not event:
            return False
        try:
            released = api.WaitForSingleObject(event, 5000) == 0
        finally:
            closed = api.CloseHandle(event)
        return released and bool(closed)
    except Exception:
        return False


class WindowsJobGate:
    """Own handles only; closing the job terminates any remaining assigned child."""
    def __init__(self, marker):
        self.marker = marker
        self.job = self.event = None

    def __enter__(self):
        c, self.api = _api()
        class Basic(c.Structure):
            _fields_ = [('process_time', c.c_int64), ('job_time', c.c_int64),
                        ('flags', c.c_uint32), ('min_working', c.c_size_t),
                        ('max_working', c.c_size_t), ('active', c.c_uint32),
                        ('affinity', c.c_size_t), ('priority', c.c_uint32),
                        ('scheduling', c.c_uint32)]
        class Counters(c.Structure):
            _fields_ = [(name, c.c_uint64) for name in
                        ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
        class Extended(c.Structure):
            _fields_ = [('basic', Basic), ('io', Counters),
                        ('process_memory', c.c_size_t), ('job_memory', c.c_size_t),
                        ('peak_process', c.c_size_t), ('peak_job', c.c_size_t)]
        try:
            self.job = self.api.CreateJobObjectW(None, None)
            if not self.job:
                raise OSError
            limits = Extended()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(self.job, 9, c.byref(limits), c.sizeof(limits)):
                raise OSError
            self.event = self.api.CreateEventW(None, True, False, _gate_name(self.marker))
            if not self.event or c.get_last_error() == 183:  # reject an existing named event
                raise OSError
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def assign(self, child):
        if not self.api.AssignProcessToJobObject(self.job, int(child._handle)):
            raise OSError

    def release(self):
        if not self.api.SetEvent(self.event):
            raise OSError

    def __exit__(self, *_):
        failed = False
        for name in ('job', 'event'):
            handle = getattr(self, name)
            if handle:
                if not self.api.CloseHandle(handle):
                    failed = True
                setattr(self, name, None)
        if failed:
            raise OSError


def supervise(args, *, popen=subprocess.Popen, gate_factory=WindowsJobGate,
              clock=time.monotonic, platform=None):
    """Inherit all stdio; no pipes, enumeration, or serial access in the parent."""
    if (os.name if platform is None else platform) != 'nt':
        return 7
    deadline = clock() + 90
    child = None
    try:
        marker = secrets.token_hex(16)
        environment = dict(os.environ)
        environment[MARKER] = marker
        vector = launch_vector(getattr(sys, 'frozen', False), sys.executable,
                               Path(__file__).resolve().parents[2] /
                               'tools/windows-python-usb-probe/entrypoint.py')
        with gate_factory(marker) as gate:
            child = popen([*vector, *args], env=environment,
                          stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
            gate.assign(child)
            gate.release()
            return wait_owned(child, deadline - clock())
    except BaseException:
        if child is not None:
            try:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=2)
            except Exception:
                return 7
        return 7
