# Native portable build source — Windows proof pending

The native builder, spec, isolated executable smoke and workflow **source** now
exist. No Windows executable/ZIP has been delivered or qualified. T5 remains in
progress. Owner-authorized feature-branch CI has started; its first run failed
in source integration tests before native compilation. No qualified artifact
exists. Linux SDK/EXE fixtures are synthetic, never runnable Windows proof.

## Developer commands (native Windows x64 only)

Use Python **3.13.x**, the exact `pyproject.toml` pins and an interactive session
with a real system tray. These commands describe the future authorized Windows
run, not commands executed during Linux development:

```powershell
python -m pip install '.[build]'
$env:PLAYWRIGHT_BROWSERS_PATH = '0'
python -m playwright install chromium --only-shell
python packaging/build_portable.py --help
python packaging/build_portable.py
# Optional repeat check of an already unpacked built folder:
python packaging/smoke.py dist/MarsDisplay
```

The builder has no output/version override, downloader, app control flag or HTTP
endpoint. It rejects unsupported hosts before SDK reads, processes or directory
creation, and refuses existing folder/ZIP/checksum destinations. Move prior
artifacts yourself to a safe location; the builder never overwrites them.

| Phase | Boundary |
| --- | --- |
| Inspect | Validate installed direct/build/backend pins; collect real dependency/vendor texts, CPython `LICENSE.txt` and PyInstaller `COPYING.txt` including its bootloader exception. |
| Compile | Pinned PyInstaller one-folder `MarsDisplay`, `entrypoint.py`, `console=False`, `upx=False`; used Qt hooks only, no collect-all Qt/WebEngine/Pdf or other bindings. |
| Inspect stage / smoke | Read the unpacked tree, require exact runtime layout, then run that EXE and its Node/browser/FFmpeg version commands with deadlines and isolated user/temp paths. |
| Qualify | Only after smoke, require the genuine native material mapping below. Measured-stage failures retain unqualified diagnostic metadata before owned staging is cleaned. |
| Publish | Only after all checks, call the existing `payload.assemble` publisher once for folder + ZIP + SHA256 sidecar. |

Compiler work/cache/temp and smoke state are owned temporary directories beneath
repository `build/`; publication scratch is beneath `dist/`. Caught failures clean
owned staging, never user data. Measurable-stage failures retain only a uniquely
named `build/unqualified-native-*.json` diagnostic and print that relative path;
prior reports and artifacts are never overwritten. Successful artifacts are
`dist/MarsDisplay-<version>-Windows-x64.zip` and `.zip.sha256`, plus the unpacked
`dist/MarsDisplay/`. Abrupt termination can leave partial output; a later build
refuses it instead of repairing or overwriting it.

## Native material is a real, unresolved gate

The installed Windows Qt payload has **not** been inspected. Binding license
texts and the 52 immutable [official source inputs](../third_party/license-material/README.md)
are not complete native/plugin attribution. Missing/unmapped native material
fails before distribution. There is no legal-certification claim.

The default builder requires reviewed local inputs at
`build/native-material/native.json`, plus the referenced genuine native license
texts in that directory. No fabricated/pass-through manifest is supplied. The
workflow therefore cannot currently produce a qualified ZIP. A future explicitly
authorized Windows diagnostic run can compile and smoke the owned internal stage,
then remain **red** for missing native mapping while retaining useful metadata.
Native material investigation and an evidence-provisioning decision are still
needed before a qualified build can succeed. Do not insert synthetic material
or treat a diagnostic upload as distribution clearance.

Manifest schema (all paths relative, checked by `payload.read_tree`):

- `qualification`: nonempty explanation of the review and its limits.
- `components`: exactly one record for **every** bundled `.dll`/`.pyd` beneath
  `_internal/PySide6/`, including binding extensions and platform/image plugins.
  Each record has `path`, exact binary `sha256`, `component`, actual Qt `version`,
  public HTTPS `sources`, and nonempty `licenses` pointing to the genuine texts.
- `license_sha256`: mapping of those relative text paths to measured SHA256.

All component versions must match measured `qVersion()`. Every binary/hash,
license path/hash and source reference must validate; unknown or extra component
mappings fail. The complete manifest/texts travel in `notices/native/`. This is
byte/provenance binding, not an automatic legal auditor: the operator must
actually establish native third-party attribution and corresponding-source
sufficiency. Other SDK/native obligations must also be reviewed before delivery.

## Unqualified diagnostics, not approval evidence

`build/unqualified-native-<unique>.json` uses the distinct
`marsdisplay-unqualified-native-v1` schema with `status: UNQUALIFIED`. It is
metadata only, not a `collect_native` input, native-license mapping or claim of
readiness. It records:

- Source commit and hashes of the actual selected source snapshot; no source bytes.
- Selected installed Python/PyInstaller/dependency/Qt versions and inspected
  browser registry revisions/versions. Node is included after successful packaged
  version/startup smoke; unavailable measurements are not invented.
- Every measured stage `.dll`, `.pyd` and `.exe` relative path with SHA256,
  including files outside PySide6.
- A fixed failure phase and honest smoke status: `passed`,
  `failed_or_unavailable`, or `not_run` when layout validation prevented smoke.
  Passed smoke does **not** qualify native notices or prove Windows 11 acceptance.

The allowlisted report contains no environment dump, absolute SDK/private-state
paths, source archives, raw exception strings or dependency URLs. Smoke failure
is recorded before propagating failure, never silently promoted to ready. SDK or
compilation failure before a measurable stage may produce **no report**. No
fictitious inventory is emitted. Final publication still requires successful
smoke, valid qualification and unchanged source; the existing publisher retains
its exclusive-create and owned-rollback rules.

## Packaged smoke is not Windows acceptance

`smoke.check(folder, scratch)` runs only on native Windows x64. It executes the
bundled Node `--version`, exact registry Chromium `--version` (must match declared
browser version), and FFmpeg `-version`. No TLS/sandbox bypass or network URL is
used. `smoke.startup` launches **the unpacked built executable**, not source main.

The child receives an allowlisted OS environment, system-only PATH and isolated
LOCALAPPDATA/APPDATA/HOME/USERPROFILE/TEMP/TMP. External Python/Qt/plugin/browser
overrides cannot mask missing resources. Within 20 seconds it must hold its
per-user QLockFile under its own PID, reach GUI input idle, dispatch bounded
WM_NULL probes through owned windows, and have no visible startup/error dialog.
Process-alive alone is insufficient; absent tray/GUI is failure, never a skip.
It remains unconfigured/stopped, must not create settings, and only this owned
idle process is terminated and waited for (5 seconds). No global taskkill/browser
termination is used. Normal packaged Exit, real tray interaction, LAN capture,
Windows 11 behavior and RAM/CPU measurements remain **T6**.

## Layout, provenance and support APIs

The current pinned Windows registry uses
`chromium_headless_shell-<revision>/chrome-headless-shell-win64/chrome-headless-shell.exe`
and `ffmpeg-<revision>/ffmpeg-win64.exe` beneath
`_internal/playwright/driver/package/.local-browsers/`. Node is
`_internal/playwright/driver/node.exe`; Qt's Windows hook uses
`_internal/PySide6/plugins/platforms/qwindows.dll`. The validator retains the
previously tested exact `headless_shell.exe` and `PySide6/Qt/plugins/` layouts;
no arbitrary prefix/EXE is accepted. Stale-revision regression checks remain.

`inventory.json` contains measured Python/PyInstaller/Qt/Node/browser versions,
installed dependency closure and project source references, native mapping,
source revision, hashes of actual included source (including dirty bytes), and
relative payload hashes. No environment dump, editable `direct_url.json`, task
logs, Git history, credentials, profiles, cookies or `.env` is collected.
Source includes app/tests/fixtures, recipes/spec/smoke, workflow, build metadata,
GPL LICENSE and registry-verified legal inputs. Final ZIP checksum covers inventory.

Standalone modules load by file path, not `packaging/__init__.py` (which would
shadow the installed requirement-parser distribution):

| Helper | Responsibility |
| --- | --- |
| `payload.read_tree` / `collect_source` | Validated runtime tree / explicit corresponding-source allowlist. |
| `payload.collect_license_material` | Exact registered version/hash/commit inputs only. |
| `notices.collect_distributions` | Installed closure with raw texts; absent texts permit exact-version registry fallback, unsafe/broken texts never do. |
| `notices.collect_vendor` | Node, Playwright/inlined sidecars, browser registry and actual installed browser/FFmpeg notices. |
| `payload.assemble` | Sole exclusive folder/ZIP/checksum publisher with owned rollback, path/collision/privacy rules. |
| `entrypoint.run` | Prepare temporary streams before app import; sanitize native startup messages; no permanent extra window. |

## Workflow source and eventual retrieval

`.github/workflows/windows-portable.yml` uses commit-pinned official node24
checkout/setup-python/upload-artifact actions, Windows Server 2025 x64,
Python 3.13, read-only contents, no persisted checkout credentials, a 30-minute
job limit and 7-day artifact retention. Source tests use offscreen Qt; native
build/smoke explicitly remove test-only Qt/Python overrides. On native-step
failure, only `build/unqualified-native-*.json` uploads as the separate
`MarsDisplay-UNQUALIFIED-native-diagnostics` artifact for seven days: no EXE,
DLL, ZIP, source or private profile. If compilation produced no diagnostic, a
missing-file warning does not change the failed build to success. Only total
success permits the existing ZIP/checksum upload, with missing files treated as
error. No secrets, production backend, screenshot service, tag or release is
configured.

Triggers are restricted to push on existing `feat/simulated-companion` and manual
dispatch. GitHub requires the workflow on the default branch for manual dispatch;
a first **explicitly authorized** feature-branch push can bootstrap registration
without unapproved main changes. The first authorized run
[39024652172](https://github.com/ghosthvj/MarsDisplay/actions/runs/39024652172)
installed the Windows SDK/browser but failed a source integration wait before
compilation. The test now scopes cleanup to each orientation and uses a bounded
15-second first/restarted-frame budget with selected-state diagnostics; exact
RGB, request counts and settings checks remain. Production timeouts/retries
are unchanged. A new-commit run is required; this is not a successful build.
Server 2025 is not Windows 11 acceptance.

After a future authorized successful run, download `MarsDisplay-Windows-x64`
from the run's Artifacts before its 7-day expiry. Extract the Actions download
archive to obtain the actual ZIP and checksum, compare the ZIP's SHA256 using
`Get-FileHash -Algorithm SHA256`, then extract the **entire** ZIP. Launch
`MarsDisplay/MarsDisplay.exe`; keep `_internal`, LICENSE, notices, source and
inventory together. No administrator/install step is required. Settings persist
per user at `%LOCALAPPDATA%\MarsDisplay\settings.json`, not beside the EXE;
replacing an extracted folder does not clear settings. The unsigned prototype
may trigger Windows warnings: do not disable security protections. No installer,
service, autostart or updater is provided.
