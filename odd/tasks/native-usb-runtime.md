# P5 truthful native output and explicit selection
Implement P5 only on `feat/native-usb-runtime`, chained from verified P4 closure `a4120ea3779ba550a903f8bb532fd38a0f4d2099`; preserve P0–P4 branches/artifacts and default Simulation.
Forecast roughly 1500–2200 authored lines with tests/docs across dependent, risk-separated work units. Qualified production timing and continuous hardware acceptance remain P6; all agent probes use owned ignored `build/p5-state`.

## Specs

### S1 — Authorization and non-goals
> adelante con P5

Accepted P5 plan is `docs/usb-integration-plan.md`, based on completed P4 API-only contracts. Implement native context composition, truthful lifecycle/output/preview and explicit stopped selection/migration UI. Do not change browser/source contracts, P3 wire/pixel protocol or P4 data format. Preserve legacy zero-argument factories, simulated landscape/retry behavior and prior diagnostics. No actual host USB, vendor execution, firmware/reset/clear/brightness/power command, arbitrary backend/module/endpoint setting, global installs, installer/service/autostart, PR/release/main merge or P6/hardware/performance qualification.

### S2 — Explicit native composition and host completion
> **Dependency:** P4. Change native composition, output states, selection UI and
> accepted-host-frame wording together. Preview still observes the accepted frame,
> not a new capture or panel ACK. A send only advances frame/count after host success;
> failed writes leave the previous accepted preview/count intact.

Compose from P4's immutable StartContext: simulated settings select Simulation; only explicit validated schema-2 native mode/profile/opaque identity select UsbTransport with the same cancellation event. No legacy identity inference, zero-argument native fallback, mutable store reload or import/constructor inventory/open/spawn. Resolve current unique identity/COM again through existing P3 admission on open/send, never follow an old COM. Keep counters/frame identity and pixels unchanged on rejected/failed native sends. Retained previous Simulation frames use neutral accepted-host wording, not retroactive USB-delivery or panel claims. Unsupported native landscape rejects without rotation/cropping/resend; Simulation keeps both geometries.

### S3 — Native failure and ownership classification
> Classify native failures instead of applying shared stage-exception recovery:
> safe transient **pre-write** failures may use a bounded approved recovery policy;
> partial writes are fatal/uncertain and must not auto-resend. Resource/termination
> uncertainty separately latches cleanup failure and retains lock/Exit ownership.
> Preserve existing simulated retry behavior exactly. Reopen only after fresh unique
> identity resolution; never send to an unrelated device that acquired the old COM.

Choose conservative zero automatic retries in native mode, including safe pre-write failures; explicit Start after confirmed cleanup is the only retry. Preserve exact Simulation retry policy/delays. Distinguish pre-write/rejected input, delivery uncertainty and cleanup/resource uncertainty with fixed sanitized diagnostics, not backend messages or string-parsed exceptions. A native close error after confirmed reap (`owned=False` and no ownership uncertainty) is a failure, not invented resource leakage. Unknown native ownership or source-close failure retains strong resource references and the cleanup latch; no new registry, retry-close UI or forced unrelated process cleanup. Report only known resource closure.

### S4 — Stop/Exit and admission authority
> Stop remains nonblocking with no automatic resume. An in-flight operation may
> finish before acknowledgement; after **acknowledged Stop**, no writes or counter
> increments occur. Keep Save/Start guards, actual worker-finish acknowledgement and
> Exit readiness; no UI-thread joins. Retain browser/source contracts untouched.

Stop cancels through the same event and never closes transport/joins the worker on the UI thread. Only actual finished worker plus known cleanup can acknowledge stopped/Exit readiness. Retain instance lock and disallow restart/save/Exit on uncertain resources, even after a worker returns. Confirmed-close errors may report failure without permanently inventing Exit ownership. Save/migration/restore/export continue to recheck P4 stopped/no-worker/no-exit authority after queued actions/modal dialogs. Source live/stale observations remain separate from output/device status.

### S5 — Stopped explicit selection and reversible UI
> **Accept:** public lifecycle/tray/preview tests cover error classes, unchanged
> counters/settings on rejection, Stop/Exit hangs, no deadlock and uncertain-resource
> lock retention. **Rollback:** Simulation default with confirmed own-child cleanup;
> never mask uncertainty by claiming stopped or forcing unrelated processes closed.

Add explicit output mode, passive Refresh and opaque identity selection with the one supported profile. No automatic first choice, legacy-identity opt-in, import/load enumeration or periodic hotplug polling. Existing schema-1 URL-only Save remains schema 1; schema-2 edits preserve fields. Native Save uses fresh P4 selection checks; refresh observations are not permanent admission. GUI schema-2 migration requires clear older-binary incompatibility/preserved-backup warning, default No and explicit confirmation, then Coordinator rechecks authority. Offer only minimal explicit export/restore through existing P4 APIs; never silently downgrade or erase unknown data. Draft controls do not change active output or saved Start settings. Controls remain in the scrollable body with reachable footer, plain text, keyboard operation and stopped-only guards. Preview observes accepted frame only, without another capture, scaling, disk history or panel-ACK claims.

### S6 — Proof and stopping boundary

Use public behavioral RED/GREEN per requested rule, unchanged bytes/counters/frame/resources on rejection and exact command/message outcomes where applicable. Preserve old behavior for every shared edited seam and compare prior P4 `a4120ea` versus candidate public forms in owned isolated copies, not committed Git-history tests. Probe real UsbTransport integration with test-owned peers/children for lost CLOSE acknowledgment versus unresolved ownership, not synthetic flags alone. Run focused/full regressions and applicable real Windows/windowed build/source/native/material/source-binding checks, one final independent verifier for named data/guard/shared-contract/concurrency risks, and one parent spot check. Native RDD remains user-owned; no invented approval. Passive docs use structural checks, not fabricated RED. Physical continuous portrait, unplug/replug, FPS, latency/capacity, production budgets and landscape hardware gate remain P6. Missing/unavailable/exhausted proof stops as one concrete owner decision, not extra verification frameworks or blind retries.

## Tasks

- T0 [S1–S6] route: parent inline; status: in_progress; commit: pending — Settle safe policy, chained baseline, tracking, isolated state and dependency boundaries. Risk: none (planning).
- T1 [S2–S4,S6] route: parent inline dependent unit; status: pending; commit: pending — Native lifecycle states/failure/retained ownership and explicit context composition, real-transport public probes, preserved Simulation and host-only counter semantics, tests/docs. Risk: items 2/3/4 (admission/shared contracts/concurrency).
- T2 [S1,S4–S6] route: parent inline dependent unit; status: pending; commit: pending — Explicit stopped selector/refresh/migration/export/restore and truthful runtime/host-preview wording, public UI/reentrancy/lock tests and docs. Risk: items 1/2/3/4 (migration consent, admission, shared UI/state/cleanup ownership).
- T3 [S1–S6] route: parent checks + one independent verifier; status: pending; commit: pending — Full/differential/Windows applicable proof, artifact/source/native/material readback, one final independent verdict, spot and closure. Risk: inherited named items; item 5 only if delivery/environment code changes.

## Log

L1 — Original request, verbatim: `adelante con P5`.
L2 — Read-only mapper mvibgee7-v-23lf examined the remaining lifecycle, UI/preview/composition and public tests; parent spotchecked lifecycle251–355. Existing send-before-counter ordering is sound; cleanup discards resource refs, all failures share Simulation retry, and labels/reset paths hardcode Simulation. P3 close may raise after confirmed reap; distinguish known closed from uncertainty rather than latching everything. CodeGraph refused non-Git parent cwd, file-read fallback used; no execution/writes/network/hardware.
L3 — No consequential product question remains: choose zero automatic native retries (plan only permits optional approved pre-write retry), retain unresolved resource refs/latch without recovery framework, compose only from validated immutable StartContext, neutral accepted-host preview wording, explicit mode/Refresh/identity with default-No migration warning and P4 rechecked authority. Minimal recovery uses existing APIs, not a general file manager. P6 remains separate.
L4 — Created `feat/native-usb-runtime` from clean exact P4 closure `a4120ea3779ba550a903f8bb532fd38a0f4d2099`, not main or a prior branch rewrite. Created ignored0700build/p5-state/{home,tmp,cache,config,data,state}. No outside temporary grant reused. All Git commands explicitly cd project because parent cwd is not Git.
L5 — Large because dependent runtime/UI/ownership contracts and external native evidence must survive compaction; the resume test needs this specification. No independent writer units: lifecycle → composition → selection/presentation depend on the same frozen contract. Inline unless runtime context backstop fires. Keep tests/docs with cohesive risk-separated commits, no size-only splitting. Source push/CI follows existing repository/standing permission; no new release/merge grant inferred.
