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

## Follow-up: reconnect without automatic resume

After the disconnect evidence has been reviewed and output is reported closed:

1. Reconnect the same screen to the same USB port. Do not change saved settings.
2. Wait 10 seconds without pressing controls. Confirm that the host counter stays
   at its disconnected value and capture does not return to running automatically.
   A boot image on the panel is not evidence of application capture.
3. If it stays idle, click **Start** exactly once. Observe whether the count advances
   and physical portrait updates return. Send the before/after count and a screenshot.
4. If capture resumes by itself, Start fails, or cleanup becomes uncertain, report
   that outcome without another restart or unplug. Do not change protocol or force
   process cleanup. This step does not yet qualify COM reassignment or duplicate units.

## Follow-up: Exit while capturing and cold relaunch

After explicit reconnect/Start has succeeded:

1. In Windows Task Manager's Details tab, note this application's `MarsDisplay.exe`
   processes/PIDs while capture is running. There may be multiple processes because
   the packaged application and its owned helper share an executable name. Do not
   end tasks or infer ownership of unrelated browser processes from their name.
2. Use the MarsDisplay notification-area icon menu and choose **Exit** while it is
   capturing. Closing the settings window with X is not the same operation.
3. Record elapsed time until the application icon/window and its previously noted
   processes disappear. If any remain after a 30-second observation, or an error is
   shown, report those names/PIDs and the exact message without killing them.
4. Only after confirmed exit, launch the same verified executable once. Confirm it
   starts stopped, preserves the saved output configuration and does not capture
   automatically. Leave it stopped and report the result.

A retained panel image after Exit is not evidence of continued USB writes. This
check observes application/helper lifetime; it does not establish exclusive
ownership or cleanup of every browser process on the machine.

## Follow-up: move the same screen to another USB port

With one screen and a spare USB port, record the screen's current COM number in
Windows Device Manager before moving it. Do not change driver settings or assign
COM numbers manually.

1. Click Stop and wait for acknowledged `stopped` and closed output.
2. Move only that screen to the spare USB port. Record its new COM number in
   Device Manager. Keep the application's saved identity and settings unchanged.
3. Confirm capture has not resumed automatically. Click Start once and observe
   host-count advancement and physical portrait updates. If it fails, report the
   message before retrying. If it succeeds, Stop again and report both COM values,
   count and physical result.

A successful move with the same COM number proves only physical-port relocation,
not COM reassignment. A second identical screen is currently unavailable, so
physical duplicate-identity rejection is unverified; software coverage does not
replace that missing physical scenario.
