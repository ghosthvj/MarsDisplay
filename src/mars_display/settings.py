"""Version-1 local settings, independent of capture and application lifecycle."""

from dataclasses import dataclass
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

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise SettingsError("Unsupported settings schema version; use version 1.") from None
        _capture_url(self.mars_url)
        device = self.device_identity
        if device is not None and (
            type(device) is not str or not device.strip() or _unsafe_text(device)
        ):
            raise SettingsError(
                "Device identity must be null or a non-empty string without control characters."
            ) from None

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
        try:
            data = json.loads(raw, object_pairs_hook=_unique_object)
        except (ValueError, RecursionError) as error:
            if isinstance(error, SettingsError):
                raise error from None
            raise SettingsError(
                "Settings file is not valid JSON; correct it or explicitly save new settings."
            ) from None
        if type(data) is not dict or data.keys() != _KEYS:
            raise SettingsError(_SCHEMA_ERROR) from None
        return Settings(**data)

    def save(self, settings: Settings) -> None:
        """Validate before any write; atomically replace only on explicit save."""
        if type(settings) is not Settings:
            raise SettingsError("Only validated Settings can be saved.") from None
        # Reuse the value constructor's invariants, even if a caller bypassed
        # frozen assignment using Python's low-level object API.
        checked = Settings(settings.mars_url, settings.device_identity, settings.schema_version)
        content = json.dumps({
            "schema_version": checked.schema_version,
            "mars_url": checked.mars_url,
            "device_identity": checked.device_identity,
        }, ensure_ascii=True, indent=2) + "\n"
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=".settings-", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
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
