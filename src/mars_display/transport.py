"""Synchronous output boundary; simulation never accesses hardware."""

from typing import Protocol

from .frames import RGBFrame, _validate_frame


class Transport(Protocol):
    """Small output contract for future adapters; calls complete synchronously."""

    def open(self) -> None: ...

    def send(self, frame: RGBFrame) -> None: ...

    def close(self) -> None: ...


class SimulatedTransport:
    """Bounded in-memory sink, initially closed; never a connected USB screen.

    Open/close are idempotent and preserve the last frame and lifetime count.
    Reopening continues the count. Each accepted send replaces the last frame,
    even when the same object is sent again. No history, files, or device I/O.
    This transport is intentionally single-threaded.
    """

    def __init__(self) -> None:
        self._is_open = False
        self._latest_frame: RGBFrame | None = None
        self._accepted_frames = 0

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def status(self) -> str:
        return "simulated-open" if self._is_open else "simulated-closed"

    @property
    def latest_frame(self) -> RGBFrame | None:
        return self._latest_frame

    @property
    def accepted_frames(self) -> int:
        return self._accepted_frames

    def open(self) -> None:
        self._is_open = True

    def send(self, frame: RGBFrame) -> None:
        if not self._is_open:
            raise RuntimeError("simulated transport is closed")
        if not isinstance(frame, RGBFrame):
            raise TypeError("frame must be an RGBFrame")
        _validate_frame(frame)
        self._latest_frame = frame
        self._accepted_frames += 1

    def close(self) -> None:
        self._is_open = False
