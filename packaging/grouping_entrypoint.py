"""Separate console executable; never routes to mars_display.app."""
import grouping_bootstrap  # Also protects direct source execution.
from mars_display.usb_grouping_experiment import main

raise SystemExit(main())
