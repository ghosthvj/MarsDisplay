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

- T0 [S1–S6] route: parent inline; status: in_progress; commit: pending — Settle owner boundary, chained baseline, schema/migration/recovery contracts, isolated state and feature tracking. Risk: none (planning only).
- T1 [S1–S4] route: parent inline dependent unit; status: pending; commit: pending — Strict schema/atomic migration/export/restore APIs, passive legacy preservation and early native Start guard with tests/docs. Risk: items 1/3 (configuration format/persistence); do not expose unsafe native fallback in an intermediate slice.
- T2 [S1,S4,S5] route: parent inline dependent unit; status: pending; commit: pending — Stopped transaction/selection admission, frozen Start-context injection and existing tray field round-trip with tests/docs; no selector/native factory. Risk: items 3/4 (shared Save/Start contracts).
- T3 [S1–S6] route: parent checks + one independent verifier; status: pending; commit: pending — Differential/full regression, applicable Windows proof, source/artifact readback if built, final independent verdict, documentation and closure. Risk: items 1/3/4, item 5 only if touched.

## Log

L1 — Original request, verbatim: `continúa entonces con P4`.
L2 — Parent asked one product-boundary question because P4 configuration and P5 selector UI overlap. Owner selected exact label `Contratos/API en P4; selector en P5 — recomendado`, token `p4_contracts_only`. Native Start stays blocked in both offered options; no further user design decision is open. Field/profile/backup names are implementation decisions, not delegated to the owner.
L3 — Read-only mapper mvi8m0lw-t-43yr found current tray has only URL/read-only identity, and Save reconstructs Settings losing future fields; parent spotchecked tray298–350. Coordinator already locks stopped Save/Start and passes one loaded settings object into worker; preserve its zero-argument output factory via separate context seam. Native errors cannot flow through existing generic simulated retry. Map used file-read fallback after CodeGraph rejected non-Git parent cwd; no source/tests/network/hardware effects.
L4 — Created `feat/native-usb-settings` from clean exact P3 closure `b39ace59da7084c2f2300f24558e38386902dd7e`, not fresh main or an implicit P3 merge. P3 source8841770/qualified artifact and accepted earlier branches remain unchanged. Created ignored0700build/p4-state/{home,tmp,cache,config,data,state}. Parent cwd is not Git; all commands explicitly cd project. No outside temp grants are reused.
L5 — Large because migration/rollback semantics, dependent contracts and native/external verification must remain resumable beyond a diff. Units are dependent, so no parallel writers; inline unless runtime context backstop fires. Preserve feature-branch-chain preference and cohesive risk-separated commits, tests/docs with behavior. Owner authorized only P4, not release/main integration or application hardware output. Source push/CI follows repository and existing standing-permission policy; this request invents no new delivery grant.
