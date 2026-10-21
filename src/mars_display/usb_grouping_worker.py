"""Private fixed-profile bootstrap: reject before admission/socket/device/Qt."""
import re
import socket
import sys

from .devices import enumerate_devices
from .usb_process import await_admission
from .usb_worker import _resolve, run_session


def valid_arguments(args):
    return (len(args) == 5 and args[0] == '--grouping-worker'
            and args[1] in ('A', 'B')
            and re.fullmatch(r'COM[1-9][0-9]*', args[2]) is not None
            and re.fullmatch(r'[1-9][0-9]{0,4}', args[3]) is not None
            and int(args[3]) <= 65535
            and re.fullmatch('[a-f0-9]{64}', args[4]) is not None)


def confirmed_inventory(com):
    snapshot = enumerate_devices()
    if _resolve(lambda: snapshot) != com:
        raise ValueError('Confirmed USB port changed')
    return snapshot


def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    if not valid_arguments(args):
        return 2
    forbidden = ('mars_display.app', 'mars_display.settings', 'PySide6.QtCore',
                 'PySide6.QtGui', 'PySide6.QtWidgets')
    if any(name in sys.modules for name in forbidden):
        return 2
    try:
        if not await_admission(args[4]):
            return 2
        from .usb_grouping_profile import load_fixture, fixed_encoder
        encoder = fixed_encoder(args[1], load_fixture())
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as channel:
            channel.settimeout(5)
            channel.connect(('127.0.0.1', int(args[3])))
            return run_session(channel, bytes.fromhex(args[4]),
                inventory=lambda: confirmed_inventory(args[2]), encoder=encoder)
    except BaseException:
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
