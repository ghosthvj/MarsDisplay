"""Opt-in internal Linux composition; does not enable application host admission."""
import sys

from .linux_usb_admission import validate_nonce
from .linux_usb_process import OwnedWorker
from .usb_transport import UsbTransport


def worker_command(port, nonce, control_fd, parent_pid, absolute_deadline):
    """Build source argv only; the Linux supervisor exclusively owns Popen."""
    validate_nonce(nonce)
    if getattr(sys, 'frozen', False):
        raise RuntimeError('Frozen Linux USB worker is not supported')
    return [sys.executable, '-m', 'mars_display.linux_usb_worker',
            '--linux-usb-worker', str(port), nonce, str(control_fd),
            str(parent_pid), str(absolute_deadline)]


def owner_factory(port, nonce, budgets, *, launcher=worker_command, gate_factory=None):
    """Accept the shared transport seam without constructing a Windows gate."""
    return OwnedWorker(port, nonce, budgets, launcher=launcher)


def create_transport(identity, *, launcher=worker_command, **options):
    """Use unchanged IPC, protocol, deadlines, cancellation and uncertainty rules."""
    return UsbTransport(identity, launcher=launcher, gate_factory=None,
                        owner_factory=owner_factory, **options)
