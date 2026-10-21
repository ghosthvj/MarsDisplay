# Work with the USB screen

**The standalone C# and Python native Windows portrait diagnostics are
owner-validated for one frame each. MarsDisplay 0.1.4 still uses simulated output
and does not drive this screen.** Use this guide
for the known-good diagnostic; see the [integration proposal](usb-integration-plan.md)
for future application work. P0–P2 are complete, recorded in the
[accepted Python bridge ledger](https://github.com/ghosthvj/MarsDisplay/blob/6bff97befee7b1e72f7afbcef3ab482a89011ea2/odd/tasks/native-python-usb-probe.md).
The authorized **P3 bounded helper is qualified**, tracked in the
[helper ledger](../odd/tasks/native-usb-helper.md) with
[native/source evidence and limits](usb-helper.md#verified-evidence-and-limits).
[P4 API-only configuration](usb-settings.md#verified-p4-evidence-and-limits) is also
qualified; it does not enable native Start or add a selector. Application wiring,
selection UI and continuous hardware qualification (P5–P6) remain unauthorized.
Python physical acceptance still covers only one frozen portrait image.

<a id="python-p2-owner-test-pending"></a>

## Python P2 owner-validated frame

The separate **PythonUsbProbe 1.0.0** package is Windows-qualified, and the owner
provided matching console and physical-image evidence on **2026-10-21**.
**P0–P2 are complete.** MarsDisplay still uses Simulation.
The C# artifact below remains preserved; do not confuse the two executables.

- Source: `a26350dd74d1d03d999bbead5195dfc20d4a5344`.
- [Native CI and seven-day artifact](https://github.com/ghosthvj/MarsDisplay/actions/runs/39512376268):
  70 tests with zero skips, seven source/frozen command checks, startup gate and
  owned-parent-death checks. Parent and independent artifact/source/license readback passed.
- ZIP: `PythonUsbProbe-1.0.0-Windows-x64.zip`, 8,676,348 bytes.
- SHA256: `75a581e017d8b69708f565751b75f1866cf956131ac05592185172a54cece621`.

Extract the whole ZIP and keep `_internal` beside `PythonUsbProbe.exe`. No Python
installation is needed. The documented external prerequisite is official Microsoft
Visual C++ v14 x64 runtime 14.51 or later; do not install it automatically or bypass
Windows security warnings. Close the vendor application and other screen probes.
In PowerShell in the extracted `PythonUsbProbe` folder:

```powershell
.\PythonUsbProbe.exe --self-test
.\PythonUsbProbe.exe --list
.\PythonUsbProbe.exe
```

Self-test must print `Self-test passed: 122 packets, 307222 bytes; no USB access.`
Listing must identify the current `COMn usb:1a86:5722:USB35INCHIPSV2`. At the
interactive prompt, enter that uppercase COM port, then type exactly `SEND COMn`
with its actual number. COM5 is not a default. The 90-second budget includes typing;
empty input cancels without opening. Do not automate confirmation or resend.

Expected completion is exactly:
`Host transfer complete: 122 packets, 307222 bytes; not a rendering ACK.`
The owner observed that exact completion after entering `COM5` and `SEND COM5`.
The accompanying photo visually matches the upright TOP/up arrow, corners 1/2/3/4,
horizontal RGB bands, white bottom-left, black bottom-right and border in
`pattern.png`. The paired evidence closes the Python single-frame P2 gate; the
host message alone is not a rendering ACK. COM5 remains an observation, not a default.
Owner photos remain private and are not embedded in the repository or distribution.

No repeat is needed to close this gate. If a later explicit test fails, preserve
console and photo, stop, and do not automatically resend or change protocol.
Continuous output, latency/FPS, reconnect, landscape and application integration
remain unqualified. P3's bounded helper passed its isolated native qualification,
not application wiring or new physical acceptance. P4 API-only settings are separately
qualified; selector/native composition and hardware qualification remain P5–P6.

The immutable packaged README retains its pre-CI preparation wording. The native
receipts establish packaging qualification; the owner's paired evidence above
separately establishes one-frame physical acceptance. This current record supersedes
the historical pending wording without modifying the qualified ZIP.

## Previously accepted C# path: Windows 11 x64

1. Close the vendor application and other serial applications. Reconnect the
   screen and check its current port in Windows Device Manager.
2. Download the [qualified diagnostic artifact](https://github.com/ghosthvj/MarsDisplay/actions/runs/39487850312/artifacts/12294995150),
   extract the Actions wrapper and the entire contained diagnostic ZIP into a
   separate folder. Verify hashes below; retain source and verification metadata.
3. Inspect `pattern.png`: portrait TOP/up arrow, numbered corners 1/2/3/4,
   horizontal red/green/blue bands, white bottom-left, black bottom-right, border.
4. In PowerShell in the extracted diagnostic directory, run:

   ```powershell
   .\UsbScreenProbe.exe --help
   .\UsbScreenProbe.exe --self-test
   .\UsbScreenProbe.exe --list
   ```

   These do not open USB. Self-test should report
   `PASS: embedded pattern and protocol: 122 writes, 307222 bytes; no USB opened.`
5. Confirm the current device is `USB\VID_1A86&PID_5722\USB35INCHIPSV2`,
   with `health=0`. Run ` .\UsbScreenProbe.exe` without arguments to choose it,
   or use the following **only if COM5 is currently that verified device**:

   ```powershell
   .\UsbScreenProbe.exe --port COM5
   ```

   Type exactly `SEND COM5` at confirmation. COM5 is an example, not a default
   or permanent identity. Enter/EOF at selection or a different confirmation
   cancels without opening a port. Do not automate confirmation.
6. Photograph the physical result and final console. Success is exactly:

   ```text
   307222 bytes drained to the serial output and port closed; not a rendering ACK. Photograph the screen. Check the device before another run.
   ```

   Compare the entire physical image with `pattern.png`, not merely console success.
   Stop and inspect before any further explicit run; there is no retry.

The diagnostic needs no Python installation, SDK, administrator access, driver
installation or security bypass. If SmartScreen or another policy blocks it,
stop and report the warning to the owner; do not disable protection. A no-argument
interactive launch pauses at the final prompt. The worker's **90 seconds includes
human input**, inventory, transfer and close; termination gets up to two more
seconds. The parent's final Enter prompt is outside that budget.

## Identify this unit, not a whole product family

| Observation | Meaning / limit |
|---|---|
| Label | SHCHV TUS-35; USB Screen; Input DC 5V 100mA; IP30 indoor. Label rating, not measured current. |
| Boot display | `PLEASE RUN THE APP WWW.TURZX.COM` |
| USB | VID `1A86`, PID `5722`, serial `USB35INCHIPSV2` |
| Earlier C# owner test | COM5, exact WMI identity, health 0; explicit selection and typed confirmation worked. |
| Python owner test | 2026-10-21: COM5, typed SEND COM5, 122 packets/307222 bytes completed; matching reference photo. |
| Qualification | One frozen 320×480 portrait frame through each standalone C# and Python diagnostic; no continuous-output claim. |

VID/PID are shared by protocol A/B devices; they do not select a protocol.
The serial may be reused across units. Missing, unknown or duplicate identities
must not lead to first-device selection or opening an old COM occupant. The probe
requires exactly one known identity and rejects unhealthy or ambiguous inventory.
WMI uses `Win32_SerialPort` in `root\cimv2`; other drivers/units remain unqualified.

## Obtain and verify the frozen delivery

Diagnostic **1.0.0** is not MarsDisplay **0.1.4**. Qualified source is
[`8227c002a48084d8c463400f45cd641f62359bb4`](https://github.com/ghosthvj/MarsDisplay/tree/8227c002a48084d8c463400f45cd641f62359bb4).
[Native CI run 39487850312](https://github.com/ghosthvj/MarsDisplay/actions/runs/39487850312)
passed 50 native assertions and seven actual public CLI commands. Delivery/source
hashes were checked; 166 local regressions and independent S1–S4 verification are
recorded in the [diagnostic ledger](https://github.com/ghosthvj/MarsDisplay/blob/0b92565c10996276af5b9ad61a7c85bfc26df327/odd/tasks/native-usb-probe.md). These are
historical evidence, not checks rerun for this documentation.

Artifact 12294995150 expires **2026-10-27T19:57:44Z**; GitHub sign-in may be
required. Expiry does not delete an already verified local copy. If unavailable,
use the pinned source and Windows build instructions below, not a similarly named
unverified executable. A new build needs its own verification and hashes.

| File | Bytes | SHA256 |
|---|---:|---|
| `UsbScreenProbe-1.0.0-Windows-x64.zip` | 80681 | `43fa275e13eef7a4da82c3770f00d8a4be3731d3bc2013ced79bf1258b48fa74` |
| `UsbScreenProbe.exe` | 327168 | `2ee5bfd797de61806121cf701e529edc692eab2ff7a42c1a34a2a260903a4c13` |

```powershell
Get-FileHash .\UsbScreenProbe-1.0.0-Windows-x64.zip -Algorithm SHA256
# After extracting the inner ZIP, run in its directory:
Get-FileHash .\UsbScreenProbe.exe -Algorithm SHA256
Get-FileHash .\pattern.png -Algorithm SHA256
```

Compare the inner ZIP against its adjacent `.sha256`, and each extracted file
against `SHA256SUMS`. Keep `nativeverification.json`, `source.zip`, LICENSE and
reference files. Hashes bind content, not publisher authenticity: also check the
workflow/source commit. Documentation updates do **not** rebuild this EXE or
change its ZIP/hash; its bundled README and manifest retain historical pending
wording. Closing ledger commit was `c6ba31d`.

Workspace-only verified copy (local path, not a public download):
`build/native-usb-probe-delivery/candidate-8227c00/verified/`.

For a fresh Windows checkout of the pinned source, use inbox .NET Framework 4.8
Framework64 compiler and PowerShell 7:

```powershell
./tools/windows-usb-probe/build.ps1
```

The [build/diagnostic README](https://github.com/ghosthvj/MarsDisplay/blob/0b92565c10996276af5b9ad61a7c85bfc26df327/tools/windows-usb-probe/README.md) explains fresh
output-directory requirements, harness, CLI checks and package contents. There is
no download/install step in the script. Do not compile or execute this Windows
EXE on Linux and call that native qualification.

## Exact portrait transfer and provenance

The [native implementation](https://github.com/ghosthvj/MarsDisplay/blob/8227c002a48084d8c463400f45cd641f62359bb4/tools/windows-usb-probe/Probe.cs) sends only:

| Part | Bytes / layout |
|---|---|
| Orientation | `00 00 00 00 00 79 64 01 40 01 E0 00 00 00 00 00` (16 bytes) |
| Image header | `00 00 04 FD DF C5` (6 bytes) |
| Image | 307200 RGB565 little-endian bytes, row-major, top-to-bottom, left-to-right |
| Chunking | 120 payload writes × 2560 bytes; 122 writes / 307222 bytes total |

RGB888 conversion is `((R >> 3) << 11) | ((G >> 2) << 5) | (B >> 3)`, low byte
first. Serial options are 115200 baud, 8N1, RTS/CTS, DTR enabled, three-second
write timeout and 15-second queue-drain deadline. Queue-empty plus close return
is **host completion**, not a panel ACK. Opening/closing may change DTR.

No reads, HELLO, reset, clear, power, brightness, firmware writes, automatic retry,
buffer/timing experiments or protocol fallback are performed. Framework close
may block: a startup-gated, kill-on-close Windows job contains only the probe's
own child. No vendor process, user browser or other process is killed by name.

The [manifest](../tools/windows-usb-probe/pattern.json) and
[public expected PNG](../tools/windows-usb-probe/pattern.png) freeze Linux Chromium
156.0.8078.4 / Playwright 1.64.0 output; the native EXE embeds it without redrawing.

- Payload SHA256: `8cbbb7e39485e211548a4f3f448ca14eeb9358286e5eadf7079a324fdc97ed1d`.
- PNG SHA256: `d8efdd4339e8c16a8f2b7e1416ec83221403cf6bdc6571ee5ff146113f00cfbc`.
- Primary protocol reference: upstream GPL-3.0
  [`lcd_comm_rev_a.py`](https://github.com/mathoudebine/turing-smart-screen-python/blob/2b33ab4f00a096916dd6a1174441a53a7ec33b03/library/lcd/lcd_comm_rev_a.py),
  with [`lcd_comm.py`](https://github.com/mathoudebine/turing-smart-screen-python/blob/2b33ab4f00a096916dd6a1174441a53a7ec33b03/library/lcd/lcd_comm.py)
  and [`serialize.py`](https://github.com/mathoudebine/turing-smart-screen-python/blob/2b33ab4f00a096916dd6a1174441a53a7ec33b03/library/lcd/serialize.py).
  Preserve license/provenance notices when adapting code; not all controls are qualified.

## Evidence boundaries and troubleshooting

On **2026-10-20**, the owner said `ahora si!!!`; parent-inspected photos show the
correct portrait image and successful native console. Local-only evidence locators:
`.herdr-web-ui/paste-20261020-201553-d37f1cd1.png` (panel) and
`.herdr-web-ui/paste-20261020-201607-e797f79c.png` (console). These are not repository
assets or public links. Physical acceptance occurred after CI, not inside CI.

Both the initial Chrome HTML probe and its drain-corrected version corrupted the
physical output despite reporting 307222 bytes written/drained. Missing
`writer.close()` was real but insufficient. The precise Chrome/driver/delivery
cause is unknown; neither bad hardware nor generally broken Chrome is established.
Windows canvas versus frozen Linux canvas byte identity is also unproven.

The owner reported successful vendor-app rendering. Static inspection identified
UsbMonitor 2.2.1.0 x64/.NET 4.8 from `https://down.turzx.com/35inchENG.rar`, SHA256
`c734371b34ae7f900883ac5696ff6a8a85d0b954ce00ff4ffc2b3fa049f9f8ea`.
The agent never executed it. The archive in ignored `build/vendor-35inch-static`
is not a runtime dependency; do not publish vendor binaries, certificates or
private-key resources. Vendor success is separate from native qualification.

| Exit / symptom | Safe next action |
|---|---|
| 0 | Read text: help/list/self-test/cancellation also return 0, not just transfer. |
| 2 / E2 | Invalid arguments; use `--help`, uppercase COM plus a positive number. |
| 3 / E3 | WMI inventory unavailable; check Device Manager/reconnect, no elevation/driver install. |
| 4 / E4 | Missing/wrong/unhealthy/duplicate identity; stop and identify the device. |
| 5 / E5 | Embedded fixture invalid; obtain verified build; no port opened. |
| 6 / E6, busy port or partial image | Transfer/cleanup uncertain; close competing apps, inspect screen and reconnect before considering a new explicit run. |
| 7 / E7 | Startup/unexpected worker failure; check verified build and screen. |
| 8 / E8 | Timeout; distinguish confirmed termination from uncertain termination. If unconfirmed, do not rerun; close probe and check Task Manager/screen. |

Exact sanitized errors and outcomes are in the [command reference](https://github.com/ghosthvj/MarsDisplay/blob/0b92565c10996276af5b9ad61a7c85bfc26df327/tools/windows-usb-probe/README.md)
and source. Do not blindly resend or try protocol variants. Enumeration immediately
before open reduces but cannot eliminate a COM hotplug race. Report diagnostic
version/hash, command, exit code, sanitized final message, target-device metadata
and pattern discrepancy. Crop unrelated inventory/Bluetooth identifiers and private
URLs/content from shared console/photos; never upload owner frames by default.

Continuous output, landscape, reconnect, performance, other units and all other
commands remain unqualified. The next step is the gated proposal, not production use.
