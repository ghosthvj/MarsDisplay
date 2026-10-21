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

## T3: first five-minute stability sample

The owner accepted continuing with one screen on COM5. Physical COM reassignment
and duplicate-screen rejection remain unverified. No Windows driver changes are
needed to manufacture those scenarios.

1. Use the same verified package, source and saved settings. If stopped, Start once;
   if already running correctly, do not restart just to reset the lifetime counter.
2. While running, record host count C0 and start a stopwatch. Capture the status.
3. Leave capture running for five minutes without changing settings, unplugging,
   restarting or resetting the counter. Observe physical redraw, freezes, corrupted
   content and errors. If an error appears, end the observation and report it without
   retrying; do not silently exclude the failed interval.
4. Before Stop, record count C1, actual elapsed seconds and status screenshot.
5. Then Stop. Record acknowledgement time and the count after another ten seconds;
   report any delivery-uncertainty warning separately from the running interval.

Report C0, C1, elapsed seconds, running errors/freezes and whether visible refresh
remained roughly consistent. `(C1 - C0) / elapsed_seconds` measures average host
acceptance during this observation, not physical panel FPS, maximum throughput or
USB write/drain latency. Five minutes is an initial observation, not proof of an
unbounded stable run. A successful sample alone cannot establish production
operation deadlines; the existing safety caps remain unchanged and provisional.

## Recorded first timed sample — limited result

Owner screenshots show these stopwatch readings and lifetime host counts:

| Elapsed seconds | Host-accepted count | State |
|---:|---:|---|
| 3.01 | 1 | running |
| 61.86 | 24 | running |
| 141.24 | 56 | running |
| 203.19 | 81 | running |
| 267.06 | 107 | running |
| 322.79 | 130 | running |
| 332.11 (stopwatch paused) | 134 | stopped / native-closed |

The running interval contains 129 accepted frames in 319.78 seconds: approximately
0.403 host-accepted frames/second, or a 2.48-second mean completion interval.
Sample-to-sample rates range from 0.391 to 0.413 frames/second. The owner reported
no visible freezes or running errors and more obvious redraw in the chart region.
This does not identify a USB bottleneck, measure panel FPS or set production budgets.
The exact Stop press was not timed; the final four frames cannot be classified as
post-Stop writes from these captures. Earlier stopped-count stability was separately
reported in T1.

The initial browser decoding attempt yielded empty frames and was rejected.
After owner-authorized installation of an isolated local FFmpeg decoder, 22
nonempty overview samples and 20 samples approximately 0.1 seconds apart around
9–11 seconds were visually inspected. Upper-card changes precede replacement of
the lower graph; intermediate samples show old and new graph traces together.
This confirms progressive redraw in that recorded transition, not its cause or
per-operation USB latency. Source animation, transmission, panel behavior and
camera effects have not been separated. No private video or image was uploaded
or included in the repository.

Stage-level numeric timing is still needed to distinguish source capture, host
send and pacing costs before choosing production deadlines or optimizations.
The synchronous loop waits only the remainder of its one-second cadence target;
it does not promise one completed frame per second. Existing safety caps remain
unchanged. T3 is not fully accepted from this visual and aggregate-rate evidence.

## Verified numeric diagnostic package

A separately verified diagnostic includes a bounded RAM-only **Native timing**
summary in Status / Settings. It is not present in the original P5 ZIP above.
Both packages use the same version filename: distinguish them by hash and source,
not by filename. The original P5 ZIP remains immutable. Diagnostic software
qualification does not establish physical stage timings or production budgets.

- Source: `d79eb805a943ddc4f0ee08a108a885e3edc23833`.
- [Diagnostic artifact 12372114144](https://github.com/ghosthvj/MarsDisplay/actions/runs/39657968799/artifacts/12372114144).
- Inner ZIP: `MarsDisplay-0.1.4-Windows-x64.zip`, 205,696,203 bytes.
- SHA256: `0b1cb758184e719fb743ac336a77b27f0c8b52df1697e238e2fa6dd48f18d321`.
- Recorded artifact expiry: 2026-10-28 19:05:33 UTC; keep the verified local copy.

Windows passed 259 tests / 65.332s with zero skips, then actual windowed build,
owned-worker smoke and source/native/material gates. Parent and independent
readback verified 1,251 payload hashes, 355 sources (351 exact Git Windows checkout
plus four SDK records), 69 AMD64 PE32+ binaries, 27 Qt and six supplemental
components, and 209 material hashes. Independent focused 69 plus two boundary
probes passed; parent final spot passed 69. The 12-case preservation differential
was exact, but does not replace tests for new timing fields. Earlier pending
wording inside the immutable diagnostic ZIP is superseded by this record.

The summary reports count, last, minimum, maximum and mean milliseconds separately
for source observations, successful host sends and non-cancelled cadence waits.
Host send includes encoding, IPC and helper work; it does **not** isolate serial
write/drain or panel rendering. Source observations without frames still count.
Failed calls and cancelled waits do not count. Stop/error retain the current report;
a new admitted native Start resets it. Simulation has no native report.

For the authorized observation, report only these numeric summaries alongside
host count and exact failure/Stop status; avoid sharing private URLs or full settings.
No diagnostic export, image capture, logging or timing history is added. Successful
sample statistics alone cannot set failure deadlines or prove panel FPS. Existing
cadence, safety caps, native zero retries and cleanup/rollback rules remain unchanged.
See [the runtime timing contract](usb-runtime.md#native-numeric-timing-diagnostic-candidate).

### Measure with the diagnostic

1. Exit the old app normally and confirm its processes close. Keep its extracted
   folder and saved settings/backup; do not delete settings or overwrite old files.
2. Download the diagnostic artifact above. Verify the **inner ZIP** using
   `Get-FileHash .\MarsDisplay-0.1.4-Windows-x64.zip -Algorithm SHA256` against the
   diagnostic hash, not the earlier P5 hash. Extract the whole inner ZIP into a new
   folder and launch that `MarsDisplay.exe`. Stop on security warnings or mismatch.
3. Confirm it starts stopped and retains the intended native configuration. Start
   once; scroll to **Native timing** if necessary. This Start resets the aggregates,
   not the lifetime frame counter. Do not change settings or restart during sampling.
4. After approximately one minute, capture all three timing rows and host count.
   At five minutes, capture them again with elapsed time. Hide private URLs.
5. Stop and capture the retained timing report/status after acknowledgement. Report
   any errors, visible freezes and whether the sweep changed; do not retry an error.

The needed rows are **Source read (observations)**, **Host send (encoding / IPC /
helper total)** and **Cadence wait (non-cancelled)**, each with count/last/min/max/mean.
No command-line diagnostic mode, file export or per-frame disk log is required.

## Recorded diagnostic stage sample

The owner verified the diagnostic ZIP SHA256 and supplied running samples through
323.03 seconds, followed by stopped/native-closed at a paused 335.06 seconds.
Host counts rose from 6 at 16.71 seconds to 129 at 323.03 seconds: approximately
0.402 host-accepted frames/second. The retained report after Stop contained 134
successful sends and the following values (milliseconds):

| Stage | Count | Last | Minimum | Maximum | Mean |
|---|---:|---:|---:|---:|---:|
| Source read | 137 | 25.561 | 19.252 | 121.148 | 25.068 |
| Host send | 134 | 2440.637 | 2308.649 | 2464.827 | 2441.610 |
| Non-cancelled cadence wait | 136 | 0.009 | 0.007 | 977.580 | 14.340 |

Independent sample counts are expected. The wait maximum includes a source
observation without a send; it is not an additional one-second delay on every
completed frame. Count-weighted successful stage durations total approximately
332.560 seconds: 327.176 seconds in host send, 3.434 in source read and 1.950 in
cadence waits. Host send accounts for about 98.38% of this measured stage time,
not 98.38% of the entire application lifetime.

The measured bottleneck lies in the host-send path, not the capture call or
steady-state cadence wait. Encoding, IPC, helper writes, queue drain and device
behavior are not separated by this report. Do not infer an isolated serial or
panel duration, choose a timeout from the successful maximum, or tune protocol
parameters from this sample. Finer stage measurements or an explicit decision to
defer production-budget qualification are still required; P6 is not fully closed.

## Verified internal-send diagnostic package

This separately qualified package adds seven rows to the existing three-row report.
Neither earlier ZIP contains them; preserve both and extract this one into a new folder.

- Source: `b947675e6332f44e276a35840ef808310ffaaae5` (core `5668150`, UI `b947675`).
- [Internal diagnostic artifact 12375057696](https://github.com/ghosthvj/MarsDisplay/actions/runs/39663099449/artifacts/12375057696).
- Inner ZIP: `MarsDisplay-0.1.4-Windows-x64.zip`, 205,707,048 bytes.
- SHA256: `f828e5f059777c8fff1b88b39067fd21ae39e7294d19ad553a086879d4b6a0ad`.

Windows passed 267 tests / 68.546s with zero skips. Parent and independent artifact
checks passed: 1,253 payload hashes, 357 source records (353 exact Git Windows
checkout files plus four SDK records), 69 AMD64 PE32+ binaries, 27 Qt and six
supplemental components, 209 material hashes and the packaged helper smoke.
Independent verification passed 52 focused tests plus two boundary probes; legacy
behavior differential checks passed. Native RDD was declined by the owner for this
candidate, not approved or globally disabled. Earlier pending-delivery wording
inside this immutable ZIP is superseded by this record.

Follow the measurement procedure above using this artifact and hash: normal Exit,
verify the inner ZIP, extract into a new folder, confirm stopped startup, then one
explicit Start without changing settings. Capture the complete report near one
minute and five minutes with elapsed time and host count, then again after Stop
acknowledgement. On an error, stop and report it without retrying. Keep previous
folders, configuration and backups intact.

For this observation, the owner needs all ten rows, each with independent
count/last/min/max/mean milliseconds. In addition to source read, host send and
cadence wait, scroll to **Helper frame decode**, **Helper identity resolution**,
**Helper RGB565 encode**, **Helper packet writes**, **Helper queue drain**,
**Host IPC body encode**, and **Host exchange (includes helper work)**.
Report unavailable rows as unavailable, not as measured zeros. Keep private URLs
out of shared evidence; no export or per-frame log is needed. Save remains in the
fixed footer while the numeric report scrolls.

Host exchange includes helper work: never add exchange and helper durations as
separate costs. Host-send total still is not panel rendering latency. Stop/error
retain the successful report; an admitted native Start resets it. Failures are
excluded, so even these finer successful measurements cannot alone establish
failure deadlines or justify protocol, serial, retry or cadence changes.

## Verified grouped-write diagnostic package

- Source: `7a7fe1d8d86afcf549f77c263c83991703e34a01`.
- [Grouped diagnostic artifact 12379222327](https://github.com/ghosthvj/MarsDisplay/actions/runs/39670365388/artifacts/12379222327).
- Inner ZIP: `MarsDisplay-0.1.4-Windows-x64.zip`, 205,712,143 bytes.
- SHA256: `67438b701952e588a3417c8101b1c79ced9fde021a9cb2baa22c9d73fa9efe34`.

Windows passed 270 tests / 69.567s with zero skips. Independent focused verification
passed 55 tests plus one numeric/framing boundary probe. Its initial isolated run
failed before tests because the verifier omitted a public fixture; after repairing
that copy, the authorized corrected run passed without candidate source changes.
Parent and independent ZIP checks verified all 1,254 payload files, 354 exact Git
Windows-checkout source files plus four SDK records, 69 AMD64 PE32+ binaries,
native material/license references and the recorded packaged helper smoke.
The owner explicitly declined native RDD for this candidate; no approval or global
switch change is claimed. Pending wording inside the immutable ZIP is superseded here.

This package preserves all ten rows and adds **Helper orientation write**,
**Helper bitmap-header write** and **Helper pixel writes** with count/last/min/max/mean
milliseconds. They are subsets of total packet writes, not extra costs. Existing
packages above remain immutable and do not contain these rows.

Exit the prior app normally, preserve settings/backups and old extracted folders,
verify this inner ZIP hash, and extract the complete package into a new folder.
Confirm stopped startup before one explicit Start. Use the same bounded procedure:
capture all thirteen rows and host count near one/five minutes and after Stop.
Stop on an error and report it without retrying. Do not disable Windows protections;
a publisher/reputation warning is separate from checksum verification.
Report unavailable detail as unavailable, never zero. No private URLs, packet
histories or exports are needed. These successful-only measurements do not authorize
orientation omission, chunk/baud/CTS changes, retries or deadline tuning.
