"""Source-only, single-frame Linux host timing; never used by the application."""
import ctypes
import json
import math
import os
import re
import signal
import sys
import time

from .devices import enumerate_devices, select_device
from .usb_grouping_profile import load_fixture, fixed_encoder
from .usb_worker import IDENTITY, serial_factory

HELP = '''Linux single-frame measurement (source only)
  --help       Show help; no USB access (also the default).
  --self-test  Validate the fixed baseline fixture/encoder; no USB access.
  --run        Linux only: confirm current tty, then send one baseline A frame.
No other options. Separate execution authorization is required before --run.
Close all other apps; exclusive access is advisory. DTR may affect the device.
Host timings only, not panel latency or FPS. See docs/linux-usb-measurement.md.'''
SELFTEST = 'Self-test OK: baseline A, 122 writes, 307222 bytes; no USB access.'
INVALID = 'Invalid arguments; use --help.'
NOTICE = 'One baseline frame; exclusive access is advisory. Close all other apps. DTR may affect the device.'
CANCELLED = 'Cancelled; no port opened.'
FAILED = 'Measurement failed; partial delivery may be uncertain. No retry.'
CLEANUP = 'Transfer stopped; waiting to reap owned child. Cleanup is not yet confirmed.'
STAGES = ('open', 'encode', 'orientation', 'header', 'pixels', 'write', 'drain', 'close')
FRAME_SECONDS, DRAIN_SECONDS, TOTAL_SECONDS = 20, 15, 30
MAX_PAYLOAD = 2048


def prompt(port):
    return f'Type SEND {port} to send exactly one baseline frame:'


def report(numbers):
    return 'Host seconds: ' + ', '.join(f'{key}={numbers[key]:.6f}' for key in STAGES)


def baseline():
    fixture = load_fixture()
    packets = fixed_encoder('A', fixture)(fixture)
    if len(packets) != 122 or sum(map(len, packets)) != 307222:
        raise ValueError('Invalid baseline')
    return packets


def resolve(expected=None):
    snapshot = enumerate_devices()
    selected = select_device(snapshot, IDENTITY)
    port = selected.device
    if not re.fullmatch(r'/dev/ttyACM[0-9]+', port):
        raise ValueError('Unsupported tty')
    if [item for item in snapshot if item.device == port] != [selected]:
        raise ValueError('Ambiguous tty')
    if expected is not None and port != expected:
        raise ValueError('Confirmed tty changed')
    return port


def measure(confirmed):
    """Only the owned child calls this in production; injection is Python-only."""
    timing = {}
    started = time.monotonic()
    packets = baseline()
    timing['encode'] = time.monotonic() - started
    resolve(confirmed)
    port = serial_factory(port=None, baudrate=115200, bytesize=8, parity='N',
                          stopbits=1, rtscts=True, dsrdtr=False,
                          write_timeout=3, timeout=1, exclusive=True)
    close_attempted = False
    try:
        port.port, port.dtr = confirmed, True
        started = time.monotonic()
        port.open()
        timing['open'] = time.monotonic() - started
        resolve(confirmed)
        started = time.monotonic()
        deadline = started + FRAME_SECONDS
        for name, group in (('orientation', packets[:1]), ('header', packets[1:2]),
                            ('pixels', packets[2:])):
            group_start = time.monotonic()
            for packet in group:
                if time.monotonic() >= deadline:
                    raise TimeoutError()
                if port.write(packet) != len(packet):
                    raise OSError()
                if time.monotonic() >= deadline:
                    raise TimeoutError()
            timing[name] = time.monotonic() - group_start
        timing['write'] = time.monotonic() - started
        started = time.monotonic()
        drain_deadline = min(deadline, started + DRAIN_SECONDS)
        while True:
            pending = port.out_waiting
            if time.monotonic() >= drain_deadline:
                raise TimeoutError()
            if pending == 0:
                break
            if type(pending) is not int or pending < 0:
                raise ValueError()
            time.sleep(0.01)
        timing['drain'] = time.monotonic() - started
        started = time.monotonic()
        close_attempted = True
        port.close()
        timing['close'] = time.monotonic() - started
        return timing
    finally:
        if not close_attempted:
            port.close()


def arm_parent_death(expected):
    """Fail closed, including the fork-to-prctl parent death race."""
    if sys.platform != 'linux' or os.getppid() != expected:
        raise RuntimeError('Linux owned parent required')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != expected:
        raise RuntimeError('Parent ownership unavailable')


def valid_timing(value):
    return (type(value) is dict and set(value) == set(STAGES)
            and all(type(v) in (int, float) and math.isfinite(v) and v >= 0
                    for v in value.values()))


def decode_payload(payload):
    def unique(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError()
        return result
    if not payload or len(payload) > MAX_PAYLOAD:
        raise ValueError()
    # raw_decode rejects even trailing whitespace, not just extra JSON objects.
    text = payload.decode('ascii')
    value, end = json.JSONDecoder(object_pairs_hook=unique).raw_decode(text)
    if end != len(text) or not valid_timing(value):
        raise ValueError()
    return value


def child_main(write_fd, expected, port):
    code = 1
    try:
        arm_parent_death(expected)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        os.close(0)  # Never consume the operator's stdin.
        result = measure(port)
        if not valid_timing(result):
            raise ValueError()
        payload = json.dumps(result, allow_nan=False).encode('ascii')
        if len(payload) > MAX_PAYLOAD or os.write(write_fd, payload) != len(payload):
            raise ValueError()
        code = 0
    except BaseException:
        pass  # No raw exception details cross the process boundary.
    finally:
        os._exit(code)


def poll_owned(pid, ownership):
    """Commit kernel reap before a pending SIGINT can interrupt Python."""
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
    try:
        found, status = os.waitpid(pid, os.WNOHANG)
        if found == pid:
            ownership['reaped'] = True
        return status
    finally:
        # This can raise KeyboardInterrupt; ownership is already committed.
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)


def reap_stopped(pid, ownership):
    """Retain ownership through delayed kernel exit and repeated interrupts."""
    warned = False
    while not ownership['reaped']:
        try:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            poll_owned(pid, ownership)
            if ownership['reaped']:
                return
            if not warned:
                warned = True
                try:
                    print(CLEANUP, flush=True)
                except (OSError, KeyboardInterrupt):
                    pass
            time.sleep(0.01)
        except KeyboardInterrupt:
            continue


def supervise(port):
    """One owned PID, no shell/grandchildren, bounded I/O then mandatory reap."""
    read_fd = write_fd = None
    pid = None
    ownership = {'reaped': False}
    started = time.monotonic()
    try:
        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        expected = os.getpid()
        # Avoid losing the returned PID to Ctrl-C during fork assignment.
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        try:
            pid = os.fork()
            if pid == 0:
                try:
                    os.close(read_fd)
                    child_main(write_fd, expected, port)
                finally:
                    os._exit(1)
        finally:
            if pid != 0:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        os.close(write_fd)
        write_fd = None
        payload = b''
        while True:
            try:
                payload += os.read(read_fd, MAX_PAYLOAD + 1 - len(payload))
            except BlockingIOError:
                pass
            if len(payload) > MAX_PAYLOAD or time.monotonic() - started >= TOTAL_SECONDS:
                return None
            status = poll_owned(pid, ownership)
            if ownership['reaped']:
                payload += os.read(read_fd, MAX_PAYLOAD + 1 - len(payload))
                if status != 0:
                    return None
                return decode_payload(payload)
            time.sleep(0.005)
    except (Exception, KeyboardInterrupt):
        return None
    finally:
        if pid is not None and pid > 0 and not ownership['reaped']:
            reap_stopped(pid, ownership)
        for fd in (read_fd, write_fd):
            if fd is not None:
                os.close(fd)


def main(args=None, *, read=input):
    args = list(sys.argv[1:] if args is None else args)
    if args in ([], ['--help']):
        print(HELP)
        return 0
    if args not in (['--self-test'], ['--run']):
        print(INVALID)
        return 2
    try:
        baseline()  # Validate before any inventory or child admission.
        if args == ['--self-test']:
            print(SELFTEST)
            return 0
        if sys.platform != 'linux':
            raise RuntimeError()
        print(NOTICE)
        port = resolve()
        print(prompt(port), flush=True)
        try:
            answer = read()
        except (EOFError, KeyboardInterrupt):
            answer = ''
        if answer != f'SEND {port}':
            print(CANCELLED)
            return 1
        result = supervise(port)
        if not valid_timing(result):
            raise RuntimeError()
        print(report(result))
        return 0
    except (Exception, KeyboardInterrupt):
        try:
            print(FAILED)
        except (OSError, KeyboardInterrupt):
            pass
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
