"""Immutable, tightly packed RGB888 frames with explicit capture times."""

from dataclasses import dataclass
from math import isfinite


def _validate_frame(frame: "RGBFrame") -> None:
    if type(frame.width) is not int or type(frame.height) is not int:
        raise TypeError("width and height must be integers")
    if (frame.width, frame.height) not in ((320, 480), (480, 320)):
        raise ValueError("geometry must be 320x480 or 480x320")
    if not isinstance(frame.rgb, bytes):
        raise TypeError("rgb must be bytes")
    if len(frame.rgb) != frame.width * frame.height * 3:
        raise ValueError("rgb length must equal width * height * 3")
    if type(frame.captured_at) not in (int, float):
        raise TypeError("captured_at must be a number")
    try:
        valid_time = isfinite(frame.captured_at) and frame.captured_at >= 0
    except OverflowError:
        valid_time = False
    if not valid_time:
        raise ValueError("captured_at must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class RGBFrame:
    """Top-to-bottom RGB rows, no padding; captured_at is monotonic seconds.

    The caller supplies a finite, non-negative capture timestamp. No wall clock
    is consulted, and delivery order does not depend on timestamp ordering.
    """

    width: int
    height: int
    rgb: bytes
    captured_at: float

    def __post_init__(self) -> None:
        _validate_frame(self)
