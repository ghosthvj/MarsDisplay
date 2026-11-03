"""Linux child admission, before inventory, serial or production data IPC.

The creating supervisor thread must survive until reap. PDEATHSIG is not
retroactive: READY alone grants nothing; only that supervisor may release.
After arming, the child must not exec, change credentials, or spawn children.
"""
import ctypes
import os
import re
import signal
import socket
import sys

from . import usb_ipc as ipc


def validate_nonce(nonce):
    if not isinstance(nonce, str) or re.fullmatch('[a-f0-9]{64}', nonce) is None:
        raise ValueError('Invalid USB startup admission')
    return bytes.fromhex(nonce)


def arm_parent_death(expected_parent):
    """Fail closed on wrong host/credentials, a lost parent, or failed prctl."""
    if sys.platform != 'linux' or os.getuid() == 0 or os.geteuid() == 0:
        raise RuntimeError('Non-root Linux USB helper required')
    if type(expected_parent) is not int or expected_parent <= 1 or os.getppid() != expected_parent:
        raise RuntimeError('USB creator no longer present')
    api = ctypes.CDLL(None, use_errno=True)
    api.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    api.prctl.restype = ctypes.c_int
    if api.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), 'Cannot arm USB parent death signal')
    if os.getppid() != expected_parent:
        raise RuntimeError('USB creator no longer present')


def await_admission(control_fd, nonce, expected_parent, deadline):
    """Consume/close the inherited socket on every path; return only on release.

    One absolute deadline covers arming and READY/release. No kernel scheduling
    or kill/reap latency bound is implied. This is an ownership protocol, not a
    security boundary against another process already running as the same user.
    """
    with socket.socket(fileno=control_fd) as control:
        token = validate_nonce(nonce)
        ipc._validate_deadline(deadline)
        control.getpeername()  # Reject listeners and unconnected descriptors.
        if control.type != socket.SOCK_STREAM:
            raise ValueError('Connected USB control stream required')
        arm_parent_death(expected_parent)
        ipc.send_packet(control, ipc.HELLO, 0, token, deadline)
        if ipc.receive_packet(control, deadline) != (ipc.OPEN, 1, token):
            raise ipc.ProtocolError('Invalid USB startup release')
