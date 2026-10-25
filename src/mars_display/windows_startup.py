"""Explicit per-user login registration; construction/import never writes Windows."""
from dataclasses import dataclass
from pathlib import PureWindowsPath
import sys

from .settings import SettingsError

_SLOTS = {
    'run': (r'Software\Microsoft\Windows\CurrentVersion\Run', 'MarsDisplay'),
    'owner': (r'Software\MarsDisplay', 'StartupCommand'),
}
_CHANGED = 'Windows startup changed; reopen Settings and try again.'
_FOREIGN = 'Windows startup entry is not owned by MarsDisplay; manage it in Windows Settings.'


def _command(executable):
    if (not isinstance(executable, str) or not PureWindowsPath(executable).is_absolute()
            or PureWindowsPath(executable).suffix.lower() != '.exe'
            or any(ord(char) < 32 or char == '"' for char in executable)):
        raise SettingsError('Windows startup requires an absolute Windows EXE path.')
    command = '"' + executable + '"'
    try:
        units = len(command.encode('utf-16-le')) // 2
    except UnicodeError:
        raise SettingsError('Windows startup requires a valid Unicode EXE path.') from None
    if units > 260:
        raise SettingsError('Windows startup command exceeds the Windows 260-character limit.')
    return command


class Registry:
    """Only two named HKCU values; never delete keys or modify other applications."""
    def __init__(self, api=None):
        if api is None:
            import winreg as api
        self.api = api

    def _query(self, key, name):
        try:
            value, kind = self.api.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        if kind != self.api.REG_SZ or not isinstance(value, str):
            raise SettingsError(_FOREIGN)
        return value

    def get(self, slot):
        path, name = _SLOTS[slot]
        try:
            with self.api.OpenKey(self.api.HKEY_CURRENT_USER, path, 0, self.api.KEY_QUERY_VALUE) as key:
                return self._query(key, name)
        except FileNotFoundError:
            return None

    def set(self, slot, value, expected):
        path, name = _SLOTS[slot]
        access = self.api.KEY_QUERY_VALUE | self.api.KEY_SET_VALUE
        with self.api.CreateKeyEx(self.api.HKEY_CURRENT_USER, path, 0, access) as key:
            if self._query(key, name) != expected:
                raise SettingsError(_CHANGED)
            self.api.SetValueEx(key, name, 0, self.api.REG_SZ, value)

    def delete_run(self, expected):
        path, name = _SLOTS['run']
        access = self.api.KEY_QUERY_VALUE | self.api.KEY_SET_VALUE
        try:
            with self.api.OpenKey(self.api.HKEY_CURRENT_USER, path, 0, access) as key:
                current = self._query(key, name)
                if current is None:
                    return
                if current != expected:
                    raise SettingsError(_CHANGED)
                self.api.DeleteValue(key, name)
        except FileNotFoundError:
            return


@dataclass(frozen=True)
class StartupState:
    enabled: bool
    needs_update: bool


class WindowsStartup:
    def __init__(self, executable, registry):
        self.command = _command(executable)
        self.registry = registry

    def _owned(self):
        run, owner = self.registry.get('run'), self.registry.get('owner')
        if owner is not None:
            try:
                valid = owner.startswith('"') and owner.endswith('"') and _command(owner[1:-1]) == owner
            except SettingsError:
                valid = False
            if not valid:
                raise SettingsError(_FOREIGN)
        if run is not None and (owner is None or run != owner):
            raise SettingsError(_FOREIGN)
        return run, owner

    def load(self):
        try:
            run, _ = self._owned()
            return StartupState(run is not None, run is not None and run != self.command)
        except OSError:
            raise SettingsError('Cannot read Windows startup; check permissions.') from None

    def save(self, enabled):
        if type(enabled) is not bool:
            raise SettingsError('Windows startup must be true or false.')
        try:
            run, owner = self._owned()
            if run is not None and (not enabled or run != self.command):
                self.registry.delete_run(run)
            if enabled and run != self.command:
                # Remove old registration first: interrupted relocation stays off.
                # Retain a harmless marker on disable; never silently repair/retry.
                if owner != self.command:
                    self.registry.set('owner', self.command, owner)
                self.registry.set('run', self.command, None)
        except OSError:
            raise SettingsError('Cannot change Windows startup; check permissions and reopen Settings.') from None
        return self.load()


def create_windows_startup():
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        return None
    return WindowsStartup(sys.executable, Registry())
