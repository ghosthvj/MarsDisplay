# Native portable build source — Windows proof pending

The native builder, spec, isolated executable smoke and workflow **source** now
exist. No Windows executable/ZIP has been delivered or qualified. T5 remains in
progress. Owner-authorized feature-branch CI has started. After the first run's
source-test failure, run **39026203729 passed Windows source tests**, then failed
before compilation with `Missing browser license material: winldd`. Its artifact
list was empty: no diagnostic or binary ZIP existed. Later run **39029908479**
on `082047b` passed source tests and completed native PyInstaller EXE + COLLECT,
then failed runtime `read_tree` validation with
`Duplicate path or empty/non-byte material`, before smoke/report/ZIP. This proves
Windows frozen assembly, not app execution or a usable prototype. The generic
error does not identify which Windows file failed first. Linux SDK/EXE fixtures
remain synthetic, never native execution proof.

Run [39032168531](https://github.com/ghosthvj/MarsDisplay/actions/runs/39032168531)
subsequently passed runtime-tree validation and produced a real **UNQUALIFIED**
JSON inventory of 136 native files. Smoke failed on the incorrect four-value
Qt lock-info unpack. After correcting that binding contract, broad-bundle run
[39033278476](https://github.com/ghosthvj/MarsDisplay/actions/runs/39033278476)
**passed native startup and binary smoke**, then failed missing native
qualification. Its UNQUALIFIED diagnostic is not a license approval or ZIP and
cannot satisfy the qualification schema. The later minimized run
**39036811563 / ad12837** also passed EXE/COLLECT and packaged smoke, failing only
for missing reviewed native qualification. Its measured inventory fell from
136 to 123 native files (Qt-prefix 46 to 33), with the four selected plugins and
nine dependent Qt DLLs removed, none added. This is runtime evidence, not a
qualified ZIP; T5 remains in progress.

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

## Minimal Qt runtime — stage one verified, qualification pending

The owner selected **Minimal app-required runtime**. The app uses raster
Core/Gui/Widgets tray drawing and Playwright Chromium rendering, not Qt PDF/SVG
file icons, QML UI or virtual-keyboard features. No GUI feature or user parameter
is changed. Stage one suppresses only these optional plugin roots:

| QtGui plugin family | Omitted Windows root basenames |
| --- | --- |
| `imageformats` | `qpdf.dll`, `qsvg.dll` |
| `iconengines` | `qsvgicon.dll` |
| `platforminputcontexts` | `qtvirtualkeyboardplugin.dll` |

`Analysis.hookspath` selects the repository-local `hook-PySide6.QtGui.py`.
It loads the pure `qt_plugins.select_plugin_roots` policy by hook-relative path,
initializes pinned PyInstaller 6.22.3 library info, and temporarily wraps only
that instance's `collect_plugins`. The stock collector still performs plugin
release/debug and dependency validation and normal QtGui module traversal.
Kept tuples/order, hidden imports and data are preserved. A `finally` restores
the exact previous instance override or removes the temporary attribute to
restore normal descriptor binding, including on failure. Installed SDK files,
class methods and other hooks are not changed.

Selection happens **before Analysis native dependency closure**, not by deleting
Qt DLLs after Analysis. Other families/plugins, qwindows, styles, base binding
hooks, Core/Widgets/Network/SSL, Mesa/ANGLE/ICU and CRT support remain delegated
to their defaults. The existing post-Analysis DATA selection below is unchanged.
There is no invented hooksconfig key, whole-family suppression or license bypass.

Run39036811563 verified removal of the four roots and Qt OpenGL/Pdf/Qml/
QmlMeta/QmlModels/QmlWorkerScript/Quick/Svg/VirtualKeyboard DLLs. Core/Gui/Network/
Widgets, required plugins, Mesa and CRT remained; packaged smoke passed. This is
not normal Exit/Windows 11 acceptance or native-license approval. The diagnostic
facts below still need actual Windows measurement before correcting the
component-version/provenance model. No qualification gate is relaxed here.

## Frozen runtime selection, not relaxed validation

`runtime_files.select_runtime_data(entries)` is a pure DATA TOC filter loaded by
absolute spec-relative file path, without a `packaging` package/import-path
change. The spec applies it to `a.datas` **after Analysis and before COLLECT**:
Playwright's pinned hooks also add copies, so filtering only the initial
`collect_data_files` list is insufficient.

Only these installer/cache destinations beneath
`playwright/driver/package/.local-browsers/` are excluded:

- The `.links/` subtree, containing build-install SDK references.
- `INSTALLATION_COMPLETE` and `DEPENDENCIES_VALIDATED` directly beneath numeric
  revision browser/tool directories, such as `chromium_headless_shell-1248`,
  `ffmpeg-1013` and `winldd-1007`.

The exact package-root `py.typed` DATA file is also excluded for **playwright,
PySide6, shiboken6, PIL, pyee and greenlet** only, whether empty or nonempty.
These PEP 561 markers serve static type checkers, not the frozen application.
Package/file spelling is compared case-insensitively for the Windows target;
unknown packages, nested/deeper `py.typed` files and non-DATA entries are retained.
This is not a generic filename glob or an empty-file exception.

Windows TOC separators are normalized for comparison only. Original kept tuples,
order, bytes and SDK files are unchanged; Node, driver, browser/FFmpeg/PrintDeps,
registry, Qt resources and all legal/real data remain intact. Similarly named
files elsewhere or deeper in a resource tree are not excluded. Arbitrary empty
files, empty legal texts and empty required executables still fail the unchanged
payload reader; no empty-file bypass or blanket removal is added.

The pinned local SDK contains compatible empty installer flags, `.links`
references and an empty `playwright/py.typed`; structural copy tests reproduce
the same reader error and cover nonempty root markers too. This is not
identification of the first failing Windows file. If Playwright performs host
validation, a missing validation cache may be recreated after validation. No
installer, downloader, automatic update or new app control is introduced; the
app uses launch, and settings remain under `%LOCALAPPDATA%\\MarsDisplay`.

## Native material is a real, unresolved gate

The broad Windows inventory has been inspected, but component attribution and
the component-version model remain incomplete. Binding license texts and the
56 registered [official source inputs](../third_party/license-material/README.md)
are not complete native/plugin attribution. Missing/unmapped native material
still fails before distribution. There is no legal-certification claim.

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

The current gate incorrectly requires every listed component version to match
`qVersion()`, including non-Qt CRT components. Correcting that model/provenance
is the **next unit**, not part of this plugin policy. Do not fabricate Qt versions
for other components or supply a pass-through manifest. Binary/hash, license
path/hash and source checks remain fail-closed; unknown or extra mappings fail. The complete manifest/texts travel in `notices/native/`. This is
byte/provenance binding, not an automatic legal auditor: the operator must
actually establish native third-party attribution and corresponding-source
sufficiency. Other SDK/native obligations must also be reviewed before delivery.

## Exact winldd notices, not a browser exemption

Windows Playwright installs the hermetic dependency tool
`package/.local-browsers/winldd-1007/PrintDeps.exe`. The pinned Python package
1.64.0 embeds **playwright-core 1.64.0-beta-1791568591000**, whose official npm
source gitHead is `1b2924712024804936dbcfe9fabaa655d52325e5`, not the stable
JavaScript 1.64.0 tag. Do not infer source identity from the Python pin alone.

`collect_vendor(driver, *, material_root=None)` retains installed local tool
legal texts first. Only their absence permits the exact core/revision/source
mapping: verified root LICENSE/NOTICE, complete PrintDeps.cpp retaining Julien
Waechter's MIT text **and** Microsoft's Apache-2.0 header, and BUILD_NUMBER1007.
The build-number file is provenance, never labeled a license. All four raw files,
commit-pinned URLs and hashes travel with notices/source. Their supplementary
registry mappings stay `packages: []`, never whole-Playwright fallback coverage.
The registered set now contains 56 raw inputs plus registry/README (58 shared
files). The original 52 raw inputs are unchanged.

Missing/unknown/mismatched core, tool revision, executable or immutable material
fails closed. Empty, broken, unsafe or altered installed texts cannot select
fallback. `material_root` is a local fixture seam, not a CLI option, downloader
or bypass. A declared winldd inventory must contain exactly one numeric revision
with its exact `PrintDeps.exe`; stale README-only paths do not count. Chromium
headless shell and FFmpeg remain mandatory. This source correction supplies no
native Qt qualification, packaged execution/smoke or legal certification.

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

## Per-file native evidence — diagnostic facts only

The optional additive `native_evidence` map is computed **only while retaining a
failure diagnostic**, from the same immutable runtime bytes as `native_files`.
Schema-v1, original native hash map, source/version fields, failure phase and
smoke status stay unchanged. No evidence is supplied to qualification or final
publication, and no native.json, approval flag or new CLI option is created.

Each native path carries its matching SHA256 plus:

- `pe`: fixed status `measured`, `absent`, `unknown` or `unavailable`. Measured
  `file_version` and `product_version` come from numeric unsigned DWORDs in
  VS_FIXEDFILEINFO, as four decimal components. Missing/malformed resources or
  an unavailable/unexpected parser never substitute Qt/package/global versions.
- `origins`: `matched` or explicitly `unknown`, RECORD availability and sorted
  matching distribution name/version/relative RECORD path/digest facts. Only
  declared dependency/build-dependency identities with exact installed versions
  and decoded RECORD SHA256 equal to runtime SHA256 are eligible. All genuine
  matches may remain; a basename is never origin evidence.

The helper lazily uses the existing Windows SDK's **pefile 2024.8.26**, without
adding a dependency for Linux. The inspected [official tagged source](https://github.com/erocarrera/pefile/blob/v2024.8.26/pefile.py)
confirms `PE(data=..., fast_load=True)`, resource-only `parse_data_directories`,
a VS_FIXEDFILEINFO list with `Signature`, `FileVersionMS/LS` and
`ProductVersionMS/LS`, and `close()`. No LoadLibrary or executable is invoked.
All arbitrary resource strings, including CompanyName/ProductName/copyright,
are deliberately omitted; no vendor label or licensing identity is inferred.

Origins use only importlib.metadata distribution/RECORD metadata, never SDK
binary reads or path lookup/resolution. Relative paths use the existing safe-path
validator; no absolute paths, parent traversal, environment, direct_url, URLs
or raw exceptions are exported. RECORD paths cannot cause symlink traversal
because they are never followed. A hash association proves only installed
owner association—not upstream supplier, source provenance or license coverage.

Supplemental collection failure emits hash-bound `status: unavailable` entries
and preserves the original build failure and prior files. Unknown facts are not
qualification evidence. Actual facts for the 123-file Windows candidate require
the next parent-controlled CI run; synthetic source tests establish no native
version/origin proof. The current Qt-version-for-CRT gate remains unchanged.

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
The pinned PySide6 API returns `(pid, hostname, appname)` from
`QLockFile.getLockInfo()`—not the C++ Boolean plus output values. A real binding
regression checks that contract; missing/nonpositive/foreign PID information
cannot reach GUI readiness checks, and the lock must still be held.
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
are unchanged. The second authorized run
[39026203729](https://github.com/ghosthvj/MarsDisplay/actions/runs/39026203729)
passed source tests but stopped during precompile vendor collection on winldd's
missing legal material; artifacts were `[]`, despite the missing-file upload
step succeeding. The bounded source correction above addresses that exact
notice gap, not native Qt qualification. Run
[39029908479](https://github.com/ghosthvj/MarsDisplay/actions/runs/39029908479)
then passed source tests and prebuild winldd collection, and completed Windows
EXE/one-folder assembly. Runtime validation failed before smoke/diagnostic, so
again no artifact was uploaded. Subsequent runtime DATA and lock-info fixes led
to the broad native smoke pass in39033278476 described above, but native
qualification and ZIP delivery remain absent. The new minimal candidate has
not been built or smoked; it requires fresh parent-controlled Windows evidence.
Owner authorization covers T5 branch pushes/CI and seven-day test artifacts;
none was executed by this correction worker. Server 2025 is not Windows 11
acceptance.

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
