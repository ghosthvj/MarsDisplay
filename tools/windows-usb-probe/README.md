# Native Windows fixed-image probe

`UsbScreenProbe.exe` version **1.0.0** is a separate, portable x64 Windows 11 diagnostic using inbox .NET Framework 4.8. No Python, SDK, installation, administrator access or external DLL is required on the owner's PC. It sends one frozen portrait image, not a slideshow. It does not change MarsDisplay or execute vendor code.

**One portrait frame owner-validated (2026-10-20):** native CI, downloaded source/hash verification and independent checks passed; the owner subsequently confirmed WMI selection and correct physical rendering with `ahora si!!!`. This is not continuous output or MarsDisplay USB integration. See the [working guide](../../docs/usb-screen-guide.md) for the qualified artifact, hashes, evidence limits and troubleshooting, and the [integration proposal](../../docs/usb-integration-plan.md) for future gates. CI never opens a serial device.

The frozen artifact source is `8227c002a48084d8c463400f45cd641f62359bb4`. Its bundled historical README still says qualification pending. This documentation update does not modify the ZIP/hash or rebuild the EXE.

## Quick path

1. Extract the ZIP. Check its adjacent `.sha256` checksum and the extracted `SHA256SUMS` using `Get-FileHash -Algorithm SHA256`. Keep `nativeverification.json` and `source.zip` with it. The metadata identifies the exact source commit and executable hash; the console version is the diagnostic's version, not MarsDisplay's.
2. Close other serial applications, including the vendor application. Inspect `pattern.png` as the expected reference.
3. Double-click `UsbScreenProbe.exe`, or run `UsbScreenProbe.exe --list` in a terminal. Inventory is passive. Locate the current COM port for **VID 1A86 / PID 5722 / serial USB35INCHIPSV2**, healthy status `0`.
4. Choose that current port, or run `UsbScreenProbe.exe --port COM5` **only if COM5 is currently the verified device**. COM5 is an example, never a default. Type the exact confirmation shown, e.g. `SEND COM5`. Enter, EOF, or any other confirmation cancels without opening a port.
5. Photograph the screen after the result. Even success reports only host queue drain and completed close, **not a rendering ACK**. Check the device before a new explicit run; there are no automatic retries.

A double-click/no-argument session stays visible at the final “Press Enter to close” prompt only when input is interactive. Redirected CI input never pauses there. There is a **90-second worker budget including inventory, typing, writing, draining and closing**, followed by at most a two-second termination check. The final parent “Press Enter” prompt is outside that budget.

## Commands and outcomes

| Command | Behavior |
|---|---|
| `--help` | Usage, no device access |
| `--list` | Passive WMI observations only, never opens a port |
| `--self-test` | Embedded hash/length and protocol check, no USB |
| `--port COMn` | Strict uppercase numeric COM name, identity check, typed confirmation and recheck |
| No arguments | Passive list, explicit choice, same confirmation and recheck |

No arbitrary image input or public worker mode is supported. The internally marked child still runs exactly the same selection and confirmation logic; the marker is an accidental-entry guard, not a security boundary against a local process owner.

| Exit | Meaning and action |
|---|---|
| 0 | Help/list/self-test, cancellation, or completed transfer; read the text to distinguish |
| 2 / E2 | Invalid arguments; follow printed usage |
| 3 / E3 | WMI serial inventory unavailable; check Device Manager/reconnect, without elevation or driver installation |
| 4 / E4 | Missing, ambiguous, wrong or unhealthy identity; check current COM and metadata |
| 5 / E5 | Corrupt embedded fixture; obtain a verified build; no port opened |
| 6 / E6 | Open/write/drain/close failure; delivery uncertain, check screen and other serial apps |
| 7 / E7 | Worker startup or unexpected execution failure; obtain a verified build/check the screen |
| 8 / E8 | Worker timeout; read whether termination was confirmed. If not, do not rerun; check Task Manager and the screen |

The probe requires `Win32_SerialPort` in `root\cimv2` to expose `DeviceID`, `PNPDeviceID`, and `ConfigManagerErrorCode`. The known USB instance must match exactly, ignoring letter case; substring matches and interface/suffix variants are intentionally rejected. The owner's tested setup exposed that WMI class and identity. Other drivers may not: this remains an acceptance uncertainty elsewhere, not permission to try a different port or install a driver. Metadata is rechecked immediately before open, but an unavoidable hotplug race remains between enumeration and opening by COM name.

## Fixed transfer and containment

- 115200 baud, 8 data bits, no parity, one stop bit, RTS/CTS handshake, DTR enabled, 3000 ms per-write timeout. Native open/close can change modem-control lines; no firmware reset command is sent.
- Exactly 16 orientation bytes `00 00 00 00 00 79 64 01 40 01 E0 00 00 00 00 00`, then header `00 00 04 FD DF C5`, then 120 writes of 2560 bytes: **122 writes / 307222 bytes**.
- Embedded RGB565LE payload: 307200 bytes, SHA256 `8cbbb7e39485e211548a4f3f448ca14eeb9358286e5eadf7079a324fdc97ed1d`. Length/hash are checked before opening anything.
- No reads, HELLO, reset, clear, power, brightness, firmware changes, extra image, retry, timing experiment or buffer adjustment.
- Queue drain polls `SerialPort.BytesToWrite` (Windows COMSTAT output queue) with a 15-second deadline. Success appears only after queue-empty **and** close return. Framework disposal may itself flush and block; all inventory and serial operations therefore occur in one owned child of this EXE.
- The supervisor starts without a shell, inherits console handles, waits at most 90 seconds and kills only its own process on timeout. A private Windows kill-on-close job contains the owned child if the parent exits; no process-name scanning or unrelated process termination is used. Cleanup exceptions never replace a primary failure with success.

The frozen image was rendered with Linux Chromium, not native fonts. `pattern.json` records provenance. It is not proven byte-identical to the owner's earlier Windows browser canvas. Vendor rendering success is also not proof of this reference's correctness.

## Reproduce and inspect the build

On a fresh Windows checkout with inbox Framework and PowerShell 7, run:

```powershell
./tools/windows-usb-probe/build.ps1
```

No download or install step is used. The script first checks Framework64 `v4.0.30319/csc.exe` and framework assemblies, validates fixtures, compiles the application and a separate dependency-free fake-port harness, then runs that harness and the actual application's public commands with captured output/exit checks and deadlines. Test-only hang/exit modes exist only in `ProbeTests.exe`, never in the delivered program. Output-directory reuse is refused to prevent stale artifact qualification.

Only after tests pass does it create:

- `build/native-usb-probe/UsbScreenProbe-1.0.0-Windows-x64.zip` and `.zip.sha256`;
- inside: the EXE, this README, reference PNG/JSON, LICENSE, relevant `source.zip`, `SHA256SUMS`, and `nativeverification.json` (source commit/hashes, compiler fingerprints, OS/image versions, executable hash and test outcomes).

Workflow artifact: **UsbScreenProbe-Windows-x64**, seven-day retention. No vendor files or owner screenshots are included. Hashes identify content, not publisher authenticity: compare against the expected workflow commit and downloaded source. Native CI success, downloaded artifact verification, and the existing Python regression suite passed the parent-owned delivery gates for the pinned artifact. The later owner physical test is separate evidence limited to one portrait frame; neither this guide nor that test authorizes application integration.
