# P5 native runtime contract

**Under implementation, not qualified.** Runtime composition/lifecycle tests are
passing; the stopped selector, migration/recovery controls and host-preview UI are
implemented with focused offscreen tests. Final differential, Windows and independent
acceptance remain pending.
Do not interpret intermediate source commits or P3/P4 evidence as P5 acceptance.
Track work in [the P5 ledger](../odd/tasks/native-usb-runtime.md).

## Explicit output composition

The app constructs output from one validated, immutable StartContext:

- Schema 1 or explicit simulated mode constructs Simulation, even with a saved
  opaque device identity. No identity alone grants native permission.
- Explicit validated schema-2 native mode/profile/identity constructs the
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
