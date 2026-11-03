"""Passive Linux settings paths; not wired into production platform admission."""

import os
from pathlib import Path

from .settings import SettingsStoreError


def linux_settings_path() -> Path:
    """Use absolute XDG_CONFIG_HOME, otherwise absolute HOME/.config.

    Validate path syntax only: no filesystem probes, creation, or migration.
    Access failures remain the explicit SettingsStore operation's responsibility.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    variable = "XDG_CONFIG_HOME" if xdg and Path(xdg).is_absolute() else "HOME"
    value = xdg if variable == "XDG_CONFIG_HOME" else os.environ.get("HOME")
    try:
        if not value or not Path(value).is_absolute() or "\x00" in value:
            raise ValueError
        os.fsencode(value)
    except (ValueError, TypeError):
        raise SettingsStoreError(
            f"{variable} is unavailable; provide an explicit settings path."
        ) from None
    base = Path(value)
    if variable == "HOME":
        base = base / ".config"
    return base / "MarsDisplay" / "settings.json"
