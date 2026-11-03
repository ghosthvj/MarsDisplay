# Linux-only onedir candidate. Windows packaging remains independent.
import platform
import sys
from pathlib import Path

if sys.platform != 'linux' or platform.machine() != 'x86_64':
    raise SystemExit('Linux x86_64 builder required')

here = Path(SPECPATH).resolve()
# Playwright's standard sync_api hook collects its package-local driver and
# .local-browsers tree (installed with PLAYWRIGHT_BROWSERS_PATH=0).
# Standard QtGui/QtWidgets hooks select plugins and their native dependencies.
a = Analysis(
    [str(here / 'entrypoint.py')],
    pathex=[str(here.parents[1] / 'src')],
    binaries=[], datas=[],
    hiddenimports=['mars_display.linux_usb_worker'],
    hookspath=[], runtime_hooks=[str(here / 'usb_bootstrap.py')],
    excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MarsDisplay',
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='MarsDisplay')
