# Isolated console; native Windows only, invoked by build_grouping_experiment.py.
from pathlib import Path
from importlib import util
import sys

if sys.platform != 'win32':
    raise RuntimeError('Grouping experiment requires native Windows')
root = Path(SPECPATH).parent
spec = util.spec_from_file_location('grouping_native_runtime', root / 'packaging/native_runtime.py')
policy = util.module_from_spec(spec)
spec.loader.exec_module(policy)
with policy.external_dependencies():
    a = Analysis(
        [str(root / 'packaging/grouping_entrypoint.py')],
        pathex=[str(root / 'src'), str(root / 'packaging')],
        datas=[(str(root / 'tools/windows-usb-probe/pattern.rgb888'), '.')],
        hookspath=[str(root / 'packaging/hooks')],
        runtime_hooks=[str(root / 'packaging/grouping_bootstrap.py')],
        # Hashing can collect libcrypto alone. Include stdlib ssl so the existing
        # reviewed Python OpenSSL pair is complete; no runtime network operation.
        hiddenimports=['mars_display.usb_grouping_worker', 'ssl'],
        excludes=['mars_display.app', 'mars_display.browser', 'playwright', 'PIL',
                  'PyQt5', 'PyQt6', 'PySide2',
                  'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
                  'PySide6.QtWebEngineQuick', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets'],
    )
# PyInstaller's data tuple uses the original basename; bind the sole public
# pattern to the exact frozen lookup name rather than exposing a path option.
a.datas = [('grouping-pattern.rgb888' if name == 'pattern.rgb888' else name, source, kind)
           for name, source, kind in a.datas]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MarsDisplayGroupingExperiment',
          console=True, upx=False, contents_directory='_internal')
collection = COLLECT(exe, a.binaries, a.datas, name='MarsDisplayGroupingExperiment', upx=False)
