"""Reserved private route before PyInstaller's Qt runtime hooks; ordinary no-op."""
import sys

if any(value.startswith("--usb-worker") for value in sys.argv[1:]):
    try:
        from mars_display.usb_worker import main as worker_main
        worker_result = worker_main(sys.argv[1:])
    except BaseException:
        worker_result = 2
    raise SystemExit(worker_result)
