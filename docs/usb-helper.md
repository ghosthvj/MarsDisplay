# P3 bounded native USB helper

P3 is under implementation. The framing and serial-session core are tested with
fake providers; owned process admission, public UsbTransport and actual frozen
Windows routing are not yet qualified. MarsDisplay still composes Simulation.
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

The remaining owned controller must retain late Popen/failed handle/reap ownership
and reject reopen/success until cleanup is known; only its child may be terminated.
The frozen private route must run before app/Qt/settings startup. These remaining
requirements are tracked in [the P3 ledger](../odd/tasks/native-usb-helper.md).
