# P0–P2 native Python USB bridge
Implement only a baseline, pure portrait encoder and standalone packaged one-image Python/pyserial diagnostic; branch `feat/native-python-usb-probe`, verified-main baseline `44b0f737e78011fc2f1014baaab9fa59f78fdfae`.
Delivery: `auto-chain`, `chain_strategy=feature-branch-chain` (owner's project native-diagnostic review preference), no PR/main integration; forecast ~1500 authored lines plus selected documentation, generated fixtures excluded. Checks: focused unittest, native Windows CI, artifact qualification and owner physical gate. Reuse Python 3.13 / pyserial 3.5 / PyInstaller 6.22.3.

## Specs

### S1 — Authorized stages and baseline
> ok, vamos con P0 - P2

Accepted plan snapshot: `0b92565c10996276af5b9ad61a7c85bfc26df327:docs/usb-integration-plan.md`, P0–P2 only. Begin from freshly verified main; preserve the diagnostic branch and carry explicitly selected canonical fixtures/documentation, never merge the whole prior feature. Leave application composition, UI, settings, browser, lifecycle, dependencies, installer/service/autostart and P3–P6 unchanged. Source/work-unit commits and known-origin Windows CI follow session delivery permission; no PR/release/tag/main merge.

### S2 — P1 pure portrait protocol
> Encode RGB888 to RGB565LE and the exact portrait orientation/header/chunks in the guide.
> Reject unsupported geometry/profile, wrong frame, unknown or duplicate identity before port open or any write; no inference from VID/PID alone.

These are accepted-plan quotations. Add `src/mars_display/usb_protocol.py`; reuse `RGBFrame` and existing frame validation, without narrowing shared RGB888/landscape semantics. Encode only the proven 320x480 portrait profile, truncating RGB565 little-endian. The public immutable packet sequence is exactly orientation `00 00 00 00 00 79 64 01 40 01 E0 00 00 00 00 00`, header `00 00 04 FD DF C5`, then 120 chunks of 2560 bytes: 122 writes, 307222 bytes total. New pure encoding has no enumeration, port, file, GUI or settings effects. Identity validation belongs in the P2 runner and reuses `enumerate_devices`/`select_device` unchanged.

### S3 — Canonical image and source evidence
> ahora si!!!

This owner statement qualifies one physical C# portrait test, not Python. Carry `pattern.png`, `pattern.rgb565`, `pattern.json` and their fixture test explicitly from `0b92565`; preserve exact bytes. RGB565 payload SHA256 `8cbbb7e39485e211548a4f3f448ca14eeb9358286e5eadf7079a324fdc97ed1d`; PNG SHA256 `d8efdd4339e8c16a8f2b7e1416ec83221403cf6bdc6571ee5ff146113f00cfbc`. Derive one immutable raw RGB888 fixture from that PNG using the existing development Pillow, record its hash/provenance, and verify P1 maps every pixel to the known payload. Do not ship Pillow/Qt/browser or regenerate/redraw the image at runtime. Prior Windows browser versus Linux canvas byte identity is unproven.

### S4 — P2 explicit one-image native runner
> Use the canonical frozen image, not a fresh browser render.
> No continuous mode, GUI integration or arbitrary input/commands at this gate.

Provide a separate console diagnostic with USB-free help/self-test, passive listing, explicit current COM selection, exact known profile VID 1A86/PID 5722/serial USB35INCHIPSV2, typed `SEND COMn` confirmation and fresh unique identity recheck immediately before open. COM5 is only an example. Reuse existing device validators/selection, reject ambiguity and foreign old-COM occupants; no first-device fallback. No configuration writes. Every rejection before I/O leaves opens/writes/settings/frame counters unchanged.

Native settings match the proven reference: 115200 baud, 8N1, RTS/CTS, DTR enabled, finite three-second write timeout; short/failed writes fail, never retry. Bounded queue drain (not unbounded `flush`) and close must finish before success; host completion is not a rendering ACK. Bound inventory/open/write/drain/close with one owned one-shot child/startup gate/Windows kill-on-close job and finite supervisor wait; qualify source-mode and frozen self-launch vectors, never assume frozen `sys.executable -m` is Python. EOF/cancel/invalid arguments do not open a device. Kill only the created child, report uncertain termination/partial delivery, never auto-resend. No HELLO/read/reset/clear/power/brightness/firmware/timing/protocol experiments. This is not P3 persistent IPC or application integration.

### S5 — Native packaging and legal qualification
> Qualify native Windows pyserial options, write/drain/close behavior and the packaged child launch path with explicit device selection.

Prepare a lean PyInstaller console onedir ZIP with only this diagnostic, required CPython/pyserial runtime, canonical reference, relevant source, license material, hashes and native evidence. Reuse generic safe-read, installed-license, SDK-license, native evidence and external-Microsoft-runtime primitives unchanged; do not reuse/fake the app-specific Qt v2 publisher or its mandatory browser inventory. Every delivered native file needs actual build/SDK provenance and terms, including CPython's generated Windows LICENSE, pyserial terms, PyInstaller bootloader exception and CPython-bundled components. Unknown origins/missing terms block publication. Exclude Microsoft DLLs during Analysis closure and reject them in the final payload; no post-build SDK deletion or copied system DLLs. Document the same external official VC++ prerequisite as the current app, never install it automatically. No vendor files, owner screenshots/frames/private URLs or full-workspace archives.

Native Windows CI executes the extracted EXE under isolated environment/PATH, verifies safe commands and frozen child lifetime without USB, exact fake-port protocol/options/deadlines, source stability/closure/legal coverage, and only then uploads a source-bound short-retention artifact. Build/source/hash readback is required before owner delivery. Existing app source/behavior remains unchanged. RDD remains user-owned (currently off); risk items 4/5 require one independent verification after source/native proof, not a per-checkbox review cycle.

### S6 — Required physical acceptance and stopping boundary
> Accept: exact transfer evidence, bounded completion and owner photo matching the reference from the actual native packaged path. Linux fake-port tests or successful C# output are insufficient.

This accepted-plan gate remains open until the owner runs the new packaged Python EXE and supplies its console result and correct physical reference image. Tests/native CI alone cannot close P2. If unavailable/failed, report that missing proof, do not enable application output or switch protocol. Keep Simulation as rollback and preserve the working C# artifact; P3–P6 need later authorization. No actual device access from the agent host is authorized or needed.

## Tasks

- T0 [S1,S3] route: parent baseline/selected carryover; status: done; commit: P0 snapshot commit recorded in next log transition — Verify main, preserve old branch, carry only canonical data/docs/test, derive/hash RGB888 and record provenance. Risk: none (fixtures/docs only).
- T1 [S2,S3] route: delegated writer (context backstop); status: in_progress; commit: pending — Pure portrait encoder and public RED/GREEN tests, shared frame/transport preservation. Risk: none (additive pure module).
- T2 [S4] route: delegated dependent writer (context backstop); status: pending; commit: pending — One-shot native runner, exact selection/confirmation, finite transport and owned child, tests/docs. Risk: item 4 (process lifecycle).
- T3 [S5] route: delegated dependent build writer plus parent native CI; status: pending; commit: pending — Lean audited payload/spec/builder/workflow and package tests; no shared helper changes. Risk: item 5 (native build/CI delivery).
- T4 [S1–S5] route: parent + one independent verifier; status: pending; commit: pending — Focused/full regressions, independent check, native build and exact artifact/source/license/hash verification; deliver owner instructions.
- T5 [S6] route: owner physical test; status: pending; commit: evidence pending — Correct reference photo plus new Python executable console result. This external gate must remain blocked, not done, until observed.

## Log

L1 — Owner original request, verbatim: `ok, vamos con P0 - P2`.
L2 — Before writes, clean diagnostic branch at0b92565 preserved. Fresh GitHub preflight job13 exit0: origin ghosthvj/MarsDisplay/defaultmain/viewerADMIN, fetched main44b0f737e78011fc2f1014baaab9fa59f78fdfae. Created new feat/native-python-usb-probe at that exact main; local main/old branch unchanged, no merge/cherry-pick of the full diagnostic feature.
L3 — Read-only map mvh6dval-e-mjxf: RGBFrame imports remain GUI-free; devices already provides exact unique selection. Generic notices/payload/native evidence/external-runtime helpers are reusable unchanged; existing publisher and Qt native-material v2 gate mandate the full app and must not qualify a fake lean profile. pyserial fallback material includes the entire verified legal registry; preserve it honestly. Frozen self-launch differs from source Python, native proof required. No code or USB was run by the explorer.
L4 — P0 explicitly carried only the two current guides, three canonical data files and fixture test from0b92565; no C# source/runtime, owner photos or vendor files copied. Guide references to old C# source/README/ledger now use immutable GitHub source links, avoiding broken local links without importing its whole feature. The plan records P0–P2 authorization and keeps P3–P6 proposed. Parent linkcheck PASS16localtargets, diffcheck0; main and previous branch unchanged.
L5 — P0 raw-RGB888 fixture rule RED:2tests/0.056s exit1 (known PNG/RGB565 test passes, new raw fixture absent). Derived once from PNG via existing Pillow12.3.0, no browser render. New460800-byte RGB888 SHA25619edb4162586afb859c062b82a4c26b54d7329dc3303205628ad61ab1558ef40; rgb888-provenance.json records source0b92565/PNGhash/derivation. GREEN2/0.059s exit0; canonical PNG/RGB565 bytes unchanged, no port enumeration/open or app changes. T0 complete; T1 pure encoder starts next.
