"""Linux private runtime hook, to precede Qt/default GUI runtime hooks."""
import sys

args = sys.argv[1:]
reserved = ('--linux-usb-worker', '--usb-worker')
if any(value.startswith(reserved) for value in args):
    result = 2
    if (len(args) == 6 and args[0] == '--linux-usb-worker'
            and not any(value.startswith(reserved) for value in args[1:])):
        try:
            from mars_display.linux_usb_worker import main
            result = main(args)
        except BaseException:
            result = 2
    raise SystemExit(result)
