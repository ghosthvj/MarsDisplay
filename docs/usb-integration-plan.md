# USB integration proposal for MarsDisplay

**Application wiring remains a proposal: the app still uses Simulation.**
P0–P4 are complete. P4 delivered API/contracts only;
the selector and native composition remain P5. P5–P6 are not authorized. The
[working diagnostic guide](usb-screen-guide.md) establishes one owner-accepted
portrait through each standalone C# and Python diagnostic. Those physical
observations alone do not qualify continuous output or production timing.

**Implementation update:** the owner has authorized `ok, vamos con P0 - P2`.
Those completed stages are recorded in the
[accepted Python bridge ledger](https://github.com/ghosthvj/MarsDisplay/blob/6bff97befee7b1e72f7afbcef3ab482a89011ea2/odd/tasks/native-python-usb-probe.md).
The owner authorized `adelante con P3`; that bounded helper stage is now complete
in the [helper ledger](../odd/tasks/native-usb-helper.md). The subsequently authorized
[P4 contracts](usb-settings.md) are also complete as API-only work;
P5–P6 remain proposals and application USB output is not authorized.

**Current gate:** P0–P2 are complete, including owner physical acceptance of one
frozen portrait image on 2026-10-21. The standalone Python P2 package at
`a26350dd74d1d03d999bbead5195dfc20d4a5344` passed
[Windows qualification](https://github.com/ghosthvj/MarsDisplay/actions/runs/39512376268):
70 tests without skips, extracted frozen commands and owned-process lifetime checks.
Source, licenses, native bytes and checksums passed parent and independent readback.
The final local regression run passed 226 tests, with three Windows-only skips;
independent focused verification passed 67, with the same three expected skips.
**P2 physical acceptance is observed:** the owner supplied the Python console
(`COM5`, typed `SEND COM5`, 122 packets/307222 bytes completed) and a photo visually
matching the canonical reference. See the
[Python evidence and limits](usb-screen-guide.md#python-p2-owner-validated-frame).
This is one-frame proof, not a device rendering ACK or continuous-output qualification.
P3's persistent bounded helper is qualified at `8841770b7f46f6aa057e80ef5d7cafafe2d19c7d`:
[Windows run 39611543729](https://github.com/ghosthvj/MarsDisplay/actions/runs/39611543729)
passed 202 tests without skips and actual windowed worker-lifetime checks. Artifact
readback and the independent S1–S6 verification passed; see
[helper evidence and limits](usb-helper.md#verified-evidence-and-limits).
P4 API/contracts are qualified at `91e20904cb5f729c520a6fd6799e69087a0cccc6`:
[Windows run 39629193023](https://github.com/ghosthvj/MarsDisplay/actions/runs/39629193023)
passed 227 tests without skips; source/artifact/recovery and independent S1–S6
verification passed. See [P4 evidence](usb-settings.md#verified-p4-evidence-and-limits).
P5–P6 remain unauthorized. MarsDisplay stays in Simulation; native Start is rejected
and no native application wiring is enabled.

Original request, verbatim:
> documenta todo lo necesario para poder trabajar con la pantalla y prepara el plan de integracion en MarsDisplay!

## Recommended route and decision gates

Keep Simulation as the default. Recommend a native Windows Python/pyserial child
adapter using the existing `pyserial==3.5` pin, but first prove the deterministic
frozen image through that native packaged path. C# success does not qualify
pyserial. If the bridge fails, stop and compare evidence; a persistent C# helper
requires a justified architecture decision, not automatic fallback. Do not launch
the interactive one-shot `UsbScreenProbe.exe` per frame or treat it as an
unmodified production service.

Start future work from fresh verified main, leaving main untouched now. Carry only
explicitly selected diagnostic fixtures/docs from this feature branch, never an
implicit merge of the whole branch. Obtain new implementation authorization once
before executing this plan; then proceed with in-scope implementation, documentation
and checks without phase-by-phase permission. Halt only for unresolved consequential
decisions, safety gates or missing required proof. This documentation request does
not activate implementation tasks.

## Current code map: preserve these seams

Paths below are repository-root paths; proposed new files are backticks, not links.

| Existing area | Current contract / planned seam |
|---|---|
| [app.py](../src/mars_display/app.py), `build_shell` | Composes idle `Coordinator(store, BrowserSession, SimulatedTransport)`. Change composition only after native gates pass. |
| [transport.py](../src/mars_display/transport.py) | Synchronous `Transport.open()`, `send(RGBFrame)`, `close()`; preserve simulation and injection. |
| [frames.py](../src/mars_display/frames.py) | Immutable tightly packed RGB888, top-down rows; 320×480 or 480×320 and finite capture timestamp. Do not narrow this shared contract. |
| [lifecycle.py](../src/mars_display/lifecycle.py), `start`, `_run` | Settings frozen at Start; output factory takes zero arguments. Latest frame/count update only after send returns. No queue; default capture cadence targets one/second, not a hardware FPS guarantee. |
| Same lifecycle, `_cleanup`, `_reap_locked` | Simulated states are hardcoded at initialization/open/cleanup/reap. Source/output stage exceptions share recovery with five additional attempts at 1,2,4,8,16 seconds unless cleanup fails. Cleanup failure latches error and stops retries; outer worker faults do not globally retry. Stop acknowledges actual worker finish and Exit waits for certainty. |
| [settings.py](../src/mars_display/settings.py) | Strict schema 1, URL plus opaque identity only, no output mode; validated atomic Save. Reuse `SettingsStore.save`, not an inline serializer. |
| [devices.py](../src/mars_display/devices.py) | Passive inventory and `select_device` require a unique explicit opaque identity. Follow its current COM; never first-device selection. Reuse these validators/selection rules. |
| [tray.py](../src/mars_display/tray.py) | Simulation wording, read-only identity, stopped-only Save and lock/Exit ownership guards need explicit native treatment. |
| [preview.py](../src/mars_display/preview.py) | Observes accepted frame, currently labeled simulated; never initiates capture. |
| [browser.py](../src/mars_display/browser.py) | Existing renderer/readiness/capture contract stays unchanged. No MARS backend/API changes. |
| [packaging/entrypoint.py](../packaging/entrypoint.py) | Windowed bootstrap captures sanitized app diagnostics and calls `run()`; no current helper dispatch/freeze-support qualification. |

Regression anchors are `tests/test_lifecycle.py`, `tests/test_devices.py`,
`tests/test_preview.py`, `tests/test_tray.py` and `tests/test_app.py`, plus public
CLI outcomes and native packaging checks. Verify actual test entrypoints when
implementing; these are future checks, not new evidence from this documentation.

## Stages, acceptance and rollback

### P0 — Freeze evidence and scope

**Dependency:** new implementation approval and a fresh verified-main baseline.
Record source `8227c002a48084d8c463400f45cd641f62359bb4`, diagnostic hashes,
canonical PNG/payload and the one-frame owner proof from the guide. Agree which
fixtures/docs to carry, license notices and the exact portrait-only profile.

**Accept:** reproducible provenance with no owner photos/vendor resources copied;
reviewable isolated branch. **Rollback:** discard proposal changes without merging
feature history into main or touching the verified diagnostic artifact.

### P1 — Pure encoder and explicit profile

**Dependency:** P0. Proposed areas: `src/mars_display/usb_protocol.py` and dedicated
protocol tests, reusing `RGBFrame` validation and device-selection invariants.
Encode RGB888 to RGB565LE and the exact portrait orientation/header/chunks in the
guide. Reject unsupported geometry/profile, wrong frame, unknown or duplicate
identity before port open or any write; no inference from VID/PID alone.

**Accept:** public pure-interface tests compare every pixel, byte, chunk count and
serial option against the frozen fixture; rejected input leaves observable frame,
counters and settings bytes unchanged. **Rollback:** retain an unused pure module
or revert this unit; Simulation remains untouched.

### P2 — Native Python single-image bridge gate

**Dependency:** P1; before production wiring. Use the canonical frozen image,
not a fresh browser render. Qualify native Windows pyserial options, write/drain/
close behavior and the packaged child launch path with explicit device selection.
No continuous mode, GUI integration or arbitrary input/commands at this gate.

**Accept:** exact transfer evidence, bounded completion and owner photo matching
the reference from the actual native packaged path. Linux fake-port tests or
successful C# output are insufficient. If this fails, stop; compare bytes/options,
identity and delivery evidence before proposing a C# architecture alternative.
**Rollback:** retain the standalone diagnostic, do not enable native application output.

### P3 — Persistent bounded helper

**Status:** complete after native/source/artifact/independent verification at
`8841770b7f46f6aa057e80ef5d7cafafe2d19c7d`. Safety caps remain provisional,
not measured hardware capacity; application USB output is not enabled.

**Dependency:** P2. Implemented seams: `src/mars_display/usb_transport.py`,
`usb_process.py`, `usb_ipc.py`, `usb_worker.py`, packaging bootstrap/recipe and tests.
Expose the synchronous transport contract through one persistent owned native
child, one in-flight frame, bounded IPC lengths/types/profile and explicit replies.
No arbitrary commands, image/URL logging, disk frame history or per-frame process.

Specify start/write/drain/close/kill/reap deadlines and cancellation semantics before
wiring. Measure latency/capacity to set a production budget; diagnostic 90 seconds
is not that budget. Qualify child entrypoint routing before Qt/app launch, sanitized
reporting and `freeze_support` if using multiprocessing. Do not assume
`sys.executable -m ...` works in PyInstaller. Native packaged tests must prove it.

**Accept:** bounded fake-port hangs and native packaged process tests; startup
containment before I/O, only own-child termination, confirmed reap, no pipe deadlock.
Unknown cleanup fails closed, never reports success or releases ownership.
**Rollback:** close/reap only the owned helper and disable native admission; no reset.

### P4 — Explicit settings and stopped-only opt-in

**Status:** authorized by `continúa entonces con P4`; owner selected
`Contratos/API en P4; selector en P5 — recomendado`. Complete and qualified at
`91e20904cb5f729c520a6fd6799e69087a0cccc6` after source/Windows/artifact/old-reader
recovery and independent verification. See [the P4 contracts](usb-settings.md) and
[task ledger](../odd/tasks/native-usb-settings.md). No native Start or selector is enabled.

**Dependency:** P3; settle schema/migration/rollback design before coding.
Propose schema 2 with strict explicit output mode, native profile and selected
opaque identity; settle explicit migration design and exact fields/validation within
the authorized implementation scope, asking the owner only for unresolved product
choices with consequential effects.
Read schema 1 as simulated without automatic rewrite. An old saved identity is
**not permission to open hardware**. Only stopped explicit Save may migrate via
existing validated atomic persistence; invalid input preserves original bytes.

An old binary rejects schema 2: require explicit user understanding, preserved
schema-1 configuration and a tested rollback/export path before enabling Save.
Never silently downgrade or erase unknown fields. Keep initial launch stopped,
Simulation default and no inventory/open during import or settings load.

Preserve existing zero-argument transport-factory injection through a distinct
Start-context composition path carrying the already-frozen settings and cancel
signal. Do not guess callable arity, catch `TypeError` to retry construction, or
reread a mutable settings store in the worker. Native selection resolves current
COM from the selected unique identity on every open and rechecks before I/O.

**Accept:** stopped-only valid Save, invalid/legacy preservation, explicit opt-in,
duplicate/unknown rejection, COM moves and foreign old-COM occupant tests.
**Rollback:** return explicitly to Simulation using approved configuration recovery;
keep original bytes available for the older binary.

### P5 — Truthful lifecycle, UI and preview

**Dependency:** P4. Change native composition, output states, selection UI and
accepted-host-frame wording together. Preview still observes the accepted frame,
not a new capture or panel ACK. A send only advances frame/count after host success;
failed writes leave the previous accepted preview/count intact.

Classify native failures instead of applying shared stage-exception recovery:
safe transient **pre-write** failures may use a bounded approved recovery policy;
partial writes are fatal/uncertain and must not auto-resend. Resource/termination
uncertainty separately latches cleanup failure and retains lock/Exit ownership.
Preserve existing simulated retry behavior exactly. Reopen only after fresh unique
identity resolution; never send to an unrelated device that acquired the old COM.

Stop remains nonblocking with no automatic resume. An in-flight operation may
finish before acknowledgement; after **acknowledged Stop**, no writes or counter
increments occur. Keep Save/Start guards, actual worker-finish acknowledgement and
Exit readiness; no UI-thread joins. Retain browser/source contracts untouched.

**Accept:** public lifecycle/tray/preview tests cover error classes, unchanged
counters/settings on rejection, Stop/Exit hangs, no deadlock and uncertain-resource
lock retention. **Rollback:** Simulation default with confirmed own-child cleanup;
never mask uncertainty by claiming stopped or forcing unrelated processes closed.

### P6 — Native hardware and delivery qualification

**Dependency:** P5 and all prior proofs. Owner-run Windows tests cover continuous
portrait, unplug/replug, COM reassignment, duplicate devices, Stop during transfer/
retry, restart, Exit, process/resource lifetime and measured latency/capacity.
Keep the default capture cadence target of one/second with synchronous backpressure and no
extra queue; do not claim panel FPS from a timer or baud rate.

Qualify the packaged native helper, clean checkout build, dependency/license
notices, artifact/source hashes and real Windows delivery independently. Only then
consider **landscape as a separate gate**: no silent rotation/cropping of unsupported
native landscape, and no regression to already-supported simulated landscape.

**Accept:** reproducible owner evidence and measured production deadline budget;
continuous/reconnect/performance claims limited to observed conditions.
**Rollback:** select Simulation, preserve configuration and close only owned
resources. No firmware reset, protocol roulette or automatic transport fallback.

## Future test and review contract

For implementation, add deterministic public-interface RED/GREEN tests for new
behavior; assert exact stdout/stderr/exit codes for changed commands and all
observable rejection effects (no port open/writes, unchanged settings/counters/
preview). Cover finite I/O, owned-child hangs, malformed IPC, invalid frames and
identities, old COM occupants, stopped Save and cleanup ownership. Preserve every
existing command sharing changed code, including differential comparison against
the prior source. Do not use internal storage assertions or source-string tests
as substitutes for behavior or hardware evidence.

Shared settings/lifecycle/UI changes are risk item 3; owned processes item 4;
native packaging/CI item 5. Keep staged independent verification and user-owned
native RDD mode decisions with the parent. No review lifecycle is activated by
this proposal. Documentation itself changes no runtime behavior.

Out of scope: installer, service, autostart, firmware/reset, guessed bulk USB,
protocol auto-fallback, vendor binary redistribution, private endpoints, MARS
backend changes and merging main. Unknown Chrome failure cause, cross-platform
canvas equality and untested hardware capabilities remain unknown.
