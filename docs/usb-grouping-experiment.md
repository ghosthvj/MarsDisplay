# Isolated USB grouping experiment

This is an **owner-run experiment**, not a change to normal MarsDisplay or a
performance claim. Do not run it unattended. The agent does not run real USB tests.
A separate frozen Windows console delivery is pending T2 qualification; do not
substitute the normal application executable.

## Safe commands

From a source checkout with its existing Python environment:

```text
python -m mars_display.usb_grouping_experiment
python -m mars_display.usb_grouping_experiment --help
python -m mars_display.usb_grouping_experiment --self-test
```

These routes never enumerate devices, open a port, acquire the app lock, or import
Qt/settings. No arguments means help. Self-test checks the frozen public RGB888
fixture's size/SHA-256, packet boundaries, and stream equality. There are no chunk,
profile, fixture-path, repeat, or environment-profile options.

## Owner procedure (Windows only)

1. For a packaged delivery, verify the published artifact SHA-256 and source
   manifest first. Close MarsDisplay **and all vendor/probe software**; the app
   lock cannot exclude unrelated vendor applications. Nothing kills them for you.
2. Explicitly opt in with `python -m mars_display.usb_grouping_experiment --run`.
3. Read the currently resolved COM port. Type exactly the displayed confirmation,
   for example `A COM5`. Empty input, other input, Ctrl-C at a prompt, or EOF
   cancels. Inventory must identify exactly one supported device and no competing
   occupant of that COM port. The child revalidates the confirmed COM at OPEN and
   again before sending; a move after confirmation is rejected, not followed.
4. A sends **one** public pattern. Wait for host success **and known cleanup**.
   Inspect the physical display. Type exactly `A VALID` only if the image is
   correct. Anything else cancels B.
5. Confirm the freshly resolved port for B, for example `B COM5`. B sends one
   frame, then closes. There is no loop, resend, or reconnect.
6. Report each arm's numeric host output and whether the physical image was
   correct. Do not include private images, configuration, URLs, or video.

Both arms use a separate, matching **open → send → close** lifetime. Opening and
closing can toggle DTR; this is not a continuous connection experiment. Neither
arm changes baud/CTS, firmware, brightness, power, orientation mode, or drivers.

A uses 122 writes; B uses 62 writes. Both send the same 307222-byte stream.
See [fixed protocol and worker notes](usb-grouping-protocol.md) for packet
boundaries, fixture hash, admission and frozen-resource requirements.
Reported milliseconds are **host-side**: exchange includes helper work; write
includes orientation/header/pixels. Do not add overlapping stages or interpret
host completion as panel acknowledgement, rendering speed, or panel FPS.

## Failure and exclusion

The experiment reuses `SingleInstanceGuard(SettingsStore())`: the same default
`LOCALAPPDATA/MarsDisplay/marsdisplay.lock`, QLockFile semantics, and dead-process
recovery as the app. It never loads or saves settings. Exclusion spans visual
inspection and both arms, and ends only after owned cleanup is known complete.
Each arm reuses `UsbTransport`, `OwnedWorker`, Windows admission/job ownership,
strict IPC, identity checks, short-write rejection, and existing safety budgets.
Human confirmation is outside transfer deadlines.

Any A open/send/close error or cleanup uncertainty permanently prevents B for
that invocation. If cleanup is uncertain, the console retains the transport and
app lock and retries **cleanup only** every 250 ms (each cleanup attempt retains
the existing reap budget). It does not return to input, resend, or reconnect.
EOF/Ctrl-C cannot release the lock in this state. Do not force-close the console
or restart MarsDisplay while this warning remains. Permanent OS cleanup failure
can therefore leave the console waiting indefinitely; this is intentional rather
than claiming resources are closed.

## Exit codes and fixed messages

Public messages go to stdout; no raw exceptions or private backend details are
printed to either stream. Dynamic output contains only the selected COM and
numeric host counts/timings. Private child rejection is silent (exit 2).

| Code | Meaning / fixed final message |
| --- | --- |
| 0 | Help, successful self-test, or `Experiment complete. Report host numbers and physical image correctness for both arms.` |
| 1 | `Cancelled; no further frames.` |
| 2 | `Invalid arguments. Use --help; no device access.` |
| 3 | `MarsDisplay instance lock unavailable; no device access.` |
| 4 | `Experiment failed; no further frames. No automatic retry.` |

Missing/corrupt fixture, lock setup error, inventory error, or transfer/cleanup
error uses code 4. Cleanup uncertainty additionally prints:

```text
Cleanup uncertain; retaining instance lock and retrying cleanup only. Do not restart MarsDisplay.
```

Code 4 is returned only once owned cleanup is known complete. Self-test success:

```text
Self-test OK: fixed public fixture; A=122 B=62 writes; identical 307222 bytes; no device access.
```

## T2 console entry

Public entry: `mars_display.usb_grouping_experiment.main`. The separate frozen
console must dispatch the private worker before Qt/settings imports; its exact
interface and pending Windows qualification are documented in the
[protocol notes](usb-grouping-protocol.md#frozen-delivery-qualification-boundary).
