"""Scoped theme density stays compact; no Qt widgets, no I/O."""

import re
import unittest

from mars_display.presentation import window_stylesheet

FONT_SIZE = re.compile(r"font-size:\s*(\d+)px")
PADDING = re.compile(r"padding:\s*(\d+)px(?:\s+(\d+)px)?;")

BASE_FONT_CEILING = 12
LARGEST_FONT_CEILING = 21
CONTROL_VERTICAL_PADDING_CEILING = 8
CONTROL_HORIZONTAL_PADDING_CEILING = 14


def block(sheet, selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", sheet)
    if match is None:
        raise AssertionError(f"Missing theme block: {selector}")
    return match.group(1)


class CompactDensityTests(unittest.TestCase):
    def test_base_text_and_headings_stay_compact_in_both_themes(self):
        for dark in (False, True):
            sheet = window_stylesheet(dark)
            base = FONT_SIZE.search(block(sheet, "QWidget"))
            self.assertIsNotNone(base, "The theme must set one base text size")
            self.assertLessEqual(int(base.group(1)), BASE_FONT_CEILING,
                                 f"Base text grew past the compact density (dark={dark})")
            sizes = [int(value) for value in FONT_SIZE.findall(sheet)]
            self.assertLessEqual(max(sizes), LARGEST_FONT_CEILING,
                                 f"A heading or value grew past the compact density (dark={dark})")

    def test_controls_keep_compact_padding(self):
        for dark in (False, True):
            sheet = window_stylesheet(dark)
            for selector in ("QPushButton", "QLineEdit", "QComboBox", "QLabel#sourceBadge"):
                padding = PADDING.search(block(sheet, selector))
                self.assertIsNotNone(padding, f"{selector} must declare padding (dark={dark})")
                vertical = int(padding.group(1))
                horizontal = int(padding.group(2) or padding.group(1))
                self.assertLessEqual(vertical, CONTROL_VERTICAL_PADDING_CEILING,
                                     f"{selector} vertical padding grew (dark={dark})")
                self.assertLessEqual(horizontal, CONTROL_HORIZONTAL_PADDING_CEILING,
                                     f"{selector} horizontal padding grew (dark={dark})")

    def test_dark_and_light_keep_distinct_palettes(self):
        self.assertNotEqual(window_stylesheet(True), window_stylesheet(False))


if __name__ == "__main__":
    unittest.main()
