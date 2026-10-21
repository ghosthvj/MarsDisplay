# P3 bounded native USB helper

P3 is under implementation. Framing, the serial core and the owned UsbTransport
controller pass source-mode fake-provider tests. Native Windows job/handle behavior
and the actual frozen application route are not yet qualified. MarsDisplay still composes Simulation.
Do not invoke the worker core as an unowned production serial service.

## Private wire v1

One authenticated, parent-owned local connection carries one operation at a time.
There is no frame queue, public endpoint option, pickle or arbitrary command RPC.
The eventual owned controller must enforce both I/O and native-call deadlines.
No frame/URL/exception body is logged or stored as history.

Each message starts with the 16-byte network-order struct `!4sBBHII`:

| Field | Value |
|---|---|
| Magic | ASCII `MUSB` |
| Version | 1 |
| Kind | One of the fixed kinds below |
| Reserved | Unsigned 16-bit zero |
| Request | Unsigned 32-bit; HELLO uses 0, operations increase from 1 |
| Body length | Exact/bounded per kind, checked before allocation |

| Kind | Value | Body |
|---|---:|---|
| HELLO | 1 | 32-byte per-session random nonce; worker-to-parent only |
| OPEN | 2 | 1–128 bytes, exact known identity `usb:1a86:5722:USB35INCHIPSV2` |
| FRAME | 3 | Exactly 460812 bytes: `!HHd` width, height, capture time, then RGB888 |
| CLOSE | 4 | Empty |
| REPLY | 5 | Exactly one fixed status byte; request must match the operation |

Frames support only 320x480 portrait, 460800 tightly packed RGB bytes, and a finite
nonnegative capture time. This does not narrow shared RGBFrame/Simulation support
for landscape. The unchanged portrait encoder emits orientation, header and
120x2560-byte RGB565LE payload chunks: 122 writes and 307222 bytes per frame.
Partial/truncated/unsupported messages are terminal, not a resynchronization mode.
An idle admitted worker may await the first message byte; once one arrives, the
whole header/body has five seconds. Parent calls always provide their operation's
absolute deadline. Send/receive cancellation and partial progress never renew it.

## Persistent serial session

OPEN validates the exact profile, current unique identity and COM occupancy before
constructing/opening the serial object. Every FRAME repeats the identity/occupancy
check and rejects an old COM reassignment before writes. Two accepted frames reuse
one open serial object; CLOSE attempts close once. Unknown/ambiguous identity,
wrong order, repeated request, invalid frame and short/failed writes do not retry.
The worker core exposes explicit Python injection for tests; no shipping fake-mode
flag or backend/module/endpoint argument is provided.

Settings remain 115200/8N1, RTS/CTS, DSR/DTR flow control disabled, DTR enabled before
open, write_timeout=3 and unused read timeout=1. Queue polling is finite, not flush.
A successful FRAME reply means all host writes completed and the queue was empty;
it is never a device rendering acknowledgement. Cleanup certainty requires the
owning parent's confirmed process reap, not merely a worker return code.

| Reply | Status | Meaning |
|---:|---|---|
| 0 | OK | Requested host operation completed |
| 1 | IDENTITY_ERROR | Unsupported, missing, ambiguous or moved identity/COM |
| 2 | INVALID | Invalid state, request order or frame |
| 3 | OPEN_ERROR | Serial construction/open failed |
| 4 | WRITE_ERROR | Write deadline, exception or short result; delivery uncertain |
| 5 | DRAIN_ERROR | Output queue did not empty; delivery uncertain |
| 6 | CLOSE_ERROR | Serial close failed; owner must establish cleanup certainty |

Provisional safety caps: startup 5s, whole frame 20s, write 3s, queue drain 15s
within frame budget, graceful close 5s, owned kill/reap 2s. They are safety limits,
not measured production throughput. Diagnostic 90s is not reused. No P6 continuous,
latency/FPS, reconnect or landscape claim is established by fake-provider tests.

## Source API and ownership

`UsbTransport(identity, cancel=None, budgets=Budgets())` performs no I/O during
construction. Its explicit `open()`, `send(RGBFrame)` and `close()` return None
on success; native operation is Windows-only. It is not selected by the app.
Trusted Python-only launcher/gate injection supports isolated tests, never a
shipping backend/endpoint/executable configuration switch.

Repeated open while healthy is idempotent; accepted sends reuse one child and one
serial session. Concurrent send rejects immediately instead of joining a queue.
Close signals cancellation and uses one absolute graceful-close budget, then the
separate bounded owned-reap budget. Failed/partial delivery never auto-resends.
Explicit reopening is possible only after confirmed complete cleanup and fresh
identity resolution. Cancel before startup performs no listener/process/device work.

`owned` stays true while child, creation attempt or channel/native cleanup remains
owned. A late Popen attempt remains retained and never releases its startup gate;
a late child is disposed of before I/O. Failed native CloseHandle leaves the raw
handle reference retryable; no false CLOSED state follows a failed reap/handle close.
`UsbError` has fixed messages plus `delivery_uncertain` and `ownership_uncertain`
flags for future lifecycle integration. Invalid frame input is rejected before new
IPC effects without destroying a healthy session. These are not P5 UI semantics.

Source self-launch uses `python -m mars_display.usb_worker`; frozen launch must use
the current EXE, never EXE `-m`. The reserved internal form is
`--usb-worker <ephemeral-port> <64-hex-nonce>`. It is not an interactive command:
invalid/missing admission exits 2 without output or GUI, and no socket/device I/O
precedes the owned Windows gate. Child stdin/stdout/stderr are explicitly DEVNULL,
so windowed None streams cannot produce a pipe bootstrap/deadlock.

## Frozen qualification boundary

The full windowed EXE has a minimal custom runtime hook, `packaging/usb_bootstrap.py`,
which handles only the reserved worker prefix before PyInstaller's default hooks.
An entrypoint-only dispatch is insufficient: the pinned PySide6 runtime hook imports
QtCore before the application entrypoint. Ordinary arguments are a no-op in the
custom hook and retain all existing Qt/application startup. The strict worker guard
still rejects preloaded Qt/app/settings modules; it has not been weakened.

`packaging/smoke.py` also invokes `usb_smoke.py` against the actual unpacked EXE:
quiet malformed-argument rejection, authenticated HELLO/CLOSE, oversized IPC rejection,
unreleased startup containment and parent-death termination with confirmed reap.
It never sends OPEN or FRAME and never opens a device. The worker gets isolated
state with no SDK/application Python path; the test-owned parent uses source code
only to own the actual packaged child. The source archive carries that fixture.
Windows-only source tests separately use test-owned fake ports for repeated exact
frames, open/write/drain/close hangs and failed raw-handle closure. There is no
shipping fake-backend flag. Windows CI requires zero skipped source tests before
compiling, and existing material/source/publication gates remain in force.

These checks are implemented, not yet observed on Windows. Source injected tests
are not frozen-process proof. Native proof is pending in [the P3 ledger](../odd/tasks/native-usb-helper.md).
