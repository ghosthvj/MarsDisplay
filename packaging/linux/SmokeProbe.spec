# Verification-only onedir: never ship with MarsDisplay/AppImage.
import platform
import sys
from pathlib import Path

if sys.platform != 'linux' or platform.machine() != 'x86_64':
    raise SystemExit('Linux x86_64 builder required')
here = Path(SPECPATH).resolve()
# Same standard QtWidgets/QtGui and Playwright sync_api hooks as production.
a = Analysis([str(here / 'smoke_probe.py')], pathex=[str(here.parents[1] / 'src')],
             binaries=[], datas=[], hiddenimports=[], hookspath=[],
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SmokeProbe',
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='SmokeProbe')
