# Pure portrait packet encoding

`mars_display.usb_protocol.encode_portrait(frame: RGBFrame) -> tuple[bytes, ...]`
encodes the proven **320x480 portrait profile** without I/O or caller mutation.
Import it directly from that module; application defaults remain Simulation.

## Packet contract

The result is an immutable tuple of immutable bytes, in transmission order:

| Index | Content | Bytes |
|---|---|---:|
| 0 | `00 00 00 00 00 79 64 01 40 01 E0 00 00 00 00 00` | 16 |
| 1 | `00 00 04 FD DF C5` | 6 |
| 2–121 | Top-to-bottom RGB565LE payload, 120 chunks | 2560 each |

Total: **122 packets, 307222 bytes**. RGB888 channels are truncated to
5 red, 6 green and 5 blue bits, packed as `(R >> 3) << 11 | (G >> 2) << 5 | (B >> 3)`,
then emitted low byte first. There is no rotation, resampling or profile inference.

## Rejected inputs

Validation runs before encoding and leaves the caller unchanged:

| Exception | Exact message |
|---|---|
| `TypeError` | `frame must be an RGBFrame` |
| `TypeError` | `width and height must be integers` |
| `ValueError` | `geometry must be 320x480 or 480x320` |
| `TypeError` | `rgb must be bytes` |
| `ValueError` | `rgb length must equal width * height * 3` |
| `TypeError` | `captured_at must be a number` |
| `ValueError` | `captured_at must be finite and non-negative` |
| `ValueError` | `portrait encoding requires 320x480 geometry` |

The existing shared frame validator runs before the portrait-only check.
`RGBFrame` and `SimulatedTransport` still accept valid 480x320 landscape frames.

## Evidence and boundary

Tests compare every payload byte against the frozen
[RGB565 fixture](../tools/windows-usb-probe/pattern.rgb565), using the frozen
[RGB888 source](../tools/windows-usb-probe/pattern.rgb888).
See the [working USB guide](usb-screen-guide.md) and
[accepted P0–P2 plan](usb-integration-plan.md).

This API performs no enumeration, port access, file reads, settings changes or
GUI work. It has no counters or stored state. Identity selection, process
supervision, native packaging and physical acceptance belong to later stages;
encoding success is not evidence of delivery or display rendering.
