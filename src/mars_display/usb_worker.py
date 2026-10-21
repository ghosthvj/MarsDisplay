"""Persistent serial worker core. Process admission is supplied by its owner."""
import re
import time

from . import usb_ipc as ipc
from .devices import enumerate_devices, select_device
from .usb_protocol import encode_portrait

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
                clock=time.monotonic, sleep=time.sleep):
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
                elif kind == ipc.FRAME:
                    if port is None:
                        raise ValueError('USB session is not open')
                    frame = ipc.decode_frame(body)
                    status = IDENTITY_ERROR
                    if _resolve(inventory) != selected:
                        raise ValueError('Current USB port changed')
                    status = WRITE_ERROR
                    deadline = clock() + budgets.frame
                    for packet in encode_portrait(frame):
                        if clock() >= deadline:
                            raise TimeoutError('USB frame deadline exceeded')
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
