# Native Windows recipe, invoked only through build_portable.py.
from pathlib import Path
from importlib import util
import sys
from PyInstaller.utils.hooks import collect_data_files

if sys.platform != 'win32':
    raise RuntimeError('MarsDisplay.spec requires native Windows')

root = Path(SPECPATH).parent
# Playwright's pinned hook uses collect_data_files; include the complete driver,
# Node, package registry, inlined notices and package-local browser resources.
_native_spec = util.spec_from_file_location('marsdisplay_native_runtime', root / 'packaging/native_runtime.py')
_native_runtime = util.module_from_spec(_native_spec)
_native_spec.loader.exec_module(_native_runtime)
with _native_runtime.external_dependencies():
    a = Analysis(
        [str(root / 'packaging/entrypoint.py')],
        pathex=[str(root / 'src')],
        datas=collect_data_files('playwright'),
        hookspath=[str(root / 'packaging/hooks')],
        runtime_hooks=[str(root / 'packaging/usb_bootstrap.py')],
        hiddenimports=['mars_display.app', 'mars_display.devices', 'mars_display.usb_transport'],
        excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6.QtWebEngineCore',
                  'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
                  'PySide6.QtPdf', 'PySide6.QtPdfWidgets'],
    )
# Hooks add their own copies during Analysis. Select only frozen runtime data;
# never mutate SDK files or weaken the portable payload validators.
_runtime_spec = util.spec_from_file_location('marsdisplay_runtime_files', root / 'packaging/runtime_files.py')
_runtime_files = util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(_runtime_files)
a.datas = _runtime_files.select_runtime_data(a.datas)

# Pinned PyInstaller Qt hooks collect the used Core/Gui/Widgets native modules
# and PySide6/plugins/platforms/qwindows.dll on Windows. Do not collect_all Qt.
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MarsDisplay',
          console=False, upx=False, contents_directory='_internal')
collection = COLLECT(exe, a.binaries, a.datas, name='MarsDisplay', upx=False)
