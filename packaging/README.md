# Portable delivery support — not a Windows build

This unit provides file/metadata helpers and a windowed bootstrap for the later
Windows 11 x64 builder. **No executable, native build recipe, workflow, packaged
smoke test or distributable Windows ZIP has been delivered.** T5 remains in progress.
Synthetic test executables are arbitrary bytes, never Windows functionality proof.

## Builder integration

Load these standalone modules by file path (`importlib.util.spec_from_file_location`)
or from the builder script directory. Do not add `packaging/__init__.py`: it would
shadow the installed `packaging` distribution used for requirement parsing.
There is no public packaging/product command or new app option.

| Helper | Input and result |
| --- | --- |
| `payload.read_tree(root, paths=None)` | Runtime tree or exact relative file selection → path/bytes mapping; rejects links/private paths. |
| `payload.collect_license_material(root)` | Local schema-1 legal registry → `(registry, verified_bytes)`; includes only listed files, registry and README. |
| `payload.collect_source(repo)` | Allowlisted source/build/test/legal inputs and `.gitattributes` → path/bytes mapping. |
| `notices.collect_distributions(roots, lookup=metadata.distribution, *, material_root=None)` | Installed runtime closure → `(inventory, license_bytes)`; exact-version local fallback only when installed license files are absent. |
| `notices.collect_vendor(driver)` | Actual Playwright driver directory with package-local browsers → `(browser_inventory, vendor_bytes)`. |
| `payload.assemble(output, version, runtime, source, notices, inventory)` | Validated mappings → `(folder, zip_path, sha256_path)`; does not run or authenticate an executable. |
| `entrypoint.run(main=None, reporter=message_box)` | Deferred app import, temporary stream capture and native sanitized reporting; returns main's exit code. |

The future builder must run on Windows with the pinned environment and bundled
Chromium, collect the four direct runtime roots declared by `pyproject.toml`
(Playwright, PySide6, Pillow, pyserial), and merge distribution/vendor notices.
Do not use the application distribution as a dependency root: application
provenance is the GPL LICENSE, corresponding source and source commit, not an
invented project URL. Collect actual build-tool versions separately; build-only
extras are not runtime dependencies. Failures identify missing license material;
resolve them from genuine upstream material with provenance, never placeholders.

## Layout and inventory contract

The native recipe must supply this one-folder layout (the default headless launch
uses Chromium headless shell, not the user's browser):

```text
MarsDisplay/
  MarsDisplay.exe
  _internal/PySide6/Qt/plugins/platforms/qwindows.dll
  _internal/playwright/driver/node.exe
  _internal/playwright/driver/package/browsers.json
  _internal/playwright/driver/package/.local-browsers/
    chromium_headless_shell-<revision>/chrome-headless-shell-win64/headless_shell.exe
    ffmpeg-<revision>/ffmpeg-win64.exe
  LICENSE
  inventory.json
  notices/third-party/...
  notices/vendor/...
  source/...
```

`inventory` requires `target: "Windows-x64"`, the exact 40-hex `source_commit`,
`build` with actual `Python`, `PyInstaller`, and bundled `Node` versions,
`dependencies` with each installed `name`, `version`, public `sources` and raw
license statements/file references, plus `browsers` from the vendor collector.
The builder must measure Node's version from the bundled binary, not infer it
from Playwright's version or a Node engine constraint. Each declared browser
revision must contain its required Windows executable at the exact layout above;
a stale directory containing only a README is not a match. Preserve registry browser versions verbatim;
FFmpeg's registry has no browser version, so retain its exact revision.
Assembly adds SHA256 hashes of all supplied files to the inventory; the inventory
itself is covered by the final ZIP checksum. No credentials, environment dump or
editable-install checkout URL belongs in the inventory. Exact source commit alone
is not enough for dirty builds: the actual included source bytes remain available
and hashed. The future builder must identify/reject unrecorded source divergence.

Source collection includes `src`, `packaging` recipes, `tests`/fixtures with known
source extensions, README, GPL LICENSE, `pyproject.toml`, both requirements
files and `.gitattributes` when present. It also includes the verified
`third_party/license-material/provenance.json`, its README and exactly its listed
material files, including supplementary Qtbase inputs; unregistered files in that
directory are not source inputs. It excludes task logs, Git/venv/cache data, settings, profiles, `.env`,
cookies, tokens and credential paths. It is not a workspace archive or general
secret scanner: the builder must inspect selected build/source inputs before
delivery. Assembly requires build/test/source categories and root build files;
it cannot prove that arbitrarily supplied source is complete or corresponds to
binary machine code. Native build/smoke verification supplies that missing proof.

Use repository `build/` for native staging and `dist/` for final outputs. Assembly
validates all paths/layout/inventory before creating output files. It rejects
Windows-unsafe names, traversal, case-insensitive/file-directory collisions,
symlinks (when reading trees), and existing folder/ZIP/checksum targets. It emits
`MarsDisplay-<version>-Windows-x64.zip` with a single `MarsDisplay/` root plus
`.zip.sha256`. Existing outputs are never replaced. Caught publication failures
roll back only newly created outputs, and temporary directories are cleaned.
This is not a crash-recovery transaction across three filesystem objects; a
terminated process may leave incomplete outputs, which a later run must refuse.

## Notices and qualification limits

Raw installed license texts/statements are retained without inventing SPDX labels
or claiming legal compatibility. Metadata project URLs provide public provenance;
URL credentials, queries and fragments are not exported. Node's driver LICENSE,
Playwright LICENSE/NOTICE/ThirdPartyNotices, per-bundle `.LICENSE` sidecars, the
browser registry and installed Chromium/FFmpeg license material are copied, not
replaced by Python package metadata. Missing required material is an error.
This inventory is preparation for review, not a completed legal audit or proof
of all third-party corresponding-source obligations.

The Linux installed-material probe found Playwright/greenlet/pyee/typing_extensions
and Pillow license files, Node's complete LICENSE, Chromium headless-shell revision
1248 (registry browser version 156.0.8078.4) and FFmpeg revision 1013 license files.
The installed PySide6 and pyserial distributions lack license-text files in their
installed file lists. Collection now uses the committed
[versioned legal inputs](../third_party/license-material/README.md) for these
explicit mappings only: pyserial 3.5; PySide6/Essentials/Addons/shiboken6 6.12.0;
PySide6_WebEngine/Pdf 6.12.0.140. Names are canonicalized, versions must match
exactly, and no prefix compatibility is inferred. Other missing mappings fail.

The default material root is resolved relative to this source module, not the
working directory. `material_root` is an optional explicit local root for isolated
callers/tests, not a product flag. Collection never fetches or updates material.
Every retained material file is SHA256-checked; safe relative paths, symlinks and
parent escape, duplicate names, source commits and public commit-pinned HTTPS
references are checked before use. Installed license paths are anchored to
`distribution.locate_file('')` and checked by the same selected-file reader before
reading bytes. Absolute/traversing paths and symlinks in any ancestor are rejected.
Installed nonempty license files take priority; unsafe, broken or empty installed
material fails rather than silently falling back. Fake metadata fixtures must
model `locate_file('')` as the distribution root. Real Linux symlink regressions
are not native Windows filesystem/privilege qualification.

Fallback inventory preserves installed raw license statements and project sources,
adding `license_provenance` (matching complete registry records), `license_registry`
and `license_qualification`. One shared `upstream/` copy contains all 52 verified
materials plus registry/README, not six copies of binding texts. Supplementary
records with `packages: []` are retained there and in application source, but are
not assigned as package license coverage. Source-archive URLs and published digests
remain registry evidence; collection does not download or authenticate archive bytes.

The actual Linux probe collected all 12 runtime distributions without missing
license-input mappings: 67 notice files including 54 shared upstream inputs,
plus 10 Playwright vendor files. It retained 41 supplementary native-source records
without assigning them as binary coverage. Qt binding texts/headers do not establish
native Qt/WebEngine/Pdf/plugin attribution, commercial rights, selected license
alternatives or complete corresponding-source compliance. Those remain native
payload qualification work. Linux availability is not Windows qualification.

## Windowed bootstrap and next unit

Freeze `entrypoint.py` with windowed/no-console settings in the next native recipe.
It prepares stdout/stderr before importing the app, reports trusted sanitized app
stderr through a temporary native MessageBox (information for exit 0, error
otherwise), and restores global streams on every path. Unexpected bootstrap/import
failures discard captured text and show only
`Cannot start MarsDisplay; check the application runtime and try again.`
It does not change main's owned cleanup or ordinary source startup. Native dialog
tests are mocked; successful silent startup creates no extra permanent window.

Next: implement `build_portable.py`/`MarsDisplay.spec`, map actual native binary
license/source obligations, supply measured build inventory, and prepare the isolated actual
executable/browser smoke and inert workflow source. Actual Windows build/ZIP/smoke,
CI execution/publication, Windows 11 tray/LAN/resource acceptance and physical
hardware/protocol support remain separately gated and unproved.
