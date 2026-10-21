# P4 output configuration contracts

**Under implementation, not qualified.** P4 is API/contracts only; the selector and
native composition remain P5. The GUI has no new mode/profile/device controls.
The application still starts stopped, defaults to Simulation and rejects saved
native mode before creating a capture worker or transport. It never substitutes
Simulation for an explicitly native configuration.

Track implementation and proof in [the P4 ledger](../odd/tasks/native-usb-settings.md).
[P3 helper qualification](usb-helper.md) does not qualify these new contracts.

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
A stored native mode reports:

> Native output is configured but is not enabled in this build. Select Simulation explicitly.

Do not interpret this as a connection failure, retry it or enable a fallback.
There is no native GUI selector in P4. Production native lifecycle, truthful output
states, Stop/Exit semantics and physical/performance qualification remain P5/P6.
