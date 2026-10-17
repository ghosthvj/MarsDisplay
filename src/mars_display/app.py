"""Ordinary GUI assembly; importing this module does not import Qt or launch I/O."""
import platform
import struct
import sys

from .browser import BrowserSession
from .lifecycle import Coordinator
from .settings import SettingsError, SettingsStore
from .transport import SimulatedTransport

_UNSUPPORTED = "MarsDisplay requires Windows x64; use Windows 11 x64."
_STARTUP_ERROR = (
    "Cannot start MarsDisplay; check the interactive system tray and settings directory access."
)


def build_shell(app, store: SettingsStore):
    """Compose an idle tray with an explicit store (also usable by packaging/tests).

    No platform spoofing or test flags belong to the product command. The caller
    supplies QApplication on its UI thread. Production main checks the host first;
    this helper still requires a real user-session tray. create_shell owns lock
    admission and configuration validation before this factory can run.
    """
    from PySide6.QtWidgets import QSystemTrayIcon
    from .tray import create_shell

    if not QSystemTrayIcon.isSystemTrayAvailable():
        raise RuntimeError(
            "A system tray is required; run MarsDisplay in an interactive Windows session."
        )
    return create_shell(app, store, lambda: Coordinator(
        store, BrowserSession, SimulatedTransport))


def main() -> int:
    """Run the tray application. All reported startup errors omit private values."""
    if (sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}
            or struct.calcsize("P") != 8):
        print(_UNSUPPORTED, file=sys.stderr)
        return 1
    try:
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon

        app = QApplication(sys.argv)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("A system tray is required; run MarsDisplay in an interactive Windows session.",
                  file=sys.stderr)
            return 1
        store = SettingsStore()
        shell = build_shell(app, store)
    except SettingsError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print(_STARTUP_ERROR, file=sys.stderr)
        return 1
    if shell is None:
        print("MarsDisplay is already running.", file=sys.stderr)
        return 0
    # Keep shell/guard alive across exec. Only the shell's acknowledged Exit
    # releases ownership. An external quit must not report a successful Exit or
    # abandon a live worker; reuse the shell's existing cleanup polling.
    result = app.exec()
    if not shell.coordinator.snapshot().exit_ready:
        print("Application event loop ended unexpectedly; waiting for owned cleanup.",
              file=sys.stderr)
        shell.coordinator.request_exit()
        shell.refresh()
        while not shell.coordinator.snapshot().exit_ready:
            app.exec()
        return 1
    return result
