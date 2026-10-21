MarsDisplayGroupingExperiment — RAW EXPERIMENT, NOT NORMAL MARSDISPLAY

Windows x64 only. External prerequisite: official Microsoft VC++ v14 x64
14.51 or newer. Microsoft DLLs are not bundled. Do not replace a normal install.
Extract the whole ZIP into a new directory; retain _internal, source and notices.
Verify the ZIP with PowerShell Get-FileHash -Algorithm SHA256 and the supplied
.zip.sha256. inventory.json binds every payload file (except itself) and exact
source_files to SHA256; source_commit identifies the baseline commit plus the
included exact source snapshot. Read source/docs/usb-grouping-experiment.md.

From PowerShell in the extracted folder:
  .\MarsDisplayGroupingExperiment.exe --help
  .\MarsDisplayGroupingExperiment.exe --self-test
These do not access devices. Only the owner, after closing MarsDisplay and ALL
vendor/probe programs, may explicitly start:
  .\MarsDisplayGroupingExperiment.exe --run

This changes transport write grouping and can produce an incorrect image.
Type the displayed A COM port confirmation; A sends one fixed public pattern.
Wait for host success and known cleanup. Inspect the actual display. Only type
A VALID if correct. B needs another fresh COM confirmation and sends one frame.
Any error, incorrect image, default/EOF or uncertainty prevents automatic B.
There is no repeat, resend or reconnect. Both arms open/send/close separately;
opening/closing may toggle DTR. Never force-close a cleanup-uncertain console
or restart MarsDisplay while it retains the shared application lock.

Report numeric host timings AND physical image correctness for A and B. Times
overlap and do not prove panel acknowledgement, FPS or a performance improvement.
No private images, settings, URLs or video. No agent hardware test is claimed.
The native build checks HELLO/CLOSE, malformed IPC, admission and owned reaping;
it never sends OPEN and never executes --run against real inventory in CI.

Build: native Windows x64 Python 3.13.16, existing pinned .[build] SDK,
  python -B packaging/build_grouping_experiment.py
Dedicated workflow: windows-usb-grouping.yml (manual dispatch only).
All source tests must pass with zero skips; frozen no-device checks and exact
native/source/license binding must pass before artifact upload. Failure is
UNQUALIFIED; no binary artifact is uploaded. Outputs use the separate
MarsDisplayGroupingExperiment name and exclusive creation. Existing outputs,
normal executable/build/workflow behavior and user settings are not overwritten.
See notices/native/SOURCE-ACCESS.txt for complete pinned upstream source access,
raw notices and redistribution obligations. Keep source and notices with binaries.
