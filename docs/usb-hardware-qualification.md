# P6: first owner-run Windows observation

**Not yet hardware-qualified.** Use only the P5 application artifact below.
The owner executes these steps; the agent reviews the evidence. Do not run the
standalone C# or Python probe simultaneously. Keep firmware, brightness and power
commands unchanged. Native landscape is unsupported and is not part of this test.

## Pin the package

- Source: `56ea091cfae996101e5106cf1acc64898bd52b59`.
- [Windows artifact 12367770679](https://github.com/ghosthvj/MarsDisplay/actions/runs/39645553766/artifacts/12367770679).
- Inner ZIP: `MarsDisplay-0.1.4-Windows-x64.zip`, 205,687,478 bytes.
- Inner ZIP SHA256: `24d8ce2fff5d9455a08c8fac2251346f0fc9a010653abe13caa0106df910171d`.

GitHub may require sign-in. The recorded artifact expires on 2026-10-28 at
17:42:01 UTC; a verified local copy remains usable afterward. If unavailable,
stop rather than substitute another same-version package. The Actions download
wrapper has a different hash: check the inner ZIP in PowerShell before extracting:

```powershell
Get-FileHash .\MarsDisplay-0.1.4-Windows-x64.zip -Algorithm SHA256
```

Extract the entire inner ZIP to a new folder, keeping `_internal`, notices and
source beside the application. Preserve existing settings and the schema-1 backup;
do not delete them to force first-run behavior. Close the vendor app, standalone
probes and previous MarsDisplay instance normally. Do not bypass security warnings
or terminate unrelated processes. A blocked close is evidence to report, not a
reason to force cleanup.

## First observation: portrait, then Stop

1. Launch `MarsDisplay.exe` from the verified extracted folder. It must start
   stopped. If a warning, crash or unexpected active capture occurs, stop and report.
2. Check the existing MARS source privately. It must provide 320×480 portrait.
   Do not share private URLs/tokens. Unsupported source geometry is not permission
   to rotate, crop or change protocol.
3. While stopped, choose **Native USB**, click **Refresh USB identities**, and
   explicitly choose `usb:1a86:5722:USB35INCHIPSV2`. Never use COM5 as a default.
   If unavailable or ambiguous, do not proceed.
4. Click **Save**. If migration is requested, read the older-binary incompatibility
   and preserved-backup warning; confirm only if acceptable. Save must remain stopped.
5. Record the initial lifetime host-accepted count. Click **Start** once. Observe
   for 60 seconds: source state, output state, changing host count, preview and
   physical portrait. Note elapsed time and whether physical content changes as
   the source changes. This short observation is not a sustained-load acceptance
   threshold, panel FPS measurement or rendering acknowledgement.
6. Click **Stop** once. Record how long acknowledgement takes and its exact status.
   After it is acknowledged, observe another 10 seconds: the host count must not
   advance. The panel retaining its last image does not itself mean writes continue.
   If Stop remains pending or reports uncertainty, capture the exact text and do
   not force-close, reconnect or retry yet.

## Return evidence before the next physical scenario

Send the package hash confirmation, initial/final host count, elapsed time, source
and output status, Stop acknowledgement/time and count after the additional wait.
Provide a photo or short video of the physical screen alongside the preview if
possible. Hide private URLs, credentials and unrelated desktop information.
Report artifacts, freezing, incorrect orientation/colors and every error verbatim.
If anything fails, stop at that point; do not automatically resend or unplug/replug.

Next scenarios are planned separately: controlled unplug/replug and explicit
restart, COM reassignment/duplicate rejection when available, in-flight Stop,
Exit and owned-resource lifetime, and measured latency/capacity. No production
budgets or landscape implementation are authorized by a successful first run.
See [the P6 task ledger](../odd/tasks/native-usb-hardware.md) for acceptance boundaries.

## Follow-up: one controlled disconnect

Proceed only after the initial portrait/Stop evidence and package checksum have
been reviewed. Keep the same package and saved settings; do not change protocol.

1. From acknowledged stopped, click **Start** once. Confirm the host count advances
   and physical updates resume. If Start fails, report that instead of unplugging.
2. Note the host count, unplug only this screen's USB cable once, and start a timer.
3. Without reconnecting or clicking Start/Stop/Exit, observe for at most 30 seconds.
   Record elapsed time to the first state/error change, the exact diagnostic,
   output/source state and final host count. Take a screenshot, hiding private URLs.
4. Stop the test at that observation and report before reconnecting. If cleanup
   remains pending or uncertain, do not kill processes or force another session.

A frame already in flight may affect the count before failure; do not infer a
panel acknowledgement from it. No automatic native restart is expected. A continued
running state after 30 seconds is evidence to investigate, not permission to widen
safety deadlines. Reconnect, COM reassignment, duplicates and Exit are separate
steps after this observation is reviewed.
