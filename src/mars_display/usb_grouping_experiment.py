"""Opt-in, fixed public-pattern experiment. Importing this module is Qt-free."""
import os
import subprocess
import sys
import time

from .devices import enumerate_devices
from .usb_grouping_profile import load_fixture, fixed_encoder
from .usb_worker import IDENTITY, _resolve
from .usb_transport import UsbTransport

HELP = '''MarsDisplay isolated USB grouping experiment
Usage: python -m mars_display.usb_grouping_experiment [--help | --self-test | --run]
No arguments: help only. --self-test: fixed public fixture, no device access.
--run: explicit opt-in; close MarsDisplay and all vendor/probe software first.
A: 122 writes (120 x 2560 payload); B: 62 writes (60 x 5120 payload).
Each sends one identical 307222-byte stream. No retry or repeat.
Both arms open/send/close separately; opening/closing can toggle DTR.
Type the displayed arm and COM port exactly; default/EOF cancels.
B requires A host success, known cleanup, A VALID visual approval, and fresh COM confirmation.
Timings are host-side, overlapping, and do not prove panel acknowledgement.'''
INVALID = 'Invalid arguments. Use --help; no device access.'
SELFTEST = 'Self-test OK: fixed public fixture; A=122 B=62 writes; identical 307222 bytes; no device access.'
NOTICE = ('Close MarsDisplay and all vendor/probe software before continuing.\n'
          'Both arms open/send/close separately; opening/closing can toggle DTR.\n'
          'One frame per arm; no retry. Host timings overlap, not panel acknowledgement.')
BUSY = 'MarsDisplay instance lock unavailable; no device access.'
CANCELLED = 'Cancelled; no further frames.'
VISUAL = 'Inspect A on the physical display. Type A VALID only if the image is correct; otherwise cancel:'
FAILED = 'Experiment failed; no further frames. No automatic retry.'
CLEANUP = 'Cleanup uncertain; retaining instance lock and retrying cleanup only. Do not restart MarsDisplay.'
DONE = 'Experiment complete. Report host numbers and physical image correctness for both arms.'


def make_guard():
    # Constructor only: no settings load/write. Reuse the actual app guard,
    # including its default path validation and dead-process-only stale policy.
    from .settings import SettingsStore
    from .tray import SingleInstanceGuard
    return SingleInstanceGuard(SettingsStore())


def worker_command(arm, com, port, nonce):
    from .usb_grouping_worker import valid_arguments
    args = ['--grouping-worker', arm, com, str(port), nonce]
    if not valid_arguments(args):
        raise ValueError('Invalid experiment invocation')
    if getattr(sys, 'frozen', False):
        return [sys.executable, *args]
    return [sys.executable, '-m', 'mars_display.usb_grouping_worker', *args]


def make_transport(arm, com):
    def launch(port, nonce):
        return subprocess.Popen(worker_command(arm, com, port, nonce),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True, shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return UsbTransport(IDENTITY, launcher=launch)


def prompt(arm, com):
    return f'Current unique port: {com}. Type {arm} {com} to send one frame; otherwise cancel:'


def report(arm, timing):
    text = f'{arm}: host send and cleanup OK; writes={122 if arm == "A" else 62}; bytes=307222'
    if timing is not None:
        for name in ('body_encode', 'exchange', 'decode', 'identity', 'encode', 'write', 'drain'):
            text += f'; {name}_ms={getattr(timing, name)*1000:.3f}'
        if timing.groups is not None:
            for name in ('orientation', 'header', 'pixels'):
                text += f'; {name}_ms={getattr(timing.groups, name)*1000:.3f}'
    return text


def _confirm(read, message, expected):
    print(message, flush=True)
    try:
        return read() == expected
    except (EOFError, KeyboardInterrupt):
        return False


def _retain_until_closed(transport):
    """Never return ownership uncertainty to an exiting console/lock destructor.

    Cleanup only; no reconnect/resend. Even EOF/Ctrl-C cannot release exclusion
    while an owned launcher, child or native handle may still be live.
    """
    if transport is None or not transport.owned:
        return
    try:
        print(CLEANUP, flush=True)
    except (Exception, KeyboardInterrupt):
        pass  # A broken console must not abandon owned resources or exclusion.
    while transport.owned:
        try:
            time.sleep(0.25)
            transport.close()
        except (Exception, KeyboardInterrupt):
            pass


def main(args=None, *, read=None):
    args = list(sys.argv[1:] if args is None else args)
    read = input if read is None else read
    if args in ([], ['--help']):
        print(HELP)
        return 0
    if args not in (['--self-test'], ['--run']):
        print(INVALID)
        return 2
    guard, transport, held = None, None, False
    try:
        fixture = load_fixture()  # Integrity before any inventory, lock or device I/O.
        a, b = (fixed_encoder(arm, fixture)(fixture) for arm in ('A', 'B'))
        if (list(map(len, a)) != [16, 6] + [2560]*120 or
                list(map(len, b)) != [16, 6] + [5120]*60 or
                b''.join(a) != b''.join(b) or sum(map(len, a)) != 307222):
            raise ValueError('Invalid experiment stream')
        if args == ['--self-test']:
            print(SELFTEST)
            return 0
        guard = make_guard()
        held = guard.acquire()
        if not held:
            print(BUSY)
            return 3
        print(NOTICE, flush=True)
        for arm in ('A', 'B'):
            com = _resolve(enumerate_devices)
            if not _confirm(read, prompt(arm, com), f'{arm} {com}'):
                print(CANCELLED)
                return 1
            transport = make_transport(arm, com)
            try:
                transport.open()
                transport.send(fixture)
            finally:
                transport.close()
            if transport.owned:
                raise RuntimeError('Cleanup remains uncertain')
            print(report(arm, transport.last_send_timing), flush=True)
            if arm == 'A' and not _confirm(read, VISUAL, 'A VALID'):
                print(CANCELLED)
                return 1
        print(DONE)
        return 0
    except (Exception, KeyboardInterrupt):
        try:
            print(FAILED, flush=True)
        except (Exception, KeyboardInterrupt):
            pass
        return 4
    finally:
        _retain_until_closed(transport)
        if held:
            guard.release()


if __name__ == '__main__':
    raise SystemExit(main())
