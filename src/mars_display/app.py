"""Ordinary GUI assembly; importing this module does not import Qt or launch I/O."""
from functools import partial
import os
import platform
import struct
import sys

from .browser import BrowserSession
from .host_platform import is_non_root_user, is_supported_host
from .lifecycle import Coordinator
from .settings import SettingsError, SettingsStore, _checked
from .transport import SimulatedTransport
from .usb_transport import UsbTransport

_UNSUPPORTED = "MarsDisplay requires Windows or Linux x64."
_NON_ROOT = "MarsDisplay requires a non-root Linux user; cannot verify safe user credentials."
_WINDOWS_TRAY = "A system tray is required; run MarsDisplay in an interactive Windows session."
_LINUX_TRAY = "A system tray is required; run MarsDisplay in an interactive Linux session."
_STARTUP_ERROR = (
    "Cannot start MarsDisplay; check the interactive system tray and settings directory access."
)


def compose_transport(context, *, native_factory=None):
    """Passive construction from one validated, frozen Start; no mode fallback."""
    settings = _checked(context.settings)
    if settings.output_mode == "native":
        factory = UsbTransport if native_factory is None else native_factory
        return factory(settings.device_identity, cancel=context.cancel)
    return SimulatedTransport()


def build_shell(app, store: SettingsStore, *, native_factory=None,
                configuration_resolver=None, windows_login=True, missing_tray_message=_WINDOWS_TRAY):
    """Compose an idle tray with an explicit store (also usable by packaging/tests).

    No platform spoofing or test flags belong to the product command. The caller
    supplies QApplication on its UI thread. Production main checks the host first;
    this helper still requires a real user-session tray. create_shell owns lock
    admission and configuration validation before this factory can run.
    """
    from PySide6.QtWidgets import QSystemTrayIcon
    from .tray import create_shell

    if not QSystemTrayIcon.isSystemTrayAvailable():
        raise RuntimeError(missing_tray_message)
    transport = (compose_transport if native_factory is None else
                 partial(compose_transport, native_factory=native_factory))
    return create_shell(app, store, lambda: Coordinator(
        store, BrowserSession, transport_context_factory=transport,
        configuration_resolver=configuration_resolver),
        windows_login=windows_login)


def main() -> int:
    """Run the tray application. All reported startup errors omit private values."""
    if not is_supported_host(sys.platform, platform.machine(), struct.calcsize("P")):
        print(_UNSUPPORTED, file=sys.stderr)
        return 1
    linux = sys.platform == "linux"
    if linux:
        try:
            safe_user = is_non_root_user(os.getuid(), os.geteuid())
        except Exception:
            safe_user = False
        if not safe_user:
            print(_NON_ROOT, file=sys.stderr)
            return 1
    missing_tray_message = _LINUX_TRAY if linux else _WINDOWS_TRAY
    try:
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon

        app = QApplication(sys.argv)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print(missing_tray_message, file=sys.stderr)
            return 1
        if linux:
            from .linux_paths import linux_settings_path
            from .linux_usb_transport import create_transport
            from .linux_usb_worker import resolve

            store = SettingsStore(linux_settings_path())
            shell = build_shell(app, store, native_factory=create_transport,
                                configuration_resolver=resolve, windows_login=False, missing_tray_message=missing_tray_message)
        else:
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
