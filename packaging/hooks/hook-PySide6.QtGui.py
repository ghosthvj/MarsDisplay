"""Delegate pinned PyInstaller 6.22.3 QtGui traversal with scoped root policy."""
from importlib import util
from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

_policy_spec = util.spec_from_file_location(
    'marsdisplay_qt_plugins', Path(__file__).resolve().parents[1] / 'qt_plugins.py')
_policy = util.module_from_spec(_policy_spec)
_policy_spec.loader.exec_module(_policy)

_info = pyside6_library_info
_version = _info.version  # Initialize lazy library info before the instance wrapper.
_missing = object()
_previous_override = _info.__dict__.get('collect_plugins', _missing)
_default_collect_plugins = _info.collect_plugins


def _collect_plugins(family):
    # Preserve stock release/debug and dependency validation before selection.
    return _policy.select_plugin_roots(family, _default_collect_plugins(family))


try:
    _info.collect_plugins = _collect_plugins
    hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
finally:
    # Do not leave a captured bound descriptor as a permanent instance override.
    if _previous_override is _missing:
        del _info.collect_plugins
    else:
        _info.collect_plugins = _previous_override
