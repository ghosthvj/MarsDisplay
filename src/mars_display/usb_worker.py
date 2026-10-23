"""Persistent serial worker core. Process admission is supplied by its owner."""
import re
import time

from . import usb_ipc as ipc
from .devices import enumerate_devices, select_device
from .usb_protocol import encode_brightness, encode_portrait

IDENTITY = 'usb:1a86:5722:USB35INCHIPSV2'
OK, IDENTITY_ERROR, INVALID, OPEN_ERROR, WRITE_ERROR, DRAIN_ERROR, CLOSE_ERROR = range(7)


def serial_factory(**options):
    from serial import Serial
    return Serial(**options)


def _resolve(inventory):
    snapshot = inventory()
    selected = select_device(snapshot, IDENTITY)
    if not isinstance(selected.device, str) or not re.fullmatch(r'COM[1-9][0-9]*', selected.device):
        raise ValueError('Unsupported current USB port')
    occupants = [item for item in snapshot if item.device.upper() == selected.device.upper()]
    if occupants != [selected]:
        raise ValueError('Ambiguous current USB port')
    return selected.device


def run_session(channel, nonce, *, inventory=enumerate_devices,
                port_factory=serial_factory, budgets=ipc.Budgets(),
                clock=time.monotonic, sleep=time.sleep, timing_clock=time.monotonic,
                encoder=encode_portrait):
    """Serve one already-admitted channel; injection is Python-only, never CLI.

    The parent must bound blocking native calls by owning/terminating this worker
    process. Replies contain fixed status bytes, not exceptions or frame history.
    """
    if not isinstance(nonce, bytes) or len(nonce) != 32:
        raise ValueError('Invalid USB session nonce')
    port, selected, previous, close_attempted = None, None, 0, False

    def reply(request, status):
        ipc.send_packet(channel, ipc.REPLY, request, bytes([status]),
                        time.monotonic() + budgets.start)

    try:
        ipc.send_packet(channel, ipc.HELLO, 0, nonce, time.monotonic() + budgets.start)
        while True:
            kind, request, body = ipc.receive_packet(channel)
            status = INVALID
            try:
                if request != previous + 1:
                    raise ValueError('Unexpected USB request')
                previous = request
                if kind == ipc.OPEN:
                    if port is not None:
                        raise ValueError('USB session already opened')
                    status = IDENTITY_ERROR
                    if body != IDENTITY.encode('ascii'):
                        raise ValueError('Unsupported USB identity')
                    selected = _resolve(inventory)
                    status = OPEN_ERROR
                    port = port_factory(port=None, baudrate=115200, bytesize=8,
                                        parity='N', stopbits=1, rtscts=True,
                                        dsrdtr=False, write_timeout=budgets.write, timeout=1)
                    port.dtr = True
                    port.port = selected
                    port.open()
                elif kind in (ipc.FRAME, ipc.TIMED_FRAME, ipc.GROUPED_FRAME):
                    if port is None:
                        raise ValueError('USB session is not open')
                    # Legacy operations do not consult the diagnostic clock.
                    grouped = kind == ipc.GROUPED_FRAME
                    measure = timing_clock if kind != ipc.FRAME else lambda: 0
                    started = measure()
                    frame = ipc.decode_frame(body)
                    decode = measure() - started
                    status = IDENTITY_ERROR
                    started = measure()
                    if _resolve(inventory) != selected:
                        raise ValueError('Current USB port changed')
                    identity = measure() - started
                    status = WRITE_ERROR
                    deadline = clock() + budgets.frame
                    started = measure()
                    packets = encoder(frame)
                    encode = measure() - started
                    started = measure()
                    for index, packet in enumerate(packets):
                        if grouped and index < 3:
                            group_started = measure()
                        if clock() >= deadline:
                            raise TimeoutError('USB frame deadline exceeded')
                        if port.write(packet) != len(packet):
                            raise OSError('USB write failed')
                        if grouped:
                            if index == 0:
                                orientation = measure() - group_started
                            elif index == 1:
                                header = measure() - group_started
                            elif index == len(packets) - 1:
                                pixels = measure() - group_started
                    write = measure() - started
                    status = DRAIN_ERROR
                    deadline = min(deadline, clock() + budgets.drain)
                    started = measure()
                    while port.out_waiting:
                        if clock() >= deadline:
                            raise TimeoutError('USB queue drain exceeded')
                        sleep(0.01)
                    drain = measure() - started
                    if kind != ipc.FRAME:
                        groups = ipc.WriteTiming(orientation, header, pixels) if grouped else None
                        detail = ipc.WorkerTiming(decode, identity, encode, write, drain, groups=groups)
                        reply_kind = ipc.GROUPED_REPLY if grouped else ipc.TIMED_REPLY
                        payload = ipc.encode_grouped_timing(detail) if grouped else ipc.encode_timing(detail)
                        ipc.send_packet(channel, reply_kind, request,
                                        payload, time.monotonic() + budgets.start)
                        continue
                elif kind == ipc.BRIGHTNESS:
                    if port is None:
                        raise ValueError('USB session is not open')
                    packet = encode_brightness(body[0])
                    status = IDENTITY_ERROR
                    if _resolve(inventory) != selected:
                        raise ValueError('Current USB port changed')
                    status = WRITE_ERROR
                    deadline = clock() + budgets.frame
                    if clock() >= deadline:
                        raise TimeoutError('USB brightness deadline exceeded')
                    if port.write(packet) != len(packet):
                        raise OSError('USB write failed')
                    status = DRAIN_ERROR
                    deadline = min(deadline, clock() + budgets.drain)
                    while port.out_waiting:
                        if clock() >= deadline:
                            raise TimeoutError('USB queue drain exceeded')
                        sleep(0.01)
                elif kind == ipc.CLOSE:
                    status = CLOSE_ERROR
                    if port is not None:
                        close_attempted = True
                        port.close()
                    reply(request, OK)
                    return 0
                else:
                    raise ValueError('Unsupported worker request')
                reply(request, OK)
            except (Exception, KeyboardInterrupt):
                reply(request, status)
                return 1
    except (Exception, KeyboardInterrupt):
        return 1
    finally:
        if port is not None and not close_attempted:
            try:
                port.close()
            except Exception:
                # Process ownership/reap, not this return code, establishes
                # cleanup certainty. Never retry a frame or leak native details.
                pass


def main(args=None):
    """Reserved source/frozen route; no GUI, dialogs or raw error reporting."""
    import socket
    import sys
    from .usb_process import await_admission
    args = list(sys.argv[1:] if args is None else args)
    if (len(args) != 3 or args[0] != '--usb-worker'
            or not re.fullmatch(r'[1-9][0-9]{0,4}', args[1])
            or int(args[1]) > 65535 or not re.fullmatch('[a-f0-9]{64}', args[2])):
        return 2
    forbidden = ('mars_display.app', 'mars_display.settings', 'PySide6.QtCore',
                 'PySide6.QtGui', 'PySide6.QtWidgets')
    if any(name in sys.modules for name in forbidden):
        return 2
    try:
        if not await_admission(args[2]):
            return 2
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as channel:
            channel.settimeout(5)
            channel.connect(('127.0.0.1', int(args[1])))
            return run_session(channel, bytes.fromhex(args[2]))
    except BaseException:
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
