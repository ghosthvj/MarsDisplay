"""Console entry point shared by source launches and the future frozen build."""
from mars_display.usb_probe import main

if __name__ == '__main__':
    raise SystemExit(main())
