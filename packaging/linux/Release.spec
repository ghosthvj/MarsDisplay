# Distribution-only recipe; preserve the original prototype and Windows specs.
import platform
import re
import sys
from pathlib import Path

if sys.platform != 'linux' or platform.machine() != 'x86_64':
    raise SystemExit('Linux x86_64 builder required')

here = Path(SPECPATH).resolve()
a = Analysis(
    [str(here / 'entrypoint.py')],
    pathex=[str(here.parents[1] / 'src')],
    binaries=[], datas=[],
    hiddenimports=['mars_display.linux_usb_worker'],
    hookspath=[], runtime_hooks=[str(here / 'usb_bootstrap.py')],
    excludes=[], noarchive=False,
)


def capture_runtime(entries):
    # PNG screenshots use CDP, not Playwright's standalone video recorder.
    # Do not remove Chromium's own media libraries or change installed SDK pins.
    prefix = ('playwright', 'driver', 'package', '.local-browsers')
    result = []
    for entry in entries:
        parts = tuple(entry[0].split('/'))
        if (len(parts) > 5 and parts[:4] == prefix
                and re.fullmatch(r'ffmpeg-[0-9]+', parts[4])):
            continue
        result.append(entry)
    return result


pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MarsDisplay',
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, capture_runtime(a.binaries), capture_runtime(a.datas),
               strip=False, upx=False, name='MarsDisplay')
