# Prepare one Linux USB timing measurement

This source-only command sends **one manually confirmed baseline A frame** from
our verified public fixture. Preparation is not execution authorization. No Linux
packaged binary is qualified for this measurement. The normal application and
Windows experiment are unchanged.

## Safe check now

From the repository, using the existing environment (no installation needed):

```sh
.venv/bin/python -B -m mars_display.linux_usb_measurement --help
.venv/bin/python -B -m mars_display.linux_usb_measurement --self-test
```

No arguments also shows help. Help and self-test do not enumerate devices, import
serial or Qt, or open ports. Self-test verifies the fixed public fixture and A
encoder: portrait 320x480, 122 writes, 307222 bytes. There are no fixture, port,
serial-setting, repeat, B-arm, or retry options.

## Future owner-run measurement — separate authorization required

1. Obtain separate permission/execution authorization before the first run.
   This guide does not authorize permission changes; if access is denied, stop.
2. Close the normal application, Windows tools, and every other serial consumer.
   Linux `exclusive=True` is a cooperative/advisory lock, not protection against
   non-cooperating programs. Opening with DTR asserted can affect the device.
3. After authorization, run this command yourself:

   ```sh
   .venv/bin/python -B -m mars_display.linux_usb_measurement --run
   ```

4. Check the displayed current port against the intended device. For a currently
   confirmed `/dev/ttyACM0`, type exactly `SEND /dev/ttyACM0` at the prompt.
   If the current confirmed port differs, use the exact displayed confirmation;
   do not assume the old port is still correct. EOF, Ctrl-C at the prompt, or any
   other answer cancels without opening. Do not pipe an automatic confirmation.
5. Physically inspect the panel: report whether the public portrait pattern is
   correct, together with command exit status and the complete timing line.
   No screenshot is required. If output fails or the image is wrong, stop; do not
   rerun automatically or infer successful delivery.

## What is measured

The fixed identity is VID `1a86`, PID `5722`, serial `USB35INCHIPSV2`. It must
resolve uniquely to `/dev/ttyACM[0-9]+`, with one observed occupant. Identity is
rechecked after confirmation before opening and again immediately before writes.
Descriptor checks reduce accidental selection; they cannot eliminate a physical
hotplug race or prove panel compatibility.

| Stage (host seconds) | Meaning |
| --- | --- |
| open | Serial open, with 115200/8N1, RTS-CTS, DTR true, DSR-DTR false |
| encode | Fixed fixture validation/loading and baseline packet encoding |
| orientation/header/pixels | Time spent submitting each packet group |
| write | All 122 writes together, excluding identity resolution |
| drain | Polling the host output queue to zero, not panel acknowledgement |
| close | Successful serial close |

These are separate open/send/close lifetimes, not steady-state streaming. Compare
`pixels * 1000` to the Windows baseline of approximately **2400 ms pixels** only
as host-side context. Linux measurements and physical image correctness remain
unverified. USB full-speed 12M is a link rate, not application throughput; these
numbers establish neither panel latency nor FPS.

## Failure and ownership limits

Each write must accept exactly its packet length, with a 3-second serial write
timeout. The frame budget is 20 seconds; queue drain has at most 15 seconds and
cannot exceed the frame deadline. No unbounded `flush()` is used. A parent
supervises exactly one forked child with a 30-second whole-operation safety
budget, including potentially blocked open/close. The child arms Linux parent-
death SIGKILL and checks its expected parent before serial I/O; failure stops it.
There is no shell, private worker CLI, reset, tuning, or automatic retry.

On timeout or interruption the parent sends SIGKILL only to its owned child and
reaps it. SIGINT is blocked during each waitpid/reaped-state update so a pending
interrupt cannot cause a signal to an already-reaped, potentially reused PID.
Kernel-delayed exit can outlast the safety budget: the parent retains
ownership, warns that cleanup is not confirmed, and waits only for cleanup (even
through repeated Ctrl-C or broken output). It never starts another transfer.
Do not treat the budget as a guarantee of immediate kernel resource release.

Timing output requires successful close, successful child exit, validated numeric
results, and confirmed reap. Failures return exit 4 with no timings and warn that
partial delivery may be uncertain. Cancellation returns 1; invalid arguments
return 2; help, self-test and successful measurement return 0. Backend exception
details are withheld. Even successful host completion requires the owner's
physical image check; draining the host queue is not proof of panel delivery.

## Offline verification boundary

The focused tests use fake inventory/serial and real owned children with fake
measurement only. They cover exact bytes/options, cancellation, identity changes,
frame/drain deadlines, failures, invalid child results, timeout, repeated
interrupts, broken output and reap. No real tty is opened during verification.
Standard unittest discovery loads command tests on every platform and ownership
tests only on Linux, without adding skipped tests to the Windows zero-skip
pipeline. Linux-only ownership tests are not Windows process-lifetime proof.
Preparation verification passed: 17 focused tests with no skips, independent
wire/command/admission and actual fake-child parent-death probes, and the full
326-test regression run (322 passed, four existing Windows-only skips). An initial
full-suite attempt aborted before tests because Qt's default xcb plugin could not
initialize; the final run used the project's existing `QT_QPA_PLATFORM=offscreen`
configuration without installing anything. These are offline source checks, not
Linux hardware timing or native Windows qualification. Hardware execution and
permission changes were outside that preparation scope. The owner subsequently
authorized one controlled real run; see the [first hardware result](linux-usb-measurement-results.md)
for observed host timings, unchanged device metadata and pending visual validation.
That separate execution authorization is not an unattended-run permission.
