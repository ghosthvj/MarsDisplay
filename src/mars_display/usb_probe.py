"""Standalone fixed-image diagnostic core; no import-time device or file I/O."""
import hashlib
import os
from pathlib import Path
import re
import sys
import time

from .devices import enumerate_devices, select_device
from .frames import RGBFrame
from .usb_protocol import encode_portrait

VERSION = '1.0.0'
IDENTITY = 'usb:1a86:5722:USB35INCHIPSV2'
HELP = '''Mars Display Python USB Probe 1.0.0
Usage: probe [--help | --self-test | --list | --port COMn]
No arguments: prompt for a current uppercase COM port.
--help       Show this USB-free help.
--self-test  Verify the fixed image and encoder without USB.
--list       List passive USB descriptors (Windows only).
--port COMn  Confirm SEND COMn, recheck identity, send one fixed image.
Completion is host transfer completion, not a rendering ACK. Never auto-resend.
'''
SELF_TEST_OK = 'Self-test passed: 122 packets, 307222 bytes; no USB access.\n'
SUCCESS = 'Host transfer complete: 122 packets, 307222 bytes; not a rendering ACK.\n'
CANCELLED = 'Cancelled; no device opened.\n'
PORT_PROMPT = 'Current uppercase COM port (empty to cancel): '
ERRORS = {
    2: 'Invalid arguments; use --help.',
    3: 'Cannot list USB serial descriptors; no transfer started.',
    4: 'Current COM port must uniquely match the known USB identity; no device opened.',
    5: 'Fixed image verification failed; no device opened.',
    6: 'Transfer failed; delivery uncertain. Do not automatically resend.',
    7: 'Worker or Windows isolation failed; delivery uncertain. Do not automatically resend.',
    8: 'Worker timed out and was stopped; delivery uncertain. Do not automatically resend.',
}


def confirmation(port):
    return f'Type SEND {port} to send the fixed image: '


def parse_args(args):
    """Reject every private/unknown/combined option before performing I/O."""
    if not args:
        return 'interactive', None
    if len(args) == 1 and args[0] in ('--help', '--self-test', '--list'):
        return args[0][2:], None
    if len(args) == 2 and args[0] == '--port' and re.fullmatch(r'COM[1-9][0-9]*', args[1]):
        return 'port', args[1]
    raise ValueError


def load_raw():
    root = (Path(sys._MEIPASS) / 'probe-assets' if getattr(sys, 'frozen', False)
            else Path(__file__).resolve().parents[2] / 'tools/windows-usb-probe')
    with (root / 'pattern.rgb888').open('rb') as fixture:
        return fixture.read(460801)


def load_packets(raw_loader=None):
    raw = (raw_loader or load_raw)()
    if len(raw) != 460800 or hashlib.sha256(raw).hexdigest() != '19edb4162586afb859c062b82a4c26b54d7329dc3303205628ad61ab1558ef40':
        raise ValueError
    packets = encode_portrait(RGBFrame(320, 480, raw, 0))
    if hashlib.sha256(b''.join(packets[2:])).hexdigest() != '8cbbb7e39485e211548a4f3f448ca14eeb9358286e5eadf7079a324fdc97ed1d':
        raise ValueError
    return packets


def serial_factory(**options):
    from serial import Serial
    return Serial(**options)


def _selected(snapshot, port):
    selected = select_device(snapshot, IDENTITY)
    occupants = [item for item in snapshot if item.device.upper() == port]
    if selected.device != port or occupants != [selected]:
        raise ValueError


def _transfer(packets, port_name, factory, clock, sleep):
    port = None
    failed = False
    try:
        port = factory(port=None, baudrate=115200, bytesize=8, parity='N', stopbits=1,
                       rtscts=True, dsrdtr=False, write_timeout=3, timeout=1)
        port.dtr = True
        port.port = port_name
        port.open()
        for packet in packets:
            if port.write(packet) != len(packet):
                raise OSError
        deadline = clock() + 15
        while port.out_waiting:
            if clock() >= deadline:
                raise TimeoutError
            sleep(0.01)
    except (Exception, KeyboardInterrupt):
        failed = True
    finally:
        if port is not None:
            try:
                port.close()
            except Exception:
                failed = True
    return not failed


def run(args, *, stdin=None, stdout=None, stderr=None, inventory=enumerate_devices,
        serial_factory=serial_factory, raw_loader=None, clock=time.monotonic, sleep=time.sleep):
    """Guarded core for an already isolated worker or explicit injected tests.

    Production callers must use main(), which supplies the owned-process boundary.
    """
    stdin, stdout, stderr = (stdin if stdin is not None else sys.stdin,
                             stdout if stdout is not None else sys.stdout,
                             stderr if stderr is not None else sys.stderr)
    def fail(code):
        stderr.write(ERRORS[code] + '\n')
        return code
    def prompt(text):
        stdout.write(text)
        stdout.flush()
        return stdin.readline().rstrip('\r\n')
    try:
        mode, port = parse_args(args)
    except ValueError:
        return fail(2)
    if mode == 'help':
        stdout.write(HELP)
        return 0
    try:
        packets = load_packets(raw_loader)
    except Exception:
        return fail(5)
    if mode == 'self-test':
        stdout.write(SELF_TEST_OK)
        return 0
    if mode == 'interactive':
        port = prompt(PORT_PROMPT)
        if not port:
            stdout.write(CANCELLED)
            return 0
        if not re.fullmatch(r'COM[1-9][0-9]*', port):
            return fail(2)
    try:
        snapshot = inventory()
    except Exception:
        return fail(3)
    if mode == 'list':
        for item in snapshot:
            stdout.write(f'{item.device} {item.identity or "(no stable identity)"}\n')
        return 0
    try:
        _selected(snapshot, port)
    except Exception:
        return fail(4)
    if prompt(confirmation(port)) != f'SEND {port}':
        stdout.write(CANCELLED)
        return 0
    try:
        snapshot = inventory()
    except Exception:
        return fail(3)
    try:
        _selected(snapshot, port)
    except Exception:
        return fail(4)
    if not _transfer(packets, port, serial_factory, clock, sleep):
        return fail(6)
    stdout.write(SUCCESS)
    return 0


def main(args=None):
    from .usb_probe_process import MARKER, consume_marker, await_gate, supervise
    args = list(sys.argv[1:] if args is None else args)
    try:
        mode, _ = parse_args(args)
    except ValueError:
        consume_marker()
        sys.stderr.write(ERRORS[2] + '\n')
        return 2
    had_marker = MARKER in os.environ
    marker = consume_marker()
    if had_marker and marker is None:
        sys.stderr.write(ERRORS[7] + '\n')
        return 7
    if marker is not None:
        if not await_gate(marker):
            sys.stderr.write(ERRORS[7] + '\n')
            return 7
        try:
            return run(args)
        except (Exception, KeyboardInterrupt):
            sys.stderr.write(ERRORS[7] + '\n')
            return 7
    if mode in ('help', 'self-test'):
        return run(args)
    code = supervise(args)
    if code in (7, 8):
        sys.stderr.write(ERRORS[code] + '\n')
    # Parent-only console usability; the owned child has already finished.
    # This final human pause is outside the 90-second child budget.
    if not args and sys.stdin.isatty():
        try:
            input('Press Enter to close.')
        except (EOFError, KeyboardInterrupt):
            pass
    return code
