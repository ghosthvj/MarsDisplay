# USB landscape: fixed 480 × 320 image qualified

**The connected unit displayed the complete horizontal reference correctly.**
The owner confirmed the result and supplied a photo showing readable text, the
upward arrow, all four corner markers and the full border. With the text upright,
the USB connector is on the **top edge** of this enclosure, not the left or right.
This qualifies one fixed-image Linux hardware probe, not landscape support in
the released MarsDisplay application. Stable rc4 remains unchanged.

## Evidence

| Check | Observed result |
| --- | --- |
| Device | VID `1a86`, PID `5722`, serial `USB35INCHIPSV2` |
| Geometry | Logical 480 × 320; normal landscape, orientation enum 2 |
| Visual result | Owner: “Sí, todo se ve correcto”; photo independently inspected |
| Host transfer | 307222 bytes, 82 writes, exit 0; empty stderr |
| Close and holders | Success emitted after close; privileged lsof found no holders |
| Device metadata | Owner, group, permissions, major/minor and inode unchanged |
| Offline checks | Nine tests passed; independent repeat and fake failure checks passed |

The image contains `LANDSCAPE`, `480 x 320`, an upward arrow, a white border,
red TL / green TR / blue BL / yellow BR blocks, and an RGB strip. The supplied
photo confirms placement and visible completeness, not calibrated color accuracy.
The photo remains private and is not included in the repository or package.

## Wire protocol and provenance

The primary reference is the RevA implementation at
[revision `2b33ab4f00a096916dd6a1174441a53a7ec33b03`](https://github.com/mathoudebine/turing-smart-screen-python/blob/2b33ab4f00a096916dd6a1174441a53a7ec33b03/library/lcd/lcd_comm_rev_a.py),
with orientation enum/base geometry from `lcd_comm.py` and RGB565 conversion from
`serialize.py` at the same revision. No upstream driver was instantiated.

```text
Orientation (16 bytes): 00 00 00 00 00 79 66 01 E0 01 40 00 00 00 00 00
Bitmap header (6):      00 00 07 7D 3F C5
Pixels:                307200 bytes, RGB565 little-endian, row-major
Chunking:              80 chunks of 3840 bytes; no software rotation
```

The orientation carries logical width 480 and height 320. The bitmap rectangle
has inclusive end coordinates (479, 319). Full wire SHA256:
`6db0b29e5e816b61367abc936b86f38a752953e43b5cb4e6bc7e73a4a0e77727`.

## Execution controls and evidence limits

The owner explicitly authorized scoped sudo for this exact device. One exclusive
serial connection used the previously verified identity/node/descriptor and lsof
guards. A 20-second frame deadline, bounded writes/drain, and outer root GNU
30-second timeout with three-second kill grace bounded execution. No timeout or
retry occurred. Opening and closing serial may affect electrical control lines.

The private helper passed independent review before the hardware action. Its
SHA256 is `a42fae5043545dfef723423e0dac01bb2f5dc8eef05d00ae44a65221161d92d7`.
Its inherited guard remained byte-identical to the earlier qualified helper.
Offline tests caught and corrected an extra zero in initially transcribed
orientation packets before any device access. The final packets are 16 bytes.

Private receipts are under `build/usb-landscape-qualification/hardware-1/`.
No brightness, reset, HELLO, clear, screen-power or firmware command was sent.
No device permissions, groups, drivers, application source or saved settings
were changed. The pattern is left visible after close; no portrait-return action
was performed and the unknown prior image/state was not restored.

Host completion is not a panel acknowledgement. This test does not qualify
reverse landscape, continuous frames, orientation switching, performance,
Windows transport, brightness behavior, power-cycle persistence or other units.
The application suite/build was not rerun because production code did not change.

## Next boundary

Production support still requires separately scoped changes to the native
encoder, IPC geometry validation and configuration, with portrait preservation
checks and a Windows candidate. This qualification does not authorize those
changes or further unattended hardware runs.
