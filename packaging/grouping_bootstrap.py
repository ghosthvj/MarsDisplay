"""Experiment-only early route, before PyInstaller's Qt runtime hooks."""
import sys


def dispatch():
    args = sys.argv[1:]
    if any(value.startswith(('--usb-worker', '--grouping-worker')) for value in args):
        result = 2
        if not any(value.startswith('--usb-worker') for value in args):
            try:
                from mars_display.usb_grouping_worker import main
                result = main(args)
            except BaseException:
                result = 2
        raise SystemExit(result)
    if args != ['--run']:
        from mars_display.usb_grouping_experiment import main
        raise SystemExit(main(args))


dispatch()
