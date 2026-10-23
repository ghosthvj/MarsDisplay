# P5 native runtime contract

**P5 software qualification passed at `56ea091cfae996101e5106cf1acc64898bd52b59`.**
Native lifecycle, explicit stopped selection, migration/recovery and host-preview
behavior passed local, Windows and independent checks. This is not physical-screen,
performance or interactive Windows-tray acceptance; those boundaries remain below.
The immutable ZIP contains earlier pending wording, superseded by this record.
Track work in [the P5 ledger](../odd/tasks/native-usb-runtime.md).

## Saved brightness candidate

Schema-3 native settings add five brightness choices: **20%, 40%, 60%, 80%, 100%**.
Older schema-1/2 configurations retain their previous behavior with no brightness
commands until explicit stopped migration. See [settings recovery](usb-settings.md).

`Coordinator.enable_brightness(acknowledge_legacy_incompatibility=True)` migrates
only the saved native configuration while stopped and rechecks device selection.
`set_brightness(percent)` validates and atomically saves only brightness, then
replaces one latest requested value. It never applies unsaved URL/device drafts,
opens a port, or performs USB work on the UI thread. Failed saves leave intent
unchanged. Live changes reject an externally changed configuration; stop and
review it rather than overwriting it. Stop/error/Exit reject changes.

The existing capture thread applies the saved value after explicit native Start
and subsequent changes between complete frame operations on the same connection.
Rapid pending changes coalesce to the latest value. No frame is interrupted,
resent or counted for a brightness command, and frame timing excludes that command.
Loading/empty source observations do not prevent brightness application. The
snapshot separates `brightness_requested` from `brightness_applied` (last successful
host completion in this Start), never a measured panel value.

Brightness failure stops native output without automatic retry or restoration:
`native-brightness` means reported failure without known transfer;
`native-brightness-uncertain` means delivery is uncertain. Explicit Start reloads
the saved choice; Stop/Exit sends no brightness command. Windows packaged acceptance
of this integration remains separate from the earlier isolated Linux test.

## Explicit output composition

The app constructs output from one validated, immutable StartContext:

- Schema 1 or explicit simulated mode constructs Simulation, even with a saved
  opaque device identity. No identity alone grants native permission.
- Explicit validated schema-2/3 native mode/profile/identity constructs the
  [owned USB transport](usb-helper.md) with that Start's same cancellation event.
- Construction/import/load does not enumerate, open a port or launch a helper.
- A legacy zero-argument-only factory cannot start native settings. It reports:
  `Native output requires an explicit Start-context factory; no fallback was started.`

There is no callable-arity guessing, TypeError fallback, worker-side settings reload,
per-frame process, extra queue or automatic backend substitution. Existing source
and browser contracts are unchanged. Native open/send reuse P3's fresh unique
identity/COM checks; a former COM reassigned to another device is not a target.

## Host acceptance, not rendering acknowledgement

The counter and retained latest-frame object/pixels advance only after `send()`
returns confirmed host success. A failed, rejected or uncertain send retains the
previous accepted frame and count. No native rotation/cropping is attempted.
Native output accepts only validated 320x480 portrait; Simulation still accepts
both shared geometries. A send rejected before submission reports:

> Native output rejected the frame before submission; only validated 320x480 portrait is supported.

Neither successful host writes nor an empty host queue prove panel rendering,
health, physical pixel equivalence or FPS. A retained older Simulation frame must
not become “USB received” merely because the next configuration is native.
Preview remains an observer with neutral “accepted by host output” wording, not a
second capture, USB reception/panel acknowledgement or an image history. The
lifetime counter is labeled “Host-accepted frames”; runtime output uses the actual
snapshot mode, independent of draft settings and source live/stale observations.

## Native numeric timing (diagnostic candidate)

Status / Settings shows **Native timing** in its scrollable body. Diagnostic source
`d79eb805a943ddc4f0ee08a108a885e3edc23833` passed separate Windows and artifact
qualification; it is not the immutable P5 ZIP. Use the
[verified diagnostic package and measurement steps](usb-hardware-qualification.md#verified-numeric-diagnostic-package).
Hardware stage measurements and production budgets remain pending.

| Stage | Successful sample measures |
|---|---|
| Source read (observations) | One completed `source.read()`, including observations without a frame |
| Host send (encoding / IPC / helper total) | One successfully returned `output.send()`; host-side total, not isolated serial write/drain or panel rendering |
| Cadence wait (non-cancelled) | Actual elapsed wait, not the requested remainder; cancelled waits are excluded |

Each stage shows its independent count, last, minimum, maximum and mean in
milliseconds. A zero count displays dashes, not measured zero latency. The immutable
snapshot holds only thirteen fixed-size numeric aggregates in RAM (durations internally
in seconds). There are no timestamps, images, URLs, identities, credentials, histories,
logs or exports in this diagnostic. Reading the display does not capture another frame.

Every admitted native Start resets the aggregates, including a Start that later
fails during setup. Duplicate/rejected Start does not reset them. Stop and errors
retain them; a subsequent Simulation Start removes the native report. Lifetime
host-frame counters and the retained preview are unchanged. Successfully completed
source/send calls may be counted during Stop; cancelled waits and failed calls are
not counted. Source observations therefore need not equal accepted frames.

The diagnostic monotonic clock is separate from scheduling. The one-second cadence
target, synchronous backpressure, cancellation, zero native retries, transport and
safety deadlines remain unchanged. Successful-duration aggregates omit failures and
cannot alone establish failure deadlines, panel FPS or production capacity.

### Internal send detail (unqualified candidate)

The lifecycle reads optional `UsbTransport.last_send_timing` only after successful
send; see [the helper API](usb-helper.md#source-api-and-ownership). Seven additional
rows show independent count/last/min/max/mean milliseconds:

| UI row | Successful sample measures |
|---|---|
| Helper frame decode (ms) | Frame payload decoding and validation |
| Helper identity resolution (ms) | Current unique device identity resolution |
| Helper RGB565 encode (ms) | Portrait packet encoding |
| Helper packet writes (ms) | Total packet-write loop |
| Helper queue drain (ms) | Host queue-drain loop |
| Host IPC body encode (ms) | Parent frame IPC-body encoding |
| Host exchange (includes helper work) (ms) | Full parent request/reply exchange, including helper work |

Exchange and helper stages overlap: **do not sum them as separate costs** or call
exchange pure IPC/USB latency or panel rendering. Missing/None optional detail
leaves counts unchanged; count-zero detail rows show `unavailable (count 0)`, not
measured zero latency. A successful measured zero has a positive sample count.
Failed sends never aggregate retained stale detail. Admitted native Start resets
all thirteen aggregates; Stop/error retain them and Simulation has no native report.
No extra capture, history, settings, logs or export is introduced.

Existing qualified P5 and `d79eb80` diagnostic ZIPs remain immutable; this new
candidate requires its own Windows/source/artifact qualification before owner use.

### Grouped writes (unqualified candidate)

The original ten rows remain. Three more rows show **Helper orientation write**,
**Helper bitmap-header write**, and **Helper pixel writes**, each with independent
count/last/min/max/mean milliseconds. These are subsets of **Helper packet writes**,
not additional costs; the total write measurement remains available.

Only fully validated successful sends contribute. Optional earlier transport detail
without `groups` leaves these rows unavailable, not measured zero. Stop/error retain
all successful aggregates; admitted Start resets them and Simulation removes the
report. The existing scrollable status body keeps Save in its reachable footer.
Device bytes, serial options, scheduling, cancellation and deadlines are unchanged.
This richer IPC pair needs independent exact-source Windows/artifact qualification;
none of the earlier immutable diagnostic packages acquires these rows retroactively.

## Failure and cleanup policy

Native mode has **zero automatic retries**, including safe pre-write and source
failures. After known cleanup, retry requires a deliberate Start and fresh admission.
No partial write is resent. Simulation retains its existing retry behavior exactly.

Snapshot adds `output_mode`, `failure_kind`, `delivery_uncertain` and
`ownership_uncertain`; existing source/live/stale observations are not panel state.
Native states include `native-opening`, `native-open`, `native-host-complete`,
`native-closed`, `native-error` and `native-cleanup-uncertain`.

| Outcome | Meaning |
|---|---|
| `native-prewrite` | Startup/known pre-write failure; no accepted frame and no automatic retry |
| `native-rejected` | Invalid/unsupported frame rejected before submission; no pixel writes |
| `native-source` | Capture/source failed; native output is not reconnected/retried |
| `native-delivery-uncertain` | Submission may have written pixels; preserve prior accepted frame/count, never resend |
| `native-close` | Close acknowledgement failed, but owned resources/reap are confirmed released; do not invent ownership uncertainty |
| `native-cleanup-uncertain` | Final resource closure is unknown; retain strong references and latch Start/Save/Exit ownership |

`UsbError.phase` is structured diagnostic context alongside its uncertainty flags;
no backend exception-message parsing, supplied URL/identity logging or raw exception
reporting is used. An initial operation uncertainty is visible during cleanup and
can clear only when actual cleanup confirms closure. Unknown close/source failures
are conservative. Retained references are bounded by the one admitted session;
there is no new cleanup registry, retry-close UI or forced unrelated-process kill.

## Stop and Exit

Stop only signals cancellation; it does not join a thread or close output on the
UI thread. A currently in-flight operation may finish before acknowledgement and
may therefore advance host acceptance while stopping. Actual worker completion
and known cleanup are required before acknowledged Stop/Exit readiness.
After acknowledgement, no writes or count advances occur and nothing resumes.
A cancelled uncertain transfer can be stopped with resources released while still
showing its delivery-uncertainty diagnostic; stopped does not undo panel writes.

A worker's return is not proof of unknown resource cleanup. If uncertainty remains,
keep the instance lock and Exit ownership, reject restart/Save and never pretend
stopped or “force quit.” A lost close acknowledgement after confirmed reap may
show failure without permanently blocking Exit. Source that really closed is not
reported as still capturing. Existing simulated cleanup/Stop/Exit behavior remains.

## Configure output while stopped

1. Stop capture and wait for actual cleanup acknowledgement.
2. Choose **Simulation** or **Native USB** under Configuration. Native supports only
   `tus35-portrait-v1` (320 × 480 portrait).
3. For a new native selection, click **Refresh USB identities** and explicitly
   choose the supported opaque identity. Refresh never selects the first device,
   opens a port or proves continuing availability. There is no periodic polling.
4. Click **Save**. First native opt-in requires schema 2: the warning explains
   older-binary incompatibility and preserved schema-1 backup, defaults to **No**,
   and requires explicit **Yes**. Save rechecks current unique device admission.
5. Start explicitly. Drafts, Refresh and Save never start or resume capture.

A schema-1 URL-only Save stays schema 1, including with a legacy identity.
Schema-2 URL edits preserve the output/profile/identity fields. Switching to
Simulation keeps schema 2 and its passive identity; it is not a downgrade.
Saved native identity is shown without enumeration. Refresh always requires a
new explicit choice; missing/duplicate devices are not guessed or substituted.

**Export schema-1 settings…** creates a new old-readable file without changing
current settings or overwriting an existing destination. **Restore preserved
schema-1 backup…** asks for default-No confirmation, restores original bytes through
the Coordinator, and reloads the form in Simulation. Unknown data or invalid backup
errors remain visible; neither action silently repairs or erases configuration.
All configuration controls are in the keyboard-accessible scrollable body; Save
remains in the visible footer. Queued actions and modal confirmations still pass
through the Coordinator's stopped/no-worker/no-exit checks after the dialog returns.

The [P4 configuration format and rollback contracts](usb-settings.md) are preserved.
No real USB tests ran on the agent host; tests use controlled peers/children/fake
ports. Continuous hardware, latency/capacity, hotplug, production deadline budgets
and additional landscape qualification remain **P6**, not claims from unit tests.

## Verified P5 evidence

[Windows run 39645553766](https://github.com/ghosthvj/MarsDisplay/actions/runs/39645553766)
qualified exact source `56ea091cfae996101e5106cf1acc64898bd52b59`:

| Check | Observed result |
|---|---|
| Windows source tests | 253 passed / 65.572s, zero skips |
| Local full regression | 253 tests / 26.980s: 249 passed, four Windows-only skips |
| Public P4 differential | 12 cases: ten exact stdout/stderr/exit matches, two intended native changes |
| Packaging correction | RED reproduced missing guide; 16 focused tests passed; differential added only the guide with prior bytes unchanged |
| Independent UI verification | 45 focused tests plus three modal/draft probes, no blockers |
| Final independent verification | 54 focused tests plus two composition/ownership probes; S1–S6 met, reusing UI evidence |
| Parent final spot | 54 tests / 1.756s, all passed, no skips |
| Parent and independent ZIP readback | 1,249 payload hashes; 353 sources (349 exact Git Windows-checkout files plus four SDK records); 69 AMD64 PE32+ binaries; GUI subsystem 2 |
| Native/material closure | 27 Qt and six supplemental components; 209 material hashes; actual windowed worker smoke passed |

Artifact `12367770679` contains `MarsDisplay-0.1.4-Windows-x64.zip`,
205,687,478 bytes, SHA256
`24d8ce2fff5d9455a08c8fac2251346f0fc9a010653abe13caa0106df910171d`.
The runtime guide is present and bound to the committed Windows-checkout bytes.
The prior `9b80139` ZIP failed guide inclusion and is not the qualified candidate.
Its failure was fixed, not waived; neither historical ZIP was rewritten.

Worker smoke exercised private admission, HELLO/CLOSE, malformed IPC, startup gate,
parent death and owned reap without OPEN or a device request. Source/native/material
binding is mechanical evidence, not legal certification or physical rendering proof.
The earlier exact RDD candidate was declined through host consent; this software
qualification is functional verification, not an RDD approval. P6 remains separate.
