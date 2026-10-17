"""Delegate the complete pinned base hook, omitting only its optional Mesa request."""
from importlib import util
from pathlib import Path
import runpy
import PyInstaller
from PyInstaller.utils.hooks.qt import pyside6_library_info

_spec = util.spec_from_file_location('marsdisplay_native_runtime', Path(__file__).resolve().parents[1] / 'native_runtime.py')
_policy = util.module_from_spec(_spec)
_spec.loader.exec_module(_policy)
with _policy.omit_optional_mesa(pyside6_library_info):
    _stock = runpy.run_path(str(Path(PyInstaller.__file__).resolve().parent / 'hooks/hook-PySide6.py'))
globals().update({name: value for name, value in _stock.items() if not name.startswith('__')})
