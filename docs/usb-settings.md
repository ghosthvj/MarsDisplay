# P4 output configuration contracts

**P4 is qualified at `91e20904cb5f729c520a6fd6799e69087a0cccc6`.**
This stage is API/contracts only; the selector and native composition remain P5. The GUI has no new mode/profile/device controls.
The application still starts stopped, defaults to Simulation and rejects saved
native mode before creating a capture worker or transport. It never substitutes
Simulation for an explicitly native configuration.

Track implementation and proof in [the P4 ledger](../odd/tasks/native-usb-settings.md).
[P3 helper qualification](usb-helper.md) is separate; the new P4 evidence is below.

## Two strict formats

Schema 1 keeps exactly its existing keys and ordinary serialization:

```json
{"schema_version": 1, "mars_url": "https://mars.example", "device_identity": null}
```

It always means simulated output, including when an old identity is present.
Loading does not rewrite, migrate, enumerate, open a port or start a helper.
`Settings(url, identity)` still constructs schema 1. The value remains frozen.

Schema 2 explicitly adds both output fields, including for Simulation:

```json
{
  "schema_version": 2,
  "mars_url": "https://mars.example",
  "device_identity": null,
  "output_mode": "simulated",
  "native_profile": null
}
```

`output_mode` is exactly `simulated` or `native`. Simulation requires null profile;
a passive legacy identity is permitted. Native requires string profile
`tus35-portrait-v1` and exact opaque identity `usb:1a86:5722:USB35INCHIPSV2`.
COM is never persisted. Missing/unknown/duplicate keys, unsupported versions,
invalid combinations/types and unsafe URLs are rejected without repairing bytes.
Static settings validity is not hardware permission or proof of current selection.

## Explicit incompatible migration

An old binary rejects schema 2. Trusted callers must acknowledge that fact and
preserve old-readable data before replacing configuration. The low-level store
APIs are not lifecycle authority: application operations must pass through the
Coordinator's stopped-only transaction admission. Save, migration, export and
restore share Start's lock and reject active, stopping or exiting state.
Do not use raw store methods to bypass an application or its instance lock.

```python
store.migrate_to_v2(
    Settings("https://mars.example", schema_version=2),
    acknowledge_legacy_incompatibility=True,
)
```

The target must already be validated schema 2. Acknowledgement must be literal
`True`, not a truthy number/string. The exact valid original schema-1 bytes are
preserved at `store.schema1_backup_path` (`settings.json.schema1-backup.json` for
the default basename). Without an original, a validated schema-1 equivalent is
preserved first. A conflicting backup is never overwritten. Backup publication or
main replacement failure never intentionally replaces the previous configuration.
An already-published valid backup may remain when the main replacement fails.

Ordinary `save()` does not migrate, downgrade or erase unknown/future fields.
Schema-2 edits require a valid preserved schema-1 backup. Explicit repair of invalid
values in a known schema-1 shape remains supported; unknown/malformed shapes are
not silently erased. Loading never repairs either form.

Migration/export use one validated byte snapshot. Migration/recovery reject an
observed configuration change before replacement; this is not an OS-level atomic
compare-and-swap against arbitrary third-party writers. Serialize application
operations through the Coordinator and keep external editors closed.

## Export and recovery

- `store.export_schema1(destination)` exclusively publishes an old-readable export;
  it never overwrites an existing destination. Schema 1 exports exact bytes;
  schema 2 exports explicit Simulation-compatible values with passive identity.
- `store.restore_schema1()` explicitly restores the validated preserved backup.
  Unknown/invalid current configuration or an invalid backup is not erased.
- No automatic downgrade, backup deletion, settings-directory scan or hardware
  reset is performed. Keep the original backup for the older binary.

## Coordinator and Start-context API

Use these trusted, explicit operations while stopped:

- `coordinator.save_settings(value)` edits without changing schema version.
- `coordinator.migrate_settings(value, acknowledge_legacy_incompatibility=True)`
  preserves schema 1 before incompatible migration.
- `coordinator.export_schema1_settings(destination)` and
  `coordinator.restore_schema1_settings()` perform explicit recovery operations.

An explicit native Save/migration passively resolves the current unique identity
and COM occupancy using the unchanged P3 selection rule. Missing/duplicate/unknown
or competing current-COM observations reject before persistence. A device moved
to COM8 is not followed to its old COM5 when another device occupies COM5.
Loading, simulated Save, native Start rejection and recovery never enumerate.
No port is opened by these configuration operations.

Existing zero-argument output injection remains:
`Coordinator(store, source_factory, transport_factory)`. The distinct named path is
`Coordinator(store, source_factory, transport_context_factory=context_factory)`;
passing both paths or neither is rejected before resources are created.
`context_factory(context)` receives one immutable `StartContext` whose `settings`
were loaded once at Start and whose `cancel` is that same Start event. Worker/retry
code never reloads settings or guesses callable arity. There is no TypeError-based
fallback to another signature; ordinary simulated retry policy remains unchanged.
Application composition still uses its existing Simulation factory, not USB.

The existing URL editor preserves loaded schema/output/profile/identity fields via
validated replacement. No native picker, migration checkbox or rollback UI has
been added. Native configuration remains an API capability, not a GUI opt-in.

The existing default settings path stays `%LOCALAPPDATA%\MarsDisplay\settings.json`.
Errors contain fixed actionable text, not supplied URLs, identities or paths.
In the qualified P4 build, stored native mode was blocked unconditionally.
P5's working native composition now requires the named context path; a legacy
zero-argument-only Coordinator rejects native mode with:

> Native output requires an explicit Start-context factory; no fallback was started.

This is composition admission, not a connection failure or fallback trigger.
P4 itself did not include a native GUI selector; P5 runtime/UI work is tracked in
[the runtime contract](usb-runtime.md), not qualified by the P4 evidence below. Production native lifecycle, truthful output
states, Stop/Exit semantics and physical/performance qualification remain P5/P6.

## Verified P4 evidence and limits

[Windows run 39629193023](https://github.com/ghosthvj/MarsDisplay/actions/runs/39629193023)
qualified exact source `91e20904cb5f729c520a6fd6799e69087a0cccc6`:
227 source tests / 64.053s, **zero skips**, followed by the actual windowed build,
existing private-worker smoke, source/native/material qualification and upload.
This is not a GUI native-output opt-in or new hardware acceptance.

| Evidence | Observed result |
|---|---|
| Final local regression | 227 tests: 223 passed, four Windows-only skips; 24.890s, exit 0 |
| Schema/API differential | Ten cases: six exact/four intended; actual prior reader rejects schema 2 and accepts byte-exact restoration |
| Lifecycle/tray differential | Eleven cases: six exact/five intended; legacy zero-argument Simulation, Stop, landscape and native-Start rejection unchanged |
| Independent P4 verification | S1–S6 met, no blockers; 63 focused tests / 1.776s, all passed, zero skips |
| Independent recovery | Real old-reader subprocesses accept original/backup/export/restoration, reject schema 2, and never rewrite bytes; CRLF formatting preserved |
| Parent spot check | Same 63 focused tests / 2.210s, all passed, zero skips |
| Parent and independent artifact readback | 1,246 payload hashes, 350 source files, 69 AMD64/PE32+ binaries; actual EXE GUI subsystem 2; 27 Qt plus six supplemental bindings and 209 material hashes |

The immutable ZIP is 205,667,244 bytes, SHA256
`c5edd037a453cc1e8171f10b377250b42d3707f65f0e59e35a272f68fb509777`.
Of 350 source files, 346 match exact Git Windows checkout bytes and four are
explicitly validated SDK metadata records. Raw legal bytes remain protected.
Mechanical/source binding is not legal certification. Neither parent nor verifier
executed Windows code or accessed USB on Linux; bound native evidence supplies
Windows proof. Offscreen Qt warnings were retained and did not indicate failure.

Historical pending wording inside the source-bound ZIP is superseded here; the
qualified ZIP is not rewritten. Initial schema/unknown-preservation and GUI/context
RED failures and their fixes remain recorded in the task ledger. No required proof
remains open. No selector, native factory, application USB, P5/P6, physical/FPS,
hotplug or production-budget claim is included. P0–P3 artifacts remain unchanged.
