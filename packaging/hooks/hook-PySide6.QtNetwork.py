"""Preserve Qt traversal; select only the reviewed prebuilt OpenSSL pair."""
from importlib import util
from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

_root = Path(__file__).resolve().parents[2]
_spec = util.spec_from_file_location('marsdisplay_openssl_prebuilt', _root / 'packaging/openssl_prebuilt.py')
_prebuilt = util.module_from_spec(_spec)
_spec.loader.exec_module(_prebuilt)
_pair = _prebuilt.collect(_root / 'build/openssl-prebuilt')
hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries += _pair
