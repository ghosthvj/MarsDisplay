# Native Windows recipe, invoked only through build_portable.py.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files

if sys.platform != 'win32':
    raise RuntimeError('MarsDisplay.spec requires native Windows')

root = Path(SPECPATH).parent
# Playwright's pinned hook uses collect_data_files; include the complete driver,
# Node, package registry, inlined notices and package-local browser resources.
a = Analysis(
    [str(root / 'packaging/entrypoint.py')],
    pathex=[str(root / 'src')],
    datas=collect_data_files('playwright'),
    hiddenimports=['mars_display.app', 'mars_display.devices'],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6.QtWebEngineCore',
              'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
              'PySide6.QtPdf', 'PySide6.QtPdfWidgets'],
)
# Pinned PyInstaller Qt hooks collect the used Core/Gui/Widgets native modules
# and PySide6/plugins/platforms/qwindows.dll on Windows. Do not collect_all Qt.
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MarsDisplay',
          console=False, upx=False, contents_directory='_internal')
collection = COLLECT(exe, a.binaries, a.datas, name='MarsDisplay', upx=False)
