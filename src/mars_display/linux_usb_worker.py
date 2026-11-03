"""Private source-only Linux worker. Importing this module has no device effects."""
import os
import re
import socket
import sys
import time

from . import usb_ipc as ipc
from .devices import enumerate_devices, select_device
from .linux_usb_admission import await_admission, validate_nonce
from .usb_worker import IDENTITY, run_session, serial_factory


def resolve(inventory):
    """Select one exact identity and one observed occupant, never a tty fallback."""
    snapshot = tuple(inventory())
    selected = select_device(snapshot, IDENTITY)
    if not isinstance(selected.device, str) or not re.fullmatch(r'/dev/ttyACM[0-9]+', selected.device):
        raise ValueError('Unsupported current USB port')
    if [item for item in snapshot if item.device == selected.device] != [selected]:
        raise ValueError('Ambiguous current USB port')
    return selected.device


class _Serial:
    """Exclusive serial delegate with a fresh post-open identity observation."""
    def __init__(self, native, inventory):
        self.native, self.inventory = native, inventory
        self.closed = False

    @property
    def port(self):
        return self.native.port

    @port.setter
    def port(self, value):
        self.native.port = value

    @property
    def dtr(self):
        return self.native.dtr

    @dtr.setter
    def dtr(self, value):
        self.native.dtr = value

    def open(self):
        try:
            self.native.open()
            if resolve(self.inventory) != self.port:
                raise ValueError('Current USB port changed')
        except BaseException:
            self.close()
            raise

    def write(self, data):
        return self.native.write(data)

    @property
    def out_waiting(self):
        return self.native.out_waiting

    def close(self):
        if not self.closed:
            self.native.close()
            self.closed = True


def serial_adapter(inventory, factory=serial_factory):
    """Python-only injection; pyserial is loaded lazily by the shared factory."""
    def create(**options):
        options['exclusive'] = True
        return _Serial(factory(**options), inventory)
    return create


def main(args=None, *, inventory=enumerate_devices, port_factory=serial_factory):
    """Quiet private route; inherited supervisor release precedes all data IPC.

    Kept callable for a future early frozen bootstrap, but frozen execution is
    deliberately rejected until that bootstrap's guard contract is implemented.
    """
    try:
        args = list(sys.argv[1:] if args is None else args)
        if (sys.platform != 'linux' or getattr(sys, 'frozen', False)
                or os.getuid() == 0 or os.geteuid() == 0):
            return 2
        forbidden = ('mars_display.app', 'mars_display.settings', 'PySide6.QtCore',
                     'PySide6.QtGui', 'PySide6.QtWidgets')
        if any(name in sys.modules for name in forbidden):
            return 2
        if (len(args) != 6 or args[0] != '--linux-usb-worker'
                or not re.fullmatch(r'[1-9][0-9]{0,4}', args[1])
                or int(args[1]) > 65535
                or not re.fullmatch(r'[0-9]+', args[3])
                or not re.fullmatch(r'[1-9][0-9]*', args[4])):
            return 2
        token = validate_nonce(args[2])
        fd, parent, deadline = int(args[3]), int(args[4]), float(args[5])
        ipc._validate_deadline(deadline)
        if fd < 3 or parent <= 1 or parent != os.getppid() or deadline <= time.monotonic():
            return 2
        os.fstat(fd)  # Must already exist; admission validates the connected stream.
        await_admission(fd, args[2], parent, deadline)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as channel:
            channel.settimeout(max(.001, deadline - time.monotonic()))
            channel.connect(('127.0.0.1', int(args[1])))
            return run_session(channel, token, inventory=inventory, resolver=resolve,
                               port_factory=serial_adapter(inventory, port_factory))
    except BaseException:
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
