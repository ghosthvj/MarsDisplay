# Prepare a fixed-image USB screen check

Open `usb-screen-probe.html` locally in Windows desktop Edge or Chrome. This standalone tool prepares a **single portrait image test** for a known SHCHV TUS-35 / USB35INCHIPSV2; it does not integrate with MarsDisplay or qualify hardware. No Python, server, installation, network access, administrator access, or firmware changes are needed by the tool.

## Quick path

1. Close the vendor display application and any other program using the port. Disconnect other matching USB displays.
2. In Device Manager, visually confirm your known SHCHV TUS-35 / USB35INCHIPSV2 and its current COM port. The owner's current port is **COM5**, but it is not hardcoded and can change.
3. Open the HTML file in desktop Edge/Chrome. Check the confirmation box, click **Choose screen and send one fixed image**, and select that screen in the native browser chooser. Cancel if unsure.
4. Compare the physical display with the preview: portrait **320 × 480**, TOP at the top, red/green/blue bands, white lower-left and black lower-right, white border, and asymmetric corners numbered 1–4. Check for rotation, mirroring, swapped colors, and incomplete rows.
5. Photograph the screen and record the browser, current COM port, and visible result before deciding whether integration is appropriate. Successfully drained output is **not** proof that the screen rendered correctly.

## Safety and recovery

- The chooser filters VID/PID **1A86:5722** and the page checks those IDs again before opening. These IDs are also shared with protocol B devices: this is not a protocol detector.
- Web Serial does not expose a USB serial number or COM number to the page. Identity confirmation is **your visual verification**, not automatic stable identity. Do not proceed with an unknown device merely because it appears in the chooser.
- Each page load permits only one selection/send attempt, including cancellation. There is no enumeration, auto-reconnect, retry, or send on load/reload.
- Cancellation or wrong IDs send nothing. A busy/open error means you should close vendor apps and other port users. Do not install drivers or elevate privileges as a workaround for this test.
- A write or drain failure/timeout may leave a **partial or uncertain transfer**. Disconnect/reconnect the device before considering a reload and a new explicit attempt. Do not blindly resend. If cleanup is uncertain, the button stays disabled; inspect the device and disconnect/reconnect before reload.
- Open, each write, and the final stream drain each wait at most 3 seconds; port cleanup waits at most 1 second. A late successful open is closed when it resolves. The chooser itself remains under user control. Native operations cannot always be cancelled; these bounds stop UI waits, not underlying OS activity.
- Unsupported or non-secure-context browsers keep the preview but disable sending. Use a supported desktop Edge/Chrome configuration. Browser policy may still block Web Serial; do not bypass security settings, install anything, or run a server to force this test.
- The screen may retain the image when the port/page closes. There is **no restoration or clear** operation.

## Exact transfer and provenance

| Item | Value |
| --- | --- |
| Serial options | 115200 baud, 8 data bits, 1 stop bit, no parity, hardware flow control |
| Orientation | Portrait = 0; 16 zero-initialized bytes with offsets 5–10 = `79 64 01 40 01 E0` (hex) |
| Image header | `00 00 04 FD DF C5` |
| Image payload | 307200 bytes, row-major RGB565 **little endian**, converted from the actual preview pixels |
| Payload writes | 120 chunks of 2560 bytes |
| Total | 307222 bytes including orientation and header |

Only the orientation command and one full image are written. There are no reads, HELLO, reset, clear, brightness, power, or firmware commands. After all 122 writes, the page awaits `writer.close()` to drain buffered serial output, then releases the writer lock and attempts bounded `port.close()` cleanup. Only a resolved drain permits the success label; it is not a USB rendering acknowledgment.

Exact status after a successful drain and cleanup:

> 307222 bytes drained to the serial output; not a rendering ACK. Photograph the screen. Reload only after checking the device.

While drain is pending, the status is `Draining serial output. Do not disconnect during the transfer.` There is no success label or port close yet. Drain rejection/timeout with successful cleanup reports:

> Drain failed or timed out; delivery uncertain, possible partial image. Disconnect/reconnect before retrying. Reload only after checking the device.

If cleanup also fails or times out, the final sentence instead reads `Cleanup uncertain; possible partial transfer. Check/disconnect/reconnect the device before reload.` The one-shot latch remains set on every outcome; there are no retries.

Writes may resolve while bytes are still buffered. The [Web Serial writable/close lifecycle](https://serial.spec.whatwg.org/) and [Chromium serial sink](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/modules/serial/serial_port_underlying_sink.cc) distinguish stream drain from port closure. The correction adds only this bounded drain; protocol bytes and serial options are unchanged.

Protocol details are derived from the GPL-3.0 upstream project `mathoudebine/turing-smart-screen-python`, pinned to commit `2b33ab4f00a096916dd6a1174441a53a7ec33b03`:

- [lcd_comm_rev_a.py](https://github.com/mathoudebine/turing-smart-screen-python/blob/2b33ab4f00a096916dd6a1174441a53a7ec33b03/library/lcd/lcd_comm_rev_a.py): orientation, image framing, RGB565 and chunking.
- [lcd_comm.py](https://github.com/mathoudebine/turing-smart-screen-python/blob/2b33ab4f00a096916dd6a1174441a53a7ec33b03/library/lcd/lcd_comm.py): serial configuration (`115200`, `rtscts=True`).

This provenance is recorded without changing the repository license. The utility is deliberately separate from the existing simulated transport, application settings, and dependencies. No publishing is part of this preparation.

## Automated evidence versus hardware evidence

`tests/test_usb_screen_probe.py` opens the actual HTML in headless Chromium with a synthetic Web Serial implementation installed before page load. It checks the public controls, exact generated bytes against every canvas pixel, one-shot behavior, failure cleanup, and absence of network or page errors. Its synthetic sink models buffered output: port closure discards pending bytes unless stream drain finished. It checks all 122 writes before drain, unlocked port cleanup, pending drain, and drain rejection/timeout. This models transport loss, not native reception. It never accesses a real serial device.

Development-only focused command (using the existing environment and browser cache):

```sh
PLAYWRIGHT_BROWSERS_PATH=/my-projects/pantalla/.cache/playwright .venv/bin/python -m unittest tests/test_usb_screen_probe.py
```

The owner's first Google Chrome run produced a visibly corrupted physical image in the supplied photograph despite reporting `307222 bytes written; not a rendering ACK. Photograph the screen. Reload only after checking the device.` That version released the writer and closed the port without awaiting stream drain. Missing drain is a confirmed lifecycle defect, **not a proven root cause of all photographed corruption**. The corrected probe awaits an owner rerun; no successful hardware result is claimed.

Hardware rendering, Windows chooser behavior, and device compatibility still require the user's physical check and photograph. Automated success is not hardware qualification.
