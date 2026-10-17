"""Passive USB-serial observations, not a screen driver or compatibility list.

Nothing enumerates at import time. No port is opened, and no settings are saved.
"""
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from urllib.parse import quote


class DeviceInventoryError(RuntimeError):
    """Descriptor enumeration failed; backend details are intentionally hidden."""


class DeviceSelectionError(ValueError):
    """An explicit identity could not resolve exactly one current observation."""


@dataclass(frozen=True)
class USBSerialDescriptor:
    """Snapshot metadata only; VID/PID never establishes protocol support."""

    device: str
    vid: int
    pid: int
    serial_number: str | None
    description: str | None
    location: str | None
    manufacturer: str | None
    product: str | None
    interface: str | None

    @property
    def identity(self) -> str | None:
        """Opaque, case-preserving USB identity; absent serial is not stable."""
        if self.serial_number is None:
            return None
        return f"usb:{self.vid:04x}:{self.pid:04x}:{quote(self.serial_number, safe='')}"


def _text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    # Exclude controls and surrogate code points; preserve meaningful case/space.
    if any(not char.isprintable() for char in value):
        return None
    return value


def _observe(record: object) -> USBSerialDescriptor | None:
    device = _text(getattr(record, "device", None))
    vid, pid = getattr(record, "vid", None), getattr(record, "pid", None)
    if device is None or any(type(value) is not int or not 0 <= value <= 65535
                             for value in (vid, pid)):
        return None
    metadata = {name: _text(getattr(record, name, None)) for name in (
        "serial_number", "description", "location", "manufacturer", "product", "interface"
    )}
    return USBSerialDescriptor(device, vid, pid, **metadata)


def enumerate_devices(
    provider: Callable[[], Iterable[object]] | None = None,
) -> tuple[USBSerialDescriptor, ...]:
    """Return frozen USB observations in deterministic metadata order.

    An injected zero-argument provider replaces native enumeration completely.
    Invalid/non-USB records are omitted; unsafe optional text becomes unknown.
    Duplicates remain visible so selection can reject ambiguous identities.
    Failure returns no partial inventory and exposes no raw backend details.
    """
    try:
        if provider is None:
            from serial.tools.list_ports import comports

            records = comports(include_links=False)
        else:
            records = provider()
        observations = [item for record in records if (item := _observe(record)) is not None]
        # Every observed field participates; no provider-order tie breaking.
        return tuple(sorted(observations, key=lambda item: tuple(
            getattr(item, field.name) if getattr(item, field.name) is not None else ""
            for field in fields(item)
        )))
    except Exception:
        raise DeviceInventoryError(
            "Cannot list USB serial descriptors; check system device access and retry."
        ) from None


def select_device(
    inventory: tuple[USBSerialDescriptor, ...], identity: str | None,
) -> USBSerialDescriptor:
    """Resolve an exact saved identity, never a port name or first-device default.

    The caller owns refreshing inventory and explicitly persisting any selection.
    Resolution neither opens the descriptor nor asserts screen compatibility.
    """
    if identity is None or (isinstance(identity, str) and not identity.strip()):
        raise DeviceSelectionError(
            "Select an explicit stable USB identity; no device was selected."
        )
    matches = [item for item in inventory if item.identity is not None and item.identity == identity]
    if not matches:
        raise DeviceSelectionError(
            "Selected USB identity was not found; refresh inventory and select again."
        )
    if len(matches) != 1:
        raise DeviceSelectionError(
            "Selected USB identity is ambiguous; disconnect duplicates or identify the hardware before selecting."
        )
    return matches[0]
