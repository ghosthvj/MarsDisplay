# Qualified USB grouping experiment delivery

This is a separate owner-run experiment, not a normal MarsDisplay update.
The owner authorized delivery without RDD (`entrega sin RDD`) for this candidate
only. No native review approval or physical performance approval is claimed.

## Immutable package

- Source: `c2c27f68d3d1a2b297708134c7b921ec83738bb3`.
- Windows run: `39682684866`, attempt **2**.
- [Download artifact 12384388565](https://github.com/ghosthvj/MarsDisplay/actions/runs/39682684866/artifacts/12384388565).
- Inner ZIP: `MarsDisplayGroupingExperiment-0.1.4-Windows-x64.zip`.
- Inner ZIP size: **33,545,828 bytes**.
- SHA256: `8ded8b6e857d7705ebba52110d2cc80f8c86a12d43754d5476cf9ac2198ada57`.

The hash applies to the inner delivery ZIP, not GitHub's outer artifact archive.
Extract into a new directory; retain all files and do not replace normal MarsDisplay.
Requires Windows x64 and official Microsoft VC++ v14 x64 14.51 or newer.

## Owner procedure

1. Verify the inner ZIP SHA256 using `Get-FileHash -Algorithm SHA256`.
2. Extract the complete ZIP. From PowerShell inside its executable directory run
   `.\MarsDisplayGroupingExperiment.exe --self-test`. This does not access USB.
3. Close normal MarsDisplay and all vendor/probe software. Then run
   `.\MarsDisplayGroupingExperiment.exe --run`.
4. Confirm A using the exact currently displayed COM prompt (for example `A COM5`).
   Wait for successful host completion and known cleanup; inspect the physical image.
5. Type `A VALID` only if A is correct. Confirm B's freshly displayed COM prompt
   (for example `B COM5`). Each arm sends just one frame; do not automatically retry.
6. Report console numeric results and physical image correctness separately for A/B.
   If an error or uncertain cleanup appears, stop the procedure. Do not force-close
   a cleanup-uncertain console or restart MarsDisplay while it retains ownership.

A uses 120 pixel writes of 2560 bytes, B uses 60 of 5120 bytes. Orientation/header
and concatenated bytes are identical. Both arms independently open/send/close,
which can toggle DTR. Host timings are not panel acknowledgement or FPS.
See [full procedure](usb-grouping-experiment.md) for cancellation and exit codes.

## Evidence and limitations

Windows: **309 tests passed, zero skips**, followed by successful frozen no-device
qualification. Parent and independent readback matched all 822 payload hashes,
823 ZIP members, 377 source records (373 Git Windows-checkout plus four generated
SDK records), 46 x64 PE files, 33 native components and 209 material hashes.
No OPEN/device request was sent during CI verification.

The independent focused run initially had one missing public fixture (68 passes,
one error); after copying that fixture, only the failed test was rerun and passed.
An artifact-probe schema error was corrected for unfinished OpenSSL checks only.
Independent PE resource parsing was unavailable; direct PE headers and reviewed
native byte hashes were checked. Earlier missing-SSL qualification failures and
attempt 1's CDN certificate rejection remain recorded, not erased by this success.
The successful retry retained TLS verification and all qualification gates.

Known documentation erratum in the immutable package: “manual dispatch only” is
outdated. Its workflow also has the authorized branch/path-restricted push trigger;
this does not affect owner commands. The artifact is not modified to change prose.

Physical A/B image validity, timing comparison and production-budget decisions
remain pending owner evidence. Normal packages, settings and backups are unchanged.
