"""Windowed bootstrap, intentionally independent of Qt until reporting is ready."""
import ctypes
import io
import sys
from contextlib import redirect_stderr, redirect_stdout

SAFE_FAILURE = 'Cannot start MarsDisplay; check the application runtime and try again.'


def message_box(message, error):
    """Temporary native dialog; no extra GUI framework or permanent window."""
    ctypes.windll.user32.MessageBoxW(None, message, 'MarsDisplay', 0x10 if error else 0x40)


def run(main=None, reporter=message_box):
    """Capture trusted app.main diagnostics, preserve its return/cleanup semantics.

    Only app.main's sanitized stderr is reportable. Unexpected failures discard
    all captured output; raw import/exception details must never reach a dialog.
    Streams are restored before invoking native reporting, even on failure.
    """
    arguments = list(sys.argv[1:])
    if any(value.startswith('--usb-worker') for value in arguments):
        # Reserved admission failure must never fall through to GUI/reporting.
        try:
            from mars_display.usb_worker import main as worker_main
            return worker_main(arguments)
        except BaseException:
            return 2
    output, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(errors):
        try:
            if main is None:
                from mars_display.app import main
            result = main()
            message = errors.getvalue().strip()
        except Exception:
            result, message = 1, SAFE_FAILURE
    if message:
        reporter(message, result != 0)
    return result


if __name__ == '__main__':
    sys.exit(run())
