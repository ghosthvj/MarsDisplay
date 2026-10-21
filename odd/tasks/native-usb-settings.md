# P4 explicit stopped-only output configuration
Implement P4 only on `feat/native-usb-settings`, chained from completed P3 `b39ace59da7084c2f2300f24558e38386902dd7e`; qualified runtime remains `8841770b7f46f6aa057e80ef5d7cafafe2d19c7d` until new proof.
Scope: API/contracts now, selector/native execution in P5. Forecast roughly 1000–1600 authored lines including tests/docs, dependent risk-separated reviewable commits; no size-only splitting. State/probes stay in ignored `build/p4-state`.

## Specs

### S1 — Authorization and boundary
> continúa entonces con P4

Owner selected:
> Contratos/API en P4; selector en P5 — recomendado

Implement schema/configuration, migration/recovery and Start-context contracts only. Preserve P0–P3 branches/artifacts and current GUI controls. Simulation remains the default; native Start must reject before worker/source/output/inventory/process effects, never silently fall back. No native selector, native application composition, new Stop/Exit/retry/preview semantics, P5/P6, hardware access, vendor execution, global installs, installer/service, PR/release/main merge. A small existing GUI binding change may preserve loaded fields; no new selection controls.

### S2 — Strict settings and passive legacy load
> Propose schema 2 with strict explicit output mode, native profile and selected
> opaque identity; settle explicit migration design and exact fields/validation within
> the authorized implementation scope, asking the owner only for unresolved product
> choices with consequential effects.

> Read schema 1 as simulated without automatic rewrite. An old saved identity is
> **not permission to open hardware**.

Keep schema-1 serialization/constructor defaults and positional compatibility. Schema 2 has exactly `schema_version`, `mars_url`, `device_identity`, `output_mode`, `native_profile`. Modes are `simulated` and `native`; simulated requires null profile and preserves passive legacy identity. Native requires profile `tus35-portrait-v1` and the exact P3 opaque identity `usb:1a86:5722:USB35INCHIPSV2`. Validate types/combinations/URL/duplicates/unknown keys/version before persistence; never store COM. Import, construction and load do no inventory/open/spawn/save. Existing URL-only GUI Save preserves the loaded version and new fields, not an implicit upgrade/downgrade.

### S3 — Explicit migration and reversible data preservation
> Only stopped explicit Save may migrate via
> existing validated atomic persistence; invalid input preserves original bytes.

> An old binary rejects schema 2: require explicit user understanding, preserved
> schema-1 configuration and a tested rollback/export path before enabling Save.
> Never silently downgrade or erase unknown fields.

Provide explicit trusted API acknowledgement of old-binary incompatibility before migration. Preserve exact valid original schema-1 bytes in a non-overwriting backup before replacing configuration; with no original, preserve a validated old-readable equivalent. Backup/export failure prevents replacement. Existing schema-1 Save does not migrate; schema-2 edits do not silently downgrade. Explicit validated export/restore is the recovery path, not implicit Save. Invalid, duplicate, unknown/future or inconsistent source/target data must not be erased. Test original-byte preservation and owned temporary/backup effects on failures. No real user settings are touched by agent checks.

### S4 — Authoritative stopped-only operations
> Keep initial launch stopped,
> Simulation default and no inventory/open during import or settings load.

> **Accept:** stopped-only valid Save, invalid/legacy preservation, explicit opt-in,
> duplicate/unknown rejection, COM moves and foreign old-COM occupant tests.

Use Coordinator's existing lock for Save/migration/recovery versus Start/Stop/Exit admission; stale UI state is not authority. Static settings validation and passive fresh selection at explicit native Save are separate from load. Reuse P3 selection rules without changing qualified P3 transport behavior. Reject missing/duplicate/unknown/foreign current COM occupancy before persistence; a moved selected identity must not follow its former COM occupied by another device. No inventory during blocked native Start. No queue, automatic native fallback, hardware permission from legacy identity or production hardware timing claim.

### S5 — Frozen Start context and unchanged Simulation
> Preserve existing zero-argument transport-factory injection through a distinct
> Start-context composition path carrying the already-frozen settings and cancel
> signal. Do not guess callable arity, catch `TypeError` to retry construction, or
> reread a mutable settings store in the worker.

Introduce an explicit immutable Start-context value carrying the settings loaded once at Start and that same cancellation event. Keep existing zero-argument output factories unchanged; named context-aware injection is a distinct path. No worker-side settings reload, arity guessing or TypeError retry. Test mutation of the store after Start, cancel identity, factory failures, Simulation retry/cleanup/Stop/Exit and both simulated orientations. Actual native factory/composition and truthful native lifecycle remain P5; P4 rejects persisted native mode before resource creation.

### S6 — Verification and bounded delivery
> **Rollback:** return explicitly to Simulation using approved configuration recovery;
> keep original bytes available for the older binary.

> Preserve every
> existing command sharing changed code, including differential comparison against
> the prior source.

Use behavioral RED/GREEN through public APIs; assert messages, exits/streams when applicable, persistent bytes, counters and absence of forbidden effects for rejection. Cover required examples/boundaries/errors and previous behavior sharing edited code. Compare prior `b39ace5` and candidate public forms in parent-owned isolated copies, not committed Git-history tests. Full regression, applicable actual Windows source/frozen proof and one independent final verifier cover risk items 1 (configuration data), 3 (shared contracts), 4 (Start/Save/cancel) and 5 if packaging/CI changes are needed. Actual RDD mode remains user-owned; no review approval invented. Passive documentation uses structural verification, not fabricated RED. No physical hardware test or production/FPS claim. Record failed/skipped/pending proof honestly; no blind retry or extra verification framework.

## Tasks

- T0 [S1–S6] route: parent inline; status: done; commit: `9e39bf23c5fd0320e26519e33b6abc3eb59ae2b4` — Settle owner boundary, chained baseline, schema/migration/recovery contracts, isolated state and feature tracking. Risk: none (planning only).
- T1 [S1–S4] route: parent inline dependent unit; status: in_progress; commit: pending — Strict schema/atomic migration/export/restore APIs, passive legacy preservation and early native Start guard with tests/docs. Risk: items 1/3 (configuration format/persistence); do not expose unsafe native fallback in an intermediate slice.
- T2 [S1,S4,S5] route: parent inline dependent unit; status: pending; commit: pending — Stopped transaction/selection admission, frozen Start-context injection and existing tray field round-trip with tests/docs; no selector/native factory. Risk: items 3/4 (shared Save/Start contracts).
- T3 [S1–S6] route: parent checks + one independent verifier; status: pending; commit: pending — Differential/full regression, applicable Windows proof, source/artifact readback if built, final independent verdict, documentation and closure. Risk: items 1/3/4, item 5 only if touched.

## Log

L1 — Original request, verbatim: `continúa entonces con P4`.
L2 — Parent asked one product-boundary question because P4 configuration and P5 selector UI overlap. Owner selected exact label `Contratos/API en P4; selector en P5 — recomendado`, token `p4_contracts_only`. Native Start stays blocked in both offered options; no further user design decision is open. Field/profile/backup names are implementation decisions, not delegated to the owner.
L3 — Read-only mapper mvi8m0lw-t-43yr found current tray has only URL/read-only identity, and Save reconstructs Settings losing future fields; parent spotchecked tray298–350. Coordinator already locks stopped Save/Start and passes one loaded settings object into worker; preserve its zero-argument output factory via separate context seam. Native errors cannot flow through existing generic simulated retry. Map used file-read fallback after CodeGraph rejected non-Git parent cwd; no source/tests/network/hardware effects.
L4 — Created `feat/native-usb-settings` from clean exact P3 closure `b39ace59da7084c2f2300f24558e38386902dd7e`, not fresh main or an implicit P3 merge. P3 source8841770/qualified artifact and accepted earlier branches remain unchanged. Created ignored0700build/p4-state/{home,tmp,cache,config,data,state}. Parent cwd is not Git; all commands explicitly cd project. No outside temp grants are reused.
L5 — Large because migration/rollback semantics, dependent contracts and native/external verification must remain resumable beyond a diff. Units are dependent, so no parallel writers; inline unless runtime context backstop fires. Preserve feature-branch-chain preference and cohesive risk-separated commits, tests/docs with behavior. Owner authorized only P4, not release/main integration or application hardware output. Source push/CI follows repository and existing standing-permission policy; this request invents no new delivery grant.

L6 — T0 contract committed9e39bf23c5fd0320e26519e33b6abc3eb59ae2b4 after branch/state/spec validation and diff-check. Feature document/mirror3139 created before source writes; four visible tasks reconcile the document. T0done, T1in_progress starts public behavioral RED tests; no P4 source changes or native permission yet.

L7 — Plan reviewed on owner reminder. T0done at9e39bf2; T1in_progress, not done. New public tests RED11/0.021sexit1 (3unknown-overwrite behavioral failures and10missing/newAPI errors); initial combined GREEN19/0.079sexit0 (8existing+11new). Implemented strict schema2, passive schema1, explicit migration/backup/export/restore, unknown/future preservation and pre-resource nativeStartguard. Existing unsupported-version tests now use3 instead of newly supported2; message updated for1/2. No sourcecommit/fullregression/differential/native/finalverifier proof yet. T1self-review still must cover exact native-profile types, validated byte-snapshot/error handling and transaction failure boundaries before any done/commit claim. T2stopped Coordinator transactions/context/selection/tray field preservation remains pending; T3allseam/full/differential/nativeapplicable/independent closure pending. No new selector, nativecomposition orP5/P6; noUSB.

L8 — Owner requested plan review; reconciled T0done/T1in_progress/T2–T3pending. Self-review behavioralRED3/0.008sexit1 (profile duck-type admitted, external unknown edit after backup overwritten, PermissionError leaked). Fixed exactnative-profiletype, singlevalidatedrawsnapshot, sanitizedreaderrors and observed-change rejection before replacement; not an OS compare-and-swap guarantee for arbitrary external writers. CombinedGREEN35/0.143sexit0:22settings+13existinglifecycle, no skips. T1isnotdone: API docs, fullregression, relevant differential and cohesive sourcecommit still pending. T2Coordinatorstoppedtransaction/context/selection/traypreservation not implemented merely because T1 has earlynativeStartguard. T3P4full/nativeapplicable/finalindependent/closure not observed; P3proofdoesnotsubstitute. No nativehardware/selector/P5/P6 orpublishing.

L9 — Owner requested plan review. Updated T1 evidence: full local job35GREEN216/24.571sexit0,212passed+4expected Windows-only skips; focused35PASS remains. API guide docs/usb-settings.md and current-plan authorization notes now written, but documentation structural check not yet executed. Disposable build/p4-state/differential_t1.py has been prepared for10public cases plus actualold-reader recovery; it has NOT run and is not PASS evidence. T1 remains in_progress until differential/docs/unitcommit. T2 new stopped/context/selection/tray contracts still absent; existing lifecyclePASS is regression, not proof of those new contracts. T3 final post-T2/full/differential/Windowsapplicable/uniqueindependent/closure remains pending. No source or artifact qualification claim for P4, no P5/P6/actualUSB or new publication.

L10 — T1 checks observed: focused35/0.143sexit0; full216/24.571sexit0 (212PASS+4Windows-onlyskips); disposable differential10casesPASS (6exact/4intentional schema2/version-message/unknown-preservation/nativeStart changes). Actual prior b39ace5 SettingsStore rejects schema2, then accepts byte-exact restoredschema1. Receipt build/p4-state/differential-t1.json. API docs and authorization notes updated;18local link targets and diff-checkPASS. T1cohesive source unit includes schema/store/atomic backup/export/restore, mandatory earlynativeStart rejection and all tests/docs (roughly600changedlines); keep transaction safety/tests together rather than size-only splitting. T1notyetdone until sourcecommit; P4native/finalindependent remains T3. T2next, dependent.

L11 — ASSESS over staged7paths/566changedlines: nativeRiskmedium, explicititem1 escalatedhigh, independentVerifiertrue for finalP4. reviewDuefalse/under_budget; no native review START. Its rddLineon does not override freshly observed globaloff. Owner requested plan review; T1checks complete and commit is the only remaining T1step, T2notstarted, T3finalP4proofpending. No new check is invented from native tier; keep one final independent verification after dependent implementation.
