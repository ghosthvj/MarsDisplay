"""Strict local settings and explicit reversible migration; no runtime admission."""

from dataclasses import dataclass, field
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import unquote, urlsplit, urlunsplit


class SettingsError(ValueError):
    """Invalid configuration; messages never contain supplied values."""


class SettingsStoreError(SettingsError):
    """Configuration could not be read or explicitly saved."""


_URL_ERROR = (
    "MARS URL must be HTTP(S) with a valid host and port, without credentials, "
    "query, fragment, whitespace or control characters."
)
_SCHEMA_ERROR = "Settings must contain exactly schema_version, mars_url and device_identity."
_KEYS = {"schema_version", "mars_url", "device_identity"}
_KEYS_V2 = _KEYS | {"output_mode", "native_profile"}
_KEYS_V3 = _KEYS_V2 | {"brightness_percent"}
_VERSION_ERROR = "Unsupported settings schema version; supported versions are 1, 2 and 3."
_SCHEMA_V3_ERROR = "Schema 3 must contain exactly schema_version, mars_url, device_identity, output_mode, native_profile and brightness_percent."
BRIGHTNESS_LEVELS = (20, 40, 60, 80, 100)
_ACK_V3_ERROR = "Schema 3 is incompatible with older binaries; explicit acknowledgement is required."
_BRIGHTNESS_BACKUP_ERROR = "A valid preserved pre-brightness backup is required."
_SCHEMA_V2_ERROR = "Schema 2 must contain exactly schema_version, mars_url, device_identity, output_mode and native_profile."
NATIVE_PROFILE = "tus35-portrait-v1"
NATIVE_IDENTITY = "usb:1a86:5722:USB35INCHIPSV2"
_ACK_ERROR = "Schema 2 is incompatible with older binaries; explicit acknowledgement is required."


def _unsafe_text(value: str) -> bool:
    return any(unicodedata.category(char) in {"Cc", "Cs"} for char in value)


def _capture_url(value: str) -> str:
    try:
        if (type(value) is not str or not value or _unsafe_text(value)
                or any(char.isspace() for char in value)
                or any(char in value for char in "?#\\")
                or re.search(r"%(?![0-9a-fA-F]{2})", value)):
            raise ValueError
        decoded = unquote(value, errors="strict")
        if _unsafe_text(decoded) or "\\" in decoded:
            raise ValueError
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError
        if parts.username is not None or parts.password is not None:
            raise ValueError
        host = parts.hostname
        if ":" in host:
            host = f"[{ipaddress.IPv6Address(host)}]"
        else:
            host = host.encode("idna").decode("ascii").lower()
            labels = host.rstrip(".").split(".")
            if len(host) > 253 or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels
            ):
                raise ValueError
        # Reading .port validates its numeric range. Check the original authority
        # too: urlsplit otherwise tolerates empty ports and text after brackets.
        port = parts.port
        authority = parts.netloc
        raw_host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
        suffix = authority[len(raw_host):]
        if authority[:len(raw_host)].lower() != raw_host.lower():
            raise ValueError
        if suffix and (not re.fullmatch(r":[0-9]+", suffix) or port is None):
            raise ValueError
        netloc = host + suffix
        path = parts.path.rstrip("/")
        if not path.endswith("/display"):
            path += "/display"
        return urlunsplit((parts.scheme, netloc, path, "", ""))
    except (ValueError, TypeError, UnicodeError):
        raise SettingsError(_URL_ERROR) from None


@dataclass(frozen=True)
class Settings:
    """Configured input only; missing configuration is represented by None."""

    mars_url: str
    device_identity: str | None = None
    schema_version: int = 1
    output_mode: str = field(default="simulated", repr=False)
    native_profile: str | None = field(default=None, repr=False)
    brightness_percent: int = field(default=100, repr=False)

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version not in (1, 2, 3):
            raise SettingsError(_VERSION_ERROR) from None
        _capture_url(self.mars_url)
        device = self.device_identity
        if device is not None and (
            type(device) is not str or not device.strip() or _unsafe_text(device)
        ):
            raise SettingsError(
                "Device identity must be null or a non-empty string without control characters."
            ) from None

        if self.output_mode not in ("simulated", "native") or type(self.output_mode) is not str:
            raise SettingsError("Output mode must be simulated or native.") from None
        if self.schema_version == 1 and (self.output_mode != "simulated" or self.native_profile is not None):
            raise SettingsError("Schema 1 supports simulated output only.") from None
        if self.output_mode == "simulated":
            if self.native_profile is not None:
                raise SettingsError("Simulated output requires a null native profile.") from None
        elif (type(self.native_profile) is not str or self.native_profile != NATIVE_PROFILE
              or self.device_identity != NATIVE_IDENTITY):
            raise SettingsError("Native output requires the supported profile and exact opaque identity.") from None

        if type(self.brightness_percent) is not int or self.brightness_percent not in BRIGHTNESS_LEVELS:
            raise SettingsError("Brightness must be an integer percentage: 20, 40, 60, 80 or 100.") from None
        if self.schema_version < 3 and self.brightness_percent != 100:
            raise SettingsError("Schemas 1 and 2 support default brightness 100 only; use explicit schema-3 migration.") from None

    @property
    def capture_url(self) -> str:
        """HTTP(S) browser destination, preserving any reverse-proxy prefix."""
        return _capture_url(self.mars_url)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SettingsError(_SCHEMA_ERROR) from None
        result[key] = value
    return result


class SettingsStore:
    """No cached state, automatic repair, launch, or runtime-state authority."""

    def __init__(self, path: Path | str | None = None):
        if path is None:
            local = os.environ.get("LOCALAPPDATA")
            if not local or not Path(local).is_absolute():
                raise SettingsStoreError(
                    "LOCALAPPDATA is unavailable; provide an explicit settings path."
                ) from None
            path = Path(local) / "MarsDisplay" / "settings.json"
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Settings | None:
        """Missing file means first run; all other failures leave it untouched."""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except UnicodeError:
            raise SettingsError(
                "Settings file is not valid JSON; correct it or explicitly save new settings."
            ) from None
        except OSError:
            raise SettingsStoreError("Cannot read settings; check file access and retry.") from None
        return Settings(**_document(raw))

    @property
    def schema1_backup_path(self) -> Path:
        """Exact original bytes retained before incompatible migration."""
        return self.path.with_name(self.path.name + ".schema1-backup.json")

    @property
    def pre_brightness_backup_path(self) -> Path:
        """Exact schema-1/2 recovery point retained before schema 3."""
        return self.path.with_name(self.path.name + ".pre-brightness-backup.json")

    def _existing(self):
        try:
            return _document(self.path.read_bytes())
        except FileNotFoundError:
            return None
        except OSError:
            raise SettingsStoreError("Cannot read settings; check file access and retry.") from None

    def _snapshot(self):
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return None, None
        except OSError:
            raise SettingsStoreError("Cannot read settings; check file access and retry.") from None
        return raw, Settings(**_document(raw))

    def _expect_unchanged(self, original):
        try:
            current = self.path.read_bytes()
        except FileNotFoundError:
            current = None
        except OSError:
            raise SettingsStoreError("Cannot read settings; check file access and retry.") from None
        if current != original:
            raise SettingsError("Settings changed during the operation; nothing was replaced.") from None

    def save(self, settings: Settings) -> None:
        """Ordinary explicit edit, never implicit migration or downgrade."""
        checked = _checked(settings)
        existing = self._existing()
        version = existing["schema_version"] if existing is not None else 1
        if checked.schema_version != version:
            raise SettingsError("Use explicit schema migration or schema-1 recovery; Save cannot change versions.") from None
        if version == 2:
            Settings(**existing)
            self._backup_bytes()
        if version == 3:
            snapshot, current = self._snapshot()
            if current is None or current.schema_version != 3:
                raise SettingsError("Settings changed during the operation; nothing was replaced.") from None
            self._pre_brightness_bytes()
            self._expect_unchanged(snapshot)
        _write(self.path, _content(checked), replace=True)

    def migrate_to_v2(self, settings: Settings, *, acknowledge_legacy_incompatibility=False) -> None:
        """Trusted explicit API: preserve old-readable bytes before replacement."""
        if acknowledge_legacy_incompatibility is not True:
            raise SettingsError(_ACK_ERROR) from None
        checked = _checked(settings)
        if checked.schema_version != 2:
            raise SettingsError("Migration requires validated schema-2 settings.") from None
        snapshot, current = self._snapshot()
        if current is not None and current.schema_version != 1:
            if current.schema_version == 3:
                raise SettingsError("Settings already use schema 3; use explicit Save.") from None
            raise SettingsError("Settings already use schema 2; use explicit Save.") from None
        original = (snapshot if current is not None
                    else _content(Settings(checked.mars_url, checked.device_identity)))
        self._preserve_schema1(original)
        self._expect_unchanged(snapshot)
        _write(self.path, _content(checked), replace=True)

    def _preserve_schema1(self, original):
        backup = self.schema1_backup_path
        try:
            if backup.exists():
                if backup.read_bytes() != original:
                    raise OSError("Conflicting backup")
            else:
                _write(backup, original, replace=False)
        except OSError:
            raise SettingsStoreError("Cannot preserve schema-1 settings; previous settings were not replaced.") from None

    def migrate_to_v3(self, settings: Settings, *, acknowledge_legacy_incompatibility=False) -> None:
        """Explicit stopped-authority caller operation; never automatic on Save."""
        if acknowledge_legacy_incompatibility is not True:
            raise SettingsError(_ACK_V3_ERROR) from None
        checked = _checked(settings)
        if checked.schema_version != 3:
            raise SettingsError("Migration requires validated schema-3 settings.") from None
        snapshot, current = self._snapshot()
        if current is not None and current.schema_version == 3:
            raise SettingsError("Settings already use schema 3; use explicit Save.") from None
        original = (snapshot if current is not None
                    else _content(Settings(checked.mars_url, checked.device_identity)))
        original_version = current.schema_version if current is not None else 1
        backup = self.pre_brightness_backup_path
        # Validate every existing recovery point before publishing any new file.
        try:
            if backup.exists() and self._pre_brightness_bytes() != original:
                raise SettingsStoreError("Conflicting pre-brightness backup; previous settings were not replaced.")
            if self.schema1_backup_path.exists():
                legacy = self._backup_bytes()
                if original_version == 1 and legacy != original:
                    raise SettingsStoreError("Cannot preserve schema-1 settings; previous settings were not replaced.")
            if not backup.exists():
                _write(backup, original, replace=False)
        except OSError:
            raise SettingsStoreError("Cannot preserve pre-brightness settings; previous settings were not replaced.") from None
        if original_version == 1:
            self._preserve_schema1(original)
        self._expect_unchanged(snapshot)
        _write(self.path, _content(checked), replace=True)

    def _pre_brightness_bytes(self) -> bytes:
        try:
            raw = self.pre_brightness_backup_path.read_bytes()
            checked = Settings(**_document(raw))
            if checked.schema_version not in (1, 2):
                raise SettingsError("Backup is not schema 1 or 2.")
            return raw
        except (OSError, SettingsError):
            raise SettingsStoreError(_BRIGHTNESS_BACKUP_ERROR) from None

    def restore_pre_brightness(self) -> None:
        """Explicitly restore original schema-1/2 bytes; retain all backups."""
        snapshot, _ = self._snapshot()
        backup = self._pre_brightness_bytes()
        self._expect_unchanged(snapshot)
        _write(self.path, backup, replace=True)

    def export_schema1(self, destination: Path | str) -> None:
        """Explicit old-reader export, exclusively created; never downgrade Save."""
        snapshot, current = self._snapshot()
        if current is None:
            raise SettingsError("No settings are available to export.") from None
        data = (snapshot if current.schema_version == 1
                else _content(Settings(current.mars_url, current.device_identity)))
        _write(Path(destination), data, replace=False)

    def _backup_bytes(self) -> bytes:
        try:
            raw = self.schema1_backup_path.read_bytes()
            checked = Settings(**_document(raw))
            if checked.schema_version != 1:
                raise SettingsError("Backup is not schema 1.")
            return raw
        except (OSError, SettingsError):
            raise SettingsStoreError("A valid preserved schema-1 backup is required.") from None

    def restore_schema1(self) -> None:
        """Explicit recovery only; refuse to erase invalid/unknown configuration."""
        snapshot, _ = self._snapshot()
        backup = self._backup_bytes()
        self._expect_unchanged(snapshot)
        _write(self.path, backup, replace=True)


def _document(raw):
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, SettingsError):
            raise error from None
        raise SettingsError(
            "Settings file is not valid JSON; correct it or explicitly save new settings."
        ) from None
    if type(data) is not dict or not _KEYS <= data.keys():
        raise SettingsError(_SCHEMA_ERROR) from None
    version = data["schema_version"]
    if type(version) is not int or version not in (1, 2, 3):
        raise SettingsError(_VERSION_ERROR) from None
    keys, error = {1: (_KEYS, _SCHEMA_ERROR), 2: (_KEYS_V2, _SCHEMA_V2_ERROR),
                   3: (_KEYS_V3, _SCHEMA_V3_ERROR)}[version]
    if data.keys() != keys:
        raise SettingsError(error) from None
    return data


def _checked(settings):
    if type(settings) is not Settings:
        raise SettingsError("Only validated Settings can be saved.") from None
    return Settings(settings.mars_url, settings.device_identity, settings.schema_version,
                    settings.output_mode, settings.native_profile, settings.brightness_percent)


def _content(settings):
    value = {"schema_version": settings.schema_version, "mars_url": settings.mars_url,
             "device_identity": settings.device_identity}
    if settings.schema_version >= 2:
        value.update(output_mode=settings.output_mode, native_profile=settings.native_profile)
    if settings.schema_version == 3:
        value["brightness_percent"] = settings.brightness_percent
    # Preserve ordinary platform text-save formatting; backup copies stay raw.
    return (json.dumps(value, ensure_ascii=True, indent=2) + "\n").replace("\n", os.linesep).encode("utf-8")


def _write(destination, data, *, replace):
    temporary = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent,
                prefix=".settings-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, destination)
            temporary = None
        else:
            os.link(temporary, destination)
            temporary.unlink()
            temporary = None
    except OSError:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                raise SettingsStoreError(
                    "Cannot save settings or remove temporary file; check directory access. "
                    "Previous settings were not replaced."
                ) from None
        raise SettingsStoreError(
            "Cannot save settings; check directory access and retry. "
            "Previous settings were not replaced."
        ) from None
