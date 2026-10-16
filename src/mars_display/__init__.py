"""MarsDisplay hardware-independent foundation; no application entrypoint."""

from .frames import RGBFrame
from .transport import SimulatedTransport, Transport

__all__ = ["RGBFrame", "SimulatedTransport", "Transport"]
