# Isolated USB brightness qualification

**The corrected image-first test qualifies visible brightness control on this connected unit at the requested nonzero levels.** The owner confirmed the physical reference image before brightness, the visible brightness changes, and that the pattern remained visible after close. Two earlier exploratory runs lacked a controlled reference and are not the basis for this physical qualification. This is not application integration or an unattended-run authorization.

## Initial brightness-only runs

- Device: VID `1a86`, PID `5722`, serial `USB35INCHIPSV2`, uniquely selected on the expected Linux tty.
- Scoped privileged execution was explicitly authorized. Device permissions/groups and drivers were not changed.
- Each run used one serial lifetime: 115200, 8N1, RTS/CTS enabled, DSR/DTR flow control disabled, DTR asserted, advisory exclusive open.
- Identity, device node and descriptor checks preceded writes; the privileged holder scan was clear before opening.
- These two initial runs each submitted only four brightness commands (24 bytes), totaling 48 protocol bytes. They sent no image, orientation, HELLO, reset, power-off or firmware commands, so their visual result lacked a controlled baseline.
- Opening/closing serial can affect control lines; absence of a reset command does not prove absence of electrical side effects.

## Protocol provenance

The pinned upstream RevA implementation at revision
[`2b33ab4f00a096916dd6a1174441a53a7ec33b03`](https://github.com/mathoudebine/turing-smart-screen-python/blob/2b33ab4f00a096916dd6a1174441a53a7ec33b03/library/lcd/lcd_comm_rev_a.py)
defines command 110 (`6E`) and calculates:

```text
absolute = int(255 - ((level / 100) * 255))
packet = [absolute >> 2, (absolute & 3) << 6, 0, 0, 0, 0x6E]
```

The scale is inverted: absolute zero is brightest. No vendor driver was instantiated or imported, avoiding its initialization and automatic-retry paths.

## Executed sequence

| Requested level | Exact six-byte packet | Cumulative host-accepted bytes per run |
| --- | --- | --- |
| 100% | `00 00 00 00 00 6E` | 6 |
| 60% | `19 80 00 00 00 6E` | 12 |
| 25% | `2F C0 00 00 00 6E` | 18 |
| 100% | `00 00 00 00 00 6E` | 24 |

Three observation pauses of four seconds were programmed between writes. Zero/off was never requested. The final 100% is a requested visible endpoint, **not restoration of the unknown original setting**.

## Observed host result

- Each hardware action completed in approximately 12 seconds with exit 0; both output captures exited 0 and stderr was empty.
- In each run, all four writes returned the full six-byte count and bounded host output-queue checks completed.
- Each success event was emitted only after serial close returned. Privileged holder scans after both runs found no open holders.
- Device metadata remained UID 0, GID 20, mode 0660, character major 166/minor 0.
- The outer root timeout was 35 seconds with a three-second kill grace. It did not trigger. No repeat/reopen/restoration-on-failure path was exercised.
- Host drain/completion is **not** a panel acknowledgement. No actual brightness readback, luminance measurement, linearity or power-cycle persistence test was performed.

Private operational evidence is retained under ignored `build/usb-brightness-qualification/parent/`; the second run is isolated in its `repeat-1/` subdirectory so the first evidence remains intact. The private probe SHA-256 is `01da87120e31336ad865825e6d265651ecdba7973370e7a5e706db26a3920b79`.

## Safety verification and limits

The private probe's requested plan first failed a meaningful offline assertion, then passed eight fake-only tests. Independent verification repeated all eight tests and an isolated self-test successfully; it checked exact packets, admission, identity/descriptor rechecks, partial-failure stop, bounded drain and close-before-success. No application commands or source changed, so an application-wide regression suite was not applicable.

Initial verification was blocked by a full temporary filesystem, not a device failure. Explicitly authorized cleanup preserved active resources; a bounded tracked-file snapshot then provided isolation without copying the ignored build tree. The hardware action started only after independent verification passed.

Any timeout, partial write, disconnect or uncertain close would require stopping without automatic retry, reopening or further restoration writes. A timeout cannot guarantee immediate kernel cleanup.

## Corrected image-first run

The owner reported seeing some change but only black/URL content on the panel and correctly identified the missing reference image. That feedback does not qualify the earlier visual method. The owner then authorized a fixed white/grays/RGB/checker pattern, physical confirmation before brightness and one open connection throughout.

- A separate fixed-image helper passed seven fake-only tests and an independent isolated repeat of those tests plus self-test. Its source SHA-256 is `e5a19a6b5bc63f9da2355a64734a33a4b455f599b01f54f329129b85762b276e`; the original brightness helper remained unchanged.
- Image upload: one proven 16-byte portrait orientation, six-byte bitmap header and 307200 RGB565LE pixel bytes: 122 writes / 307222 bytes. Complete image-wire SHA-256: `22d4931202fcdfcf511a6cb0136f0814219bbc0330e79e3de804c67eb5762fc3`.
- After the full image and bounded drain, the helper held the same port open and waited for an actual human decision. The owner explicitly selected that the physical pattern was correct and visible; only then was a fresh, matching, timely approval released. No brightness command preceded that checkpoint.
- The same connection then carried the four 100/60/25/100 requests: 24 additional bytes, with three four-second pauses. No second image or reopen occurred.
- The complete action exited 0 after approximately 2 minutes 11 seconds, including the human wait, with 126 writes / 307246 bytes, empty stderr and success only after close. Output capture also exited 0. The outer 180-second timeout did not trigger.
- The post-run holder scan was clear and device ownership/mode remained unchanged. No reset, HELLO, power or firmware command was sent.

The 120-second visual gate rejected stale, pre-upload, cancelled, mismatched or late approval; tests and independent review verified these guards. Private evidence is under the ignored `parent/pattern-1/` directory. Neither the approval nonce nor private environment data is published here.

## Physical observation

**Reference visibility, visible brightness changes and image retention after close: owner-confirmed in the corrected run.** The owner's final response was:

> si, se vieron los cambios del brillo y aun se muestra la imagen de prueba

Together with the earlier explicit physical-pattern checkpoint, this supports a limited successful qualification for this unit and the requested 100/60/25/100 sequence. It does not establish exact physical percentage, luminance calibration, behavior at untested levels (including zero), power-cycle persistence, other models, or a Windows implementation. No brightness ACK or current-value getter was established; 100% remains the final requested endpoint, not restoration of the unknown original value.

No GUI control, application transport change, packaged executable, production deployment or firmware modification is included. Any integration into MarsDisplay requires separate scope; no further device command is needed to close this test.
