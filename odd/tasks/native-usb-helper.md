# P3 persistent bounded USB helper
Implement only P3 on `feat/native-usb-helper`, fresh verified-main baseline `44b0f737e78011fc2f1014baaab9fa59f78fdfae`; preserve accepted P0–P2 branch `6bff97befee7b1e72f7afbcef3ab482a89011ea2` and qualified Python ZIP source `a26350dd74d1d03d999bbead5195dfc20d4a5344`.
Delivery: `auto-chain`, cached `chain_strategy=feature-branch-chain`, no PR/release/main integration. Forecast ~2200–2800 authored changed lines with tests/docs plus explicitly selected prerequisite carryover; coherent ~400-line slices, never code-golf. Checks: behavioral RED/GREEN, legacy differential, full regression, real Windows packaged proof and one independent risk verifier.

## Specs

### S1 — Authorization and boundaries
> adelante con P3

Accepted plan: `6bff97befee7b1e72f7afbcef3ab482a89011ea2:docs/usb-integration-plan.md`, P3 only; P0–P2 physical Python acceptance is already observed. Create the new branch from fresh verified main, explicitly carry only P1 encoder/tests, canonical test assets/provenance and relevant guides. Do not merge the whole prior feature or change its accepted source/binaries. Add no app composition, settings/schema migration, GUI/tray/preview/lifecycle, browser, dependencies, installer/service/autostart or P4–P6 behavior. Simulation stays the default. No actual USB from the agent host, vendor execution, firmware/reset/clear/brightness/power commands, protocol fallback, global installs, PR/release/tag or main merge. Use in-project ignored, test-owned state; the removed P0–P2 temporary-directory grant is not a P3 grant.

### S2 — Persistent transport and selection
> Expose the synchronous transport contract through one persistent owned native
> child, one in-flight frame, bounded IPC lengths/types/profile and explicit replies.

Add `UsbTransport` with explicit known opaque identity and synchronous `open()`, `send(RGBFrame)`, `close()` returning `None`; do not change existing `Transport`, Simulation, exports or zero-argument application factory. Import/constructor do no inventory, spawn or port I/O. One child and serial session persist across accepted sends; no per-frame spawn, queue, automatic retry/reopen or backend fallback. Concurrent send attempts reject instead of queueing. Reuse the unchanged portrait encoder and shared RGBFrame validation without narrowing simulated landscape. Invalid frames fail before new IPC/serial effects and leave accepted state unchanged. Only proven 320x480 portrait is supported natively. Reuse `enumerate_devices`/`select_device`, require exact profile `usb:1a86:5722:USB35INCHIPSV2`, unique selected identity and no foreign case-insensitive COM occupant, with fresh checks immediately before open and each frame's writes. Never treat COM5 or an old port as identity. Explicit Python injection for test-owned inventory/port/process fixtures is permitted; production accepts no executable/module/endpoint configuration.

### S3 — Bounded private IPC, no arbitrary capability
> No arbitrary commands, image/URL logging, disk frame history or per-frame process.

Use one private fixed-loopback `127.0.0.1` listener with OS-assigned port, Windows exclusive bind, random per-session nonce and one authenticated child connection. No public/network endpoint option, pickle, arbitrary command, module or file-path RPC. Startup admission must precede socket/device I/O. Both directions use bounded binary framing and absolute monotonic deadlines, not blocking ordinary-pipe writes or abandoned reader threads. Define v1 magic/version/type/request-id/length and finite body limits before allocation; permit only authenticated ready/open/frame/close and fixed sanitized replies. Frame bodies contain validated metadata and one RGB888 frame (460800 bytes), never URLs or filesystem paths. Reject malformed/oversized/truncated/wrong-order/stale-request/unsupported-profile input before port effects. Replies acknowledge host operations only, never panel rendering. Preserve the proven 115200/8N1, RTS/CTS, DTR and exact P1 packet sequence; short/failed writes are terminal and never resent.

### S4 — Deadlines, cancellation and uncertain ownership
> Specify start/write/drain/close/kill/reap deadlines and cancellation semantics before
> wiring. Measure latency/capacity to set a production budget; diagnostic 90 seconds
> is not that budget.

> Unknown cleanup fails closed, never reports success or releases ownership.

Engineering safety caps for this stage, explicitly provisional rather than measured production capacity: startup/admission 5s, entire frame operation 20s, each serial write 3s, queue drain 15s (within frame cap), graceful close 5s, owned kill/reap 2s. Bound IPC bootstrap/read/write against absolute budgets and observe cancellation during waits; no deadline refresh per chunk. Parent owns a Windows kill-on-close job and startup event; never release admission before assignment. Preserve accepted P2 code rather than modifying its context manager, which does not retain failed CloseHandle ownership. Cancel/timeout during possible writes marks delivery uncertain and closes/reaps only the created child. Successful send requires explicit matching host-completion reply after all writes/drain. Close may force termination but must confirm reap before claiming resource closure. Failed handle-close/reap retains ownership and prevents reopen/success; safe repeated cleanup may confirm it later, never resending a frame. No PID scanning or killing unrelated processes.

Python documents that OS process creation cannot necessarily be interrupted. A bounded owned launcher must retain a late/uncertain creation attempt, keep admission closed, and dispose of a late child before any I/O; do not equate a timed-out wait or dropped reference with no child. Test controlled late-spawn/cleanup failure without leaving an unbounded test thread/process. This stage does not promise measured hardware timing or the future P5 Stop/Exit UI contract.

### S5 — Early frozen route and reproducible packaging
> Qualify child entrypoint routing before Qt/app launch, sanitized
> reporting and `freeze_support` if using multiprocessing. Do not assume
> `sys.executable -m ...` works in PyInstaller. Native packaged tests must prove it.

Source launch targets the worker module directly; frozen launch uses the same executable and reserved private worker route, dispatched before app/Qt/settings/dialog imports or I/O. Invalid/private admission fails closed without falling through to GUI or leaking tokens/raw exceptions. Ordinary no-worker windowed startup, None-stream handling, sanitized reports and existing command outcomes remain unchanged. No multiprocessing is required; do not add an unused freeze_support mechanism.

Prefer the existing full-app builder/material qualification, with real windowed MarsDisplay.exe worker-route checks plus test-owned Windows fake-backend children using the same worker core. No shipping fake-backend flag/environment switch and no fake empty-Qt/lean approval. Keep existing source/license/native-material gates unchanged unless narrowly necessary for helper source closure; explicitly include carried fixtures and new proof source in the source archive. A build verifies source stability and uploads only qualified source-bound artifacts under existing repository policy. Do not introduce a new general verification framework or use a surrogate test EXE as proof of the actual windowed entrypoint.

### S6 — Acceptance, regression and stopping boundary
> **Accept:** bounded fake-port hangs and native packaged process tests; startup
> containment before I/O, only own-child termination, confirmed reap, no pipe deadlock.

> **Rollback:** close/reap only the owned helper and disable native admission; no reset.

Use public behavioral RED/GREEN tests for each requested rule, all observable rejection effects, exact command streams/exits and unchanged counters/settings. Cover repeated frames through one owned child/port, malformed IPC/identity/frame rejection, hanging open/write/drain/close/launcher, blocked IPC both ways, cancellation, parent death and cleanup uncertainty. Test-old behavior for every changed shared bootstrap/helper; compare old/new public forms with the new input on isolated base state, not committed git-history assertions. Full regression and one independent verification follow the actual escalated risk items 4/5 (and worker admission guards), regardless of RDD being off.

Native Windows proof must inspect the actual windowed EXE before Qt startup and owned process lifetimes without an open-device request; native test-owned injected children exercise fake port hangs, not a production fake mode. No owner continuous hardware/FPS/hotplug test belongs to P3; those remain P6. Close P3 only after required source, regression, native packaging and verifier evidence is observed. Missing/unavailable proof is one concrete blocked decision, never a claimed pass or an extra auxiliary verification project.

## Tasks

- T0 [S1,S4] route: parent inline baseline/contracts; status: in_progress; commit: pending — Prepare fresh-main branch, selected prerequisite carryover, isolated in-project state and documented IPC/deadline boundaries. Risk: none (prerequisite snapshot/docs).
- T1 [S2,S3] route: parent inline dependent unit; status: pending; commit: pending — Bounded binary IPC and persistent serial worker core with public fake-provider tests and protocol docs. Risk: item 4 (duplex session/lifetime), admission validation.
- T2 [S2,S4] route: parent inline dependent unit; status: pending; commit: pending — Owned gated launcher, UsbTransport, cancellation, finite exchange/cleanup and retained uncertain ownership; tests/docs. Risk: item 4 (concurrency/process lifetime).
- T3 [S1,S5] route: parent inline dependent unit; status: pending; commit: pending — Early windowed bootstrap, exact source closure, native worker smoke/workflow and old command preservation/differential. Risk: item 5 (packaging/CI), item 4 (worker route).
- T4 [S1–S6] route: parent native checks + one independent verifier; status: pending; commit: pending — Full regression, actual Windows native build/process tests, source/artifact/license readback and final docs. Risk: items 4/5. No app output or P4–P6 activation.

## Log

L1 — Owner original request, verbatim: `adelante con P3`.
L2 — Previous P0–P2 closure is6bff97befee7b1e72f7afbcef3ab482a89011ea2; owner console/photo qualified one actual Python portrait, not streaming. Parent fresh-main preflight job27 exit0: fetchedorigin/main44b0f737e78011fc2f1014baaab9fa59f78fdfae, repositoryghosthvj/MarsDisplay/defaultmain/viewerADMIN. Created newbranchref feat/native-usb-helper at exactmain, not switched or carried source yet; oldbranch/main/artifact unchanged.
L3 — Bounded read-only map mvi2nmfy-q-pkwu: preserve structuralTransport, sharedframevalidation and Simulation; no existing persistent IPC. P2 WindowsJobGate clears handle fields after failed CloseHandle, so preserve it and use P3 ownership-retaining controller. Actual packaging/MarsDisplay.spec is windowed and bootstrap has no earlyroute; fullappbuilder/materialgate is appropriate, not diagnosticconsoleprofile. Sourcecollector omits tools/binaryfixtures and newworkflow needs explicit inclusion. Parent spotchecked bootstrap/sourcecollector/buildordering. No source edits/tests/network/USB by mapper.
L4 — Resolve bootstrap uncertainty without socket handle sharing or blocking pipe bootstrap: fixed private loopback with ephemeral port/nonce, all send/recv/accept absolute-timeout controlled; Windows exclusive bind. Context7 Python3.13 reference supports socket timeouts/exclusivebind; official https://docs.python.org/3.13/library/subprocess.html explicitly states process creation may outlive timeout. Startup uncertainty is retained, not hidden; safety caps are provisional. No new dependencies or production timing claim. These are reversible implementation choices inside approvedP3, not P4/P5 decisions.
L5 — Large task because native external checks and cross-session resumability require a durable feature. No independent writer units exist: runtime, bootstrap, tests/docs are one dependent behavior, so work inline absent a runtime context-backstop signal. Use the cached feature-branch-chain review preference and coherent risk-separated work-unit commits; no PR/mainmerge. Old P0–P2 temporary grant is not reused; tests/state stay in owned ignored build/P3 area unless a later exact outside grant is required.
