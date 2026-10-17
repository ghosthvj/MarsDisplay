# Windows portable build and verified delivery

## Verified artifact — T5 complete

[Download MarsDisplay 0.1.1 Windows x64](https://github.com/ghosthvj/MarsDisplay/actions/runs/39055573997/artifacts/12109691322)
from [run39055573997](https://github.com/ghosthvj/MarsDisplay/actions/runs/39055573997), exact source
`5d0de48b4f08c38a33c5027195e18841fe2c86d4`. The artifact contains the
application ZIP and SHA256 sidecar; retention ends **2026-10-24 17:54 UTC**.
This build contains the bounded SPA display-root readiness correction; the
previous 0.1.0 artifact does not.

| Verified evidence | Result |
| --- | --- |
| Native CI | 143 source tests passed in 49.084s, then compile, external profile, startup/binary smoke, genuine-material provisioning, unchanged v2 qualification, source stability and upload passed. |
| Download | 205,550,469-byte ZIP; SHA256 `84769fa48f091323a4d7598fb12358d725c4a2cc6ef6a96fa7f504f75b7a4fc4` matches its sidecar. |
| Content | 1,222 members; all 1,221 file hashes and 325 source hashes verified without executing or extracting Windows code on Linux; browser source/version match the source commit. |
| Native inventory | 69 files; 27 Qt components and 6 supplemental associations bound to notices/evidence; no selected Microsoft DLLs or Qt Mesa. |
| Runtime | Python3.13.16, Qt6.12.0, PyInstaller6.22.3, Node24.21.0, Chromium156.0.8078.4, FFmpeg1013. |
| Source access | Root README.txt points to notices/native/SOURCE-ACCESS.txt; application/build source and original notices are included. |

Exit the old instance, install official VC++ v14 x64 14.51+ manually if missing,
and extract the complete new application ZIP into a separate folder. Do not mix
versions or copy just MarsDisplay.exe. Existing per-user settings persist. Open
the new EXE, check settings and Start explicitly; output remains simulated and no
physical screen is driven. This is unsigned, not an installer or release. Do not
disable security to run it.

The earlier four corrected defects and three missing-input diagnostic runs remain
recorded in the feature ledger. The first qualified artifact was 0.1.0/run39049628794;
0.1.1 addresses the later owner-reported capture bootstrap race. A local monitor
initially failed because unqualified Python was absent; the feature push succeeded
and monitoring attached to the same run. No duplicate workflow or validation bypass
was used.

**T6 remains partial:** owner Windows screenshots show running/ready, live,
non-stale data and increasing frames; the tested ZIP version is not visible.
Normal Stop/Exit, owned-browser cleanup, LAN/recovery and sustained whole-process-
tree CPU/RAM still require owner evidence. A 36.7 MB / 0% process snapshot is not
the aggregate Node/Chromium cost. Windows Server2025 CI and ZIP checks are not
Windows11 acceptance or legal certification. Later documentation-only commits
do not change/rebuild the artifact.

## Selected external-runtime profile

The owner chose **official VC++ as an external prerequisite**, not Microsoft DLL
conveyance. Python, Qt, Chromium, Pillow and other open-source extensions remain
bundled. Install the current official **VC++ v14 x64 14.51+** manually if missing:
https://aka.ms/vc14/vc_redist.x64.exe . The validated build used14.51; older
versions are not promised compatible. Windows11 supplies OS UCRT/API-set DLLs.
MarsDisplay has no installer/downloader, automatic license acceptance or service;
a runtime EULA is not treated as a redistribution grant.

The exact external DLL set is MSVCP140.dll/_1/_2, VCRUNTIME140.dll/_1,
ucrtbase.dll and the api-ms-win-core-*/api-ms-win-crt-* DLL contract families.
Case/separators are normalized, not arbitrary DLL/vendor-name substrings.
The spec temporarily delegates pinned6.22.3 `find_binary_dependencies(binaries,
import_packages, symlink_suppression_patterns)` and `dylib.include_library(path)`.
It selects the **Analysis-owned root list before closure** (stock Analysis retains
that list and extends it with results), then vetoes targeted dependencies while
preserving default traversal and untargeted inclusion/exclusion. Both functions
are restored in `finally`; no SDK file or environment is patched.

The local base PySide6 hook executes the entire stock hook, preserving binding
guards, shiboken/inspect/deprecated imports, ANGLE/ICU and other defaults. Only its
exact optional `_collect_all_or_none(['opengl32sw.dll'])` request is omitted.
The app's default raster/GDI Widgets/tray path does not request software OpenGL;
forced Qt/RHI/OpenGL debug graphics are unsupported by this profile. Chromium
GL/Vulkan/SwiftShader resources and the existing QtGui policy are unchanged.
If independent native edges still require Mesa, it remains in closure and the
final profile assertion **rejects**, never purges, it before smoke/qualification/
publication. The same assertion rejects any known external DLL still present.
This is bounded selection, not a general vendor/license classifier.

The builder copies immutable `packaging/PORTABLE-README.txt` source bytes to the
owned stage's root `README.txt`, exclusively, before hashing/layout/smoke. Both
source and staged copies are inventoried. The source collector also explicitly includes
validated native-source inputs; it never archives the workspace or all third_party.
The delivered artifact's Microsoft-DLL-free/Mesa-free inventory and native smoke
are verified in run39049628794.
Host CI does not prove a clean Windows11 machine has the prerequisite; T6 owns
that acceptance. Build inputs remain mandatory before any future native build.

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
| Inspect | Validate genuine pinned native inputs/policy first, then selected SDK pins/RECORD before processes; collect dependency/vendor texts, CPython `LICENSE.txt` and PyInstaller bootloader exception. |
| Compile | Pinned PyInstaller one-folder `MarsDisplay`, `entrypoint.py`, `console=False`, `upx=False`; used Qt hooks only, no collect-all Qt/WebEngine/Pdf or other bindings. |
| Inspect stage / smoke | Read the unpacked tree, require exact runtime layout, then run that EXE and its Node/browser/FFmpeg version commands with deadlines and isolated user/temp paths. |
| Qualify | After smoke, prepare reviewed policy/material with fresh facts in the owned stage, then call the unchanged v2 gate independently. Measured-stage failures retain unqualified diagnostic metadata before cleanup. |
| Publish | Only after all checks, call the existing `payload.assemble` publisher once for folder + ZIP + SHA256 sidecar. |

Compiler work/cache/temp and smoke state are owned temporary directories beneath
repository `build/`; publication scratch is beneath `dist/`. Caught failures clean
owned staging, never user data. Measurable-stage failures retain only a uniquely
named `build/unqualified-native-*.json` diagnostic and print that relative path;
prior reports and artifacts are never overwritten. Successful artifacts are
`dist/MarsDisplay-<version>-Windows-x64.zip` and `.zip.sha256`, plus the unpacked
`dist/MarsDisplay/`. Abrupt termination can leave partial output; a later build
refuses it instead of repairing or overwriting it.

## Minimal Qt runtime — verified plugin-root selection

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
hooks and Core/Widgets/Network/SSL remain delegated. The later external-runtime
profile above now changes only Microsoft inclusion and the optional Mesa root,
not ANGLE/ICU, consumer code or the original four-root QtGui policy. The existing post-Analysis DATA selection below is unchanged.
There is no invented hooksconfig key, whole-family suppression or license bypass.

Run39036811563 verified removal of the four roots and Qt OpenGL/Pdf/Qml/
QmlMeta/QmlModels/QmlWorkerScript/Quick/Svg/VirtualKeyboard DLLs. Core/Gui/Network/
Widgets, required plugins, Mesa and CRT remained; packaged smoke passed. This is
not normal Exit/Windows 11 acceptance or native-license approval. The diagnostic
facts were subsequently measured in run39038363658/29f18f7: 123 native files,
101 measured PE versions/22 absent, 46 RECORD associations/77 unknown, none
unavailable. Qt PE6.12.0.0 differs from PySide-prefix CRT14.44.35211.0; bindings
and Mesa lack PE versions but have owner6.12.0. Owner version is not Mesa source
release. The explicit v2 model below separates these dimensions. Pinned Qt/PySide/OpenSSL source
inputs and a curated external-profile policy now exist. Mesa is not licensed by
inference: it is omitted only by the selected profile and rejected if still present.

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

## Offline native-source provisioning, then unchanged v2 gate

The default builder requires [pinned primary material and reviewed policy](../third_party/native-material/README.md)
in `third_party/native-material`, not a manual `build/native-material/native.json`.
Missing inputs fail before SDK/process work with:
`Missing verified native sources: third_party/native-material; Windows qualification is pending`.
Present but invalid inputs fail with `Invalid verified native sources or policy`.
No source text is downloaded, normalized or silently replaced. The reader checks
registry/policy trust anchors, every raw SHA256 and git blob identity, immutable
public source URLs, declared LicenseFile references and annotated release tags.

The policy explicitly maps 27 expected Qt-prefix paths to qtbase, qtimageformats
or pyside full module sources. Hashes, PE facts and exact PySide6_Essentials6.12.0
RECORD associations were curated from historical Windows39038363658, not inferred
from basenames. That report is never read by the builder or used as verification.
Preflight requires live selected SDK RECORD associations before compilation.
After profile/layout/smoke, fresh byte/PE/RECORD facts must match every policy item;
only then is v2 material created exclusively in the owned temporary native-material
stage. The unchanged `collect_native` measures again before the sole publisher.
Stale/unknown paths, hashes, owners or PE facts fail; no supplier-approved flag is
filled. Manual older build/native-material files have no authority. Test-only
qualification injection remains explicit and has no public CLI control.

All 204 raw texts/233 origin records, registry, policy, source directions and
supplemental inventory travel in hashed notices and explicit corresponding source.
Full-module notices retain copyrights, conditional QtUsage, versions, patents and
alternative license terms, without claiming all optional features were compiled.
Release references are separate version evidence, never license substitutes.
Supplemental Shiboken's two files and four outer OpenSSL3.5.5/3.5.9 DLLs have their
own exact fresh-fact/source inventory, outside the unchanged Qt gate. Other runtime
obligations remain covered by existing CPython generated Windows LICENSE, full
Node/Chromium/FFmpeg/winldd/vendor and Python-package texts and PyInstaller exception;
unknown RECORD ownership is not automatically unlicensed.

Root README.txt points to `notices/native/SOURCE-ACCESS.txt`: complete immutable
upstream module archives (including build/configuration and vendored code), local
application/build-hook source, retained terms and replaceable dynamic DLLs. Under
the GPLv3 section 6(d) route the distributor must maintain equivalent source access
next to the binary; expiry of a CI artifact is not an exemption. Mechanical binding
is not legal certification. Policy correspondence/notice sufficiency requires
independent semantic review. Native provisioner/profile/qualification and the ZIP
are now verified in run39049628794; fixtures alone did not establish that result.

### Explicit native-material v2 (no implicit migration)

`native.json` must use `schema: marsdisplay-native-material-v2`. Legacy,
unknown and UNQUALIFIED diagnostic schemas are rejected; there is no implicit
conversion. Only the pinned policy provisioner creates default owned-stage material.
Direct helper calls retain their unchanged legacy missing-input error:
`Missing reviewed native notices: build/native-material/native.json; Windows qualification is pending`.

Top-level fields are exactly:

- `schema`: the v2 ID above.
- `qt_release`: exact `inventory.build.Qt` stack release, not a label for CRT,
  Mesa or every component's source release.
- `qualification`: nonempty manual-review explanation and limitations.
- `material_sha256`: nonempty relative path→SHA256 map covering genuine license
  texts **and separately referenced source-version proof documents**. The strict
  reader verifies exact nonempty bytes, safe paths and absence of symlinks.
- `components`: exactly one record for each required PySide-prefix native file.

Each component has exactly `path`, binary `sha256`, `component`, `version`,
`sources`, `licenses`, `version_evidence` and `binary_evidence`:

- `version` is the manually reviewed **upstream source release** claim (a bounded
  1–128-character ASCII version token). It is not inferred from Qt, PE numeric
  values, a basename or the installed wheel's version.
- `sources` are nonempty public HTTPS source references. `licenses` and
  `version_evidence` are nonempty lists referencing hashed material; their paths
  must be disjoint. Version evidence must genuinely support the exact source
  release and binary/source correspondence, not substitute PE/RECORD diagnostics
  or generic license text. **Human semantic/authenticity review is required**:
  structural checks bind claims to bytes but cannot certify what a document proves.
- `binary_evidence` must equal a **fresh** `native_evidence.collect` record from
  current runtime bytes, including SHA256, PE status/versions and all RECORD-owner
  matches. Measurement runs only after manifest/schema/material admission; a
  downloaded diagnostic, cached inventory or caller claim is never verification.

Explicit fresh PE `absent` is legitimate, for example for bindings; `unknown` or
`unavailable` cannot verify a required comparison. RECORD `unknown` with
`record_status: available` stays explicitly unknown, neither automatically
licensed nor unlicensed. Unavailable RECORD metadata cannot verify comparison.
CRT source release and PE14.44 remain independent of Qt6.12. A Mesa owner6.12
association alone cannot supply its upstream version or source proof.

The mapping still covers every `.dll`/`.pyd` beneath `_internal/PySide6/` (33 in
the previous runtime inventory); its selector is unchanged, with no expansion
to Shiboken or outside-prefix files. The external-runtime inventory now measures 27 Qt-prefix files in the qualified
build, within 69 total native files; this is measured evidence, not just policy expectation.
Supplemental Shiboken/OpenSSL obligations are bound separately, never fed into this
selector. Complete manifests and raw materials travel in `notices/native/`.
Synthetic tests alone cannot prove Windows qualification. The later native
run39049628794 executed the staged material/v2 gate and produced the verified ZIP.

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

The additive diagnostic `native_evidence` field is still computed **only while
retaining a failure diagnostic**, from the same immutable bytes as `native_files`.
Its schema-v1, existing fields and failure flow stay unchanged. Separately, v2
material admission deliberately calls the same helper afresh for required
binaries to verify declared `binary_evidence`; it never trusts archived diagnostic
facts. The separate pinned policy provisioner now creates owned-stage native.json;
this evidence helper itself still creates no manifest, approval flag or CLI option.

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
source-version proof or legal approval. Run39038363658 measured real facts for
123 native files, but those archived facts are not current verification inputs.
The v2 model requires fresh facts plus separately supported source claims;
synthetic tests establish neither native facts nor genuine material sufficiency.

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

## Workflow and artifact retrieval

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
to the broad native smoke pass in39033278476 described above. Later qualified
runs39049628794 (0.1.0) and39055573997 (0.1.1) executed the complete minimal
external-runtime pipeline and produced verified ZIPs. Owner authorization covers
feature-branch pushes/CI and seven-day test artifacts, not main/PR/release/installer
or hardware work. Server2025 is not Windows11 acceptance.

After a successful authorized run, download `MarsDisplay-Windows-x64`
from the run's Artifacts before its 7-day expiry. Extract the Actions download
archive to obtain the actual ZIP and checksum, compare the ZIP's SHA256 using
`Get-FileHash -Algorithm SHA256`, then extract the **entire** ZIP. Launch
`MarsDisplay/MarsDisplay.exe`; keep `_internal`, LICENSE, notices, source and
inventory together, including root README.txt. MarsDisplay needs no installer;
the separate official VC++ installer may require administrator permission.
Settings persist
per user at `%LOCALAPPDATA%\MarsDisplay\settings.json`, not beside the EXE;
replacing an extracted folder does not clear settings. The unsigned prototype
may trigger Windows warnings: do not disable security protections. No installer,
service, autostart or updater is provided.
