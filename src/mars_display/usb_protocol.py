"""Pure encoding for the proven 320x480 portrait USB display profile."""

from .frames import RGBFrame, _validate_frame


def encode_brightness(percent: int) -> bytes:
    """Encode only the five supported RevA brightness levels, without I/O."""
    if type(percent) is not int or percent not in (20, 40, 60, 80, 100):
        raise ValueError('USB brightness must be an integer in 20, 40, 60, 80, 100')
    # Equivalent to int(255 - ((percent / 100) * 255)) for these five levels.
    absolute = 255 - percent * 255 // 100
    return bytes((absolute >> 2, (absolute & 3) << 6, 0, 0, 0, 0x6E))


def encode_portrait(frame: RGBFrame) -> tuple[bytes, ...]:
    """Return orientation, header and 120 RGB565LE chunks without any I/O.

    RGB channels are truncated, not rounded. Shared frame validation runs
    before the portrait-only geometry check; the caller's frame is unchanged.
    """
    if not isinstance(frame, RGBFrame):
        raise TypeError("frame must be an RGBFrame")
    _validate_frame(frame)
    if (frame.width, frame.height) != (320, 480):
        raise ValueError("portrait encoding requires 320x480 geometry")

    payload = bytearray(320 * 480 * 2)
    for source in range(0, len(frame.rgb), 3):
        red, green, blue = frame.rgb[source:source + 3]
        word = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
        target = (source // 3) * 2
        payload[target] = word & 0xFF
        payload[target + 1] = word >> 8

    return (
        bytes.fromhex("00 00 00 00 00 79 64 01 40 01 E0 00 00 00 00 00"),
        bytes.fromhex("00 00 04 FD DF C5"),
        *(bytes(payload[start:start + 2560])
          for start in range(0, len(payload), 2560)),
    )
