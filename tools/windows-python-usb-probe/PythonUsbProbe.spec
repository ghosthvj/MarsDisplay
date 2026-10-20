# Invoked only by build_probe.py on the actual Windows x64 SDK.
from importlib import util
from pathlib import Path
import hashlib
import json
import os
import re
import sys
import PyInstaller
from PyInstaller.archive.readers import ZlibArchiveReader

if sys.platform != 'win32':
    raise RuntimeError('PythonUsbProbe.spec requires native Windows')
root = Path(SPECPATH).parents[1]
helper = util.spec_from_file_location('probe_native_runtime', root / 'packaging/native_runtime.py')
native_runtime = util.module_from_spec(helper)
helper.loader.exec_module(native_runtime)
fixture = root / 'tools/windows-usb-probe/pattern.rgb888'
if hashlib.sha256(fixture.read_bytes()).hexdigest() != '19edb4162586afb859c062b82a4c26b54d7329dc3303205628ad61ab1558ef40':
    raise ValueError('Canonical raw fixture hash mismatch')
with native_runtime.external_dependencies():
    a = Analysis(
        [str(root / 'tools/windows-python-usb-probe/entrypoint.py')],
        pathex=[str(root / 'src')],
        datas=[(str(fixture), 'probe-assets')],
        excludes=['PIL', 'Pillow', 'PySide6', 'shiboken6', 'PyQt5', 'PyQt6', 'playwright', 'tkinter'],
        hiddenimports=[],
    )
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PythonUsbProbe',
          console=True, upx=False, contents_directory='_internal')
collection = COLLECT(exe, a.binaries, a.datas, name='PythonUsbProbe', upx=False)
origins = {}
for destination, source, kind in a.binaries:
    if Path(destination).suffix.lower() in {'.dll', '.pyd'}:
        key = '_internal/' + destination.replace('\\', '/')
        if key in origins:
            raise ValueError('Duplicate native Analysis origin')
        origins[key] = str(Path(source).absolute())
if len(exe.exefiles) != 1:
    raise ValueError('Unexpected EXE bootloader input')
bootloader = Path(exe.exefiles[0][1])
report = {
    'origins': origins,
    'modules': sorted({node.identifier for node in a.graph.nodes()
                       if type(node).__name__ not in {'ExcludedModule', 'MissingModule', 'Script'}
                       and re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', node.identifier)}),
    'entrypoint': {'path': 'tools/windows-python-usb-probe/entrypoint.py',
                   'sha256': hashlib.sha256((root / 'tools/windows-python-usb-probe/entrypoint.py').read_bytes()).hexdigest()},
    'pyz_modules': sorted(ZlibArchiveReader(pyz.name).toc),
    'bootloader_sha256': hashlib.sha256(bootloader.read_bytes()).hexdigest(),
    'exe_sha256': hashlib.sha256(Path(exe.name).read_bytes()).hexdigest(),
}
with Path(os.environ['PROBE_ANALYSIS_REPORT']).open('x', encoding='utf-8') as stream:
    json.dump(report, stream, sort_keys=True, indent=2)
