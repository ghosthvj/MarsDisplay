"""Qt-free fixed public fixture and two trusted experiment encoders."""
import hashlib
from pathlib import Path
import sys

from .frames import RGBFrame
from .usb_protocol import encode_portrait

FIXTURE_SHA256 = '19edb4162586afb859c062b82a4c26b54d7329dc3303205628ad61ab1558ef40'


def fixture_path():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'grouping-pattern.rgb888'
    return Path(__file__).resolve().parents[2] / 'tools/windows-usb-probe/pattern.rgb888'


def load_fixture():
    rgb = fixture_path().read_bytes()
    if len(rgb) != 460800 or hashlib.sha256(rgb).hexdigest() != FIXTURE_SHA256:
        raise ValueError('Invalid public experiment fixture')
    return RGBFrame(320, 480, rgb, 0)


def fixed_encoder(arm, fixture):
    """Trusted Python seam, never a normal worker option or environment setting."""
    if arm not in ('A', 'B'):
        raise ValueError('Invalid experiment arm')
    def encode(frame):
        if (frame.width, frame.height, frame.rgb) != (320, 480, fixture.rgb):
            raise ValueError('Only the public experiment frame is permitted')
        packets = encode_portrait(frame)
        if arm == 'A':
            return packets
        return packets[:2] + tuple(packets[i] + packets[i+1] for i in range(2, 122, 2))
    return encode
