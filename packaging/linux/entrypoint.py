"""Ordinary GUI entry; private dispatch belongs to the early runtime hook."""
from mars_display.app import main

if __name__ == '__main__':
    raise SystemExit(main())
