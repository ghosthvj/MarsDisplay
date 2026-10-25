"""Optional launch intent, separate from strict rc5-compatible capture settings."""
import json
from pathlib import Path

from .settings import SettingsError, SettingsStoreError, _unique_object, _write


class StartupPreferenceStore:
    """Passive reads; only explicit save publishes a validated boolean atomically."""

    def __init__(self, settings_path: Path):
        self.path = settings_path.with_name(settings_path.name + '.startup.json')

    def load(self) -> bool:
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
            if (not isinstance(value, dict) or set(value) != {'start_capture_on_launch'}
                    or type(value['start_capture_on_launch']) is not bool):
                raise ValueError
            return value['start_capture_on_launch']
        except FileNotFoundError:
            return False
        except (OSError, UnicodeError, ValueError):
            raise SettingsStoreError(
                'Cannot read startup preference. Automatic capture is disabled; '
                'change the option to save a valid preference.') from None

    def save(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise SettingsError('Startup capture must be true or false.')
        data = json.dumps({'start_capture_on_launch': enabled}, indent=2) + '\n'
        _write(self.path, data.encode('utf-8'), replace=True)
