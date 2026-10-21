"""Bounded private USB IPC. No sockets, files or devices opened at import."""
from dataclasses import dataclass, fields
import math
import socket
import struct
import time

from .frames import RGBFrame, _validate_frame

HELLO, OPEN, FRAME, CLOSE, REPLY = range(1, 6)
TIMED_FRAME, TIMED_REPLY = 6, 7
TIMING = struct.Struct('!B5d')
HEADER = struct.Struct('!4sBBHII')
METADATA = struct.Struct('!HHd')
FRAME_BYTES = METADATA.size + 320 * 480 * 3
POLL = 0.05


class ProtocolError(ValueError):
    """Malformed, truncated or unsupported private message."""


@dataclass(frozen=True)
class WorkerTiming:
    """Successful helper stages, in seconds; never clock timestamps."""
    decode: float
    identity: float
    encode: float
    write: float
    drain: float

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('USB timings must be nonnegative finite seconds')


def encode_timing(detail):
    return TIMING.pack(0, detail.decode, detail.identity, detail.encode,
                       detail.write, detail.drain)


def decode_timing(body):
    if not isinstance(body, bytes) or len(body) != TIMING.size:
        raise ProtocolError('Invalid USB timing length')
    status, *durations = TIMING.unpack(body)
    if status != 0:
        raise ProtocolError('Invalid USB timing status')
    return WorkerTiming(*durations)


class Cancelled(RuntimeError):
    """The caller requested cancellation; no delivery claim is implied."""


@dataclass(frozen=True)
class Budgets:
    """Provisional safety limits, not measured hardware capacity."""
    start: float = 5
    frame: float = 20
    write: float = 3
    drain: float = 15
    close: float = 5
    reap: float = 2

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('USB budgets must be positive finite seconds')


def _validate_deadline(deadline):
    try:
        valid = type(deadline) in (int, float) and math.isfinite(deadline)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('USB IPC requires a finite absolute deadline')


def _remaining(deadline, cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled('USB operation cancelled')
    if deadline is None:
        return POLL
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('USB IPC deadline exceeded')
    return min(POLL, remaining)


def _shape(kind, request, size):
    if type(request) is not int or not 0 <= request <= 0xffffffff:
        raise ValueError('Invalid USB request identifier')
    if type(kind) is not int or kind not in (HELLO, OPEN, FRAME, CLOSE, REPLY, TIMED_FRAME, TIMED_REPLY):
        raise ValueError('Unknown USB message type')
    if (kind == HELLO) != (request == 0):
        raise ValueError('Invalid USB request order')
    valid_size = {HELLO: size == 32, OPEN: 0 < size <= 128,
                  FRAME: size == FRAME_BYTES, CLOSE: size == 0, REPLY: size == 1,
                  TIMED_FRAME: size == FRAME_BYTES, TIMED_REPLY: size == TIMING.size}
    if not valid_size[kind]:
        raise ValueError('Invalid USB message length')


def _receive(channel, size, deadline, cancel):
    chunks = bytearray()
    while len(chunks) < size:
        channel.settimeout(_remaining(deadline, cancel))
        try:
            chunk = channel.recv(min(size - len(chunks), 65536))
        except socket.timeout:
            continue
        if not chunk or len(chunk) > size - len(chunks):
            raise ProtocolError('Incomplete USB message')
        chunks.extend(chunk)
    return bytes(chunks)


def send_packet(channel, kind, request, body, deadline, *, cancel=None):
    _validate_deadline(deadline)
    if not isinstance(body, bytes):
        raise TypeError('USB message body must be bytes')
    _shape(kind, request, len(body))
    data = memoryview(HEADER.pack(b'MUSB', 1, kind, 0, request, len(body)) + body)
    while data:
        channel.settimeout(_remaining(deadline, cancel))
        try:
            sent = channel.send(data)
        except socket.timeout:
            continue
        if not sent or sent > len(data):
            raise ProtocolError('USB channel stopped accepting data')
        data = data[sent:]


def receive_packet(channel, deadline=None, *, cancel=None):
    if deadline is not None:
        _validate_deadline(deadline)
    # An owned idle worker may wait for its first byte. Once a message starts,
    # the entire header/body has one finite deadline, never renewed per chunk.
    if deadline is None:
        first = _receive(channel, 1, None, cancel)
        deadline = time.monotonic() + 5
        header = first + _receive(channel, HEADER.size - 1, deadline, cancel)
    else:
        header = _receive(channel, HEADER.size, deadline, cancel)
    magic, version, kind, flags, request, size = HEADER.unpack(header)
    try:
        if magic != b'MUSB' or version != 1 or flags:
            raise ValueError('Unsupported USB IPC header')
        _shape(kind, request, size)
    except ValueError:
        raise ProtocolError('Invalid USB IPC header') from None
    return kind, request, _receive(channel, size, deadline, cancel)


def encode_frame(frame):
    if not isinstance(frame, RGBFrame):
        raise TypeError('frame must be an RGBFrame')
    _validate_frame(frame)
    if (frame.width, frame.height) != (320, 480):
        raise ValueError('Native USB requires 320x480 portrait')
    return METADATA.pack(frame.width, frame.height, frame.captured_at) + frame.rgb


def decode_frame(body):
    if not isinstance(body, bytes) or len(body) != FRAME_BYTES:
        raise ValueError('Invalid USB frame length')
    width, height, captured = METADATA.unpack_from(body)
    frame = RGBFrame(width, height, body[METADATA.size:], captured)
    if (width, height) != (320, 480):
        raise ValueError('Native USB requires 320x480 portrait')
    return frame
