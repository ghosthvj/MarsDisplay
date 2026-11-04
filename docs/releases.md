# Publish a Windows and Linux release

1. Open **Actions → Publish Windows and Linux release → Run workflow**, select **main**.
2. Enter a new **Tag**, for example `v0.2.0rc8` or `v0.2.0`, then run it.
   This requests public publication, not a dry run. No prior edit to
   `pyproject.toml` or manual tag creation is needed.
3. After success, download the complete portable ZIP and its `.sha256` file
   from **Releases**. Do not distribute the EXE separately from its resources.
   Linux adds an experimental x86_64 AppImage, companion support ZIP and both
   SHA256 files. Preserve the companion sources/notices when distributing it.

Tags must use canonical `vX.Y.Z` or `vX.Y.ZrcN` form (no leading zeroes in
numeric components). `rc` tags create prereleases; other accepted tags create
regular releases. Existing tags or releases, including drafts visible to the
workflow token, are rejected before the build. Publication still uses exclusive
tag creation to reject a duplicate created while the build was running.

## Build version and source provenance

The tag points to the exact triggering main commit. That commit's
`pyproject.toml` stays unchanged: the action makes **no version commits**.
Before installing the application, the Windows job stamps only
`[project].version` in its disposable checkout, using the canonical Git blob.
Dependency pins and other settings remain unchanged. The installed package,
ZIP name and bundled `source/pyproject.toml` use the selected version.
This does not add a GUI version display or an EXE file-version resource.

The archive's `inventory.json` retains `source_commit` as the original revision
and includes `release` provenance: requested tag, effective/original versions,
stamp method, and original/effective TOML SHA256 hashes. Bundled source contains
the stamped TOML, so it is explicitly **base source plus a version stamp**, not
a pristine checkout. The builder validates this record and installed version;
the publisher independently checks the exact transformation against its clean
checkout before any tag/release writes. All ordinary source/payload hashes
continue to describe the actual shipped bytes.

Tests (zero skips on Windows), native/license qualification and packaged smoke
remain required. Only the publisher has write permission. It creates a draft,
waits for both platform builders, uploads all six assets by that draft's ID,
verifies remote asset hashes and
the actual tag commit, then publishes. Preserve bundled source-access directions
and notices when redistributing the package.

## Failures and development

No existing tag, release or asset is overwritten or deleted. A failed run may
leave a tag/draft or an uncertain final state after a network error. Inspect
GitHub before rerunning; there is no automatic retry or cleanup. Use a new
version for a new release. A rerun uses its original workflow commit.

`python packaging/release.py --help` documents `plan`, `stamp` and `publish`.
`plan --tag vX.Y.Z` validates the manual-main context and remotely checks
availability with a read-only GitHub token. `stamp --tag vX.Y.Z` prepares only
the current checkout and `build/release-version.json`; it never commits or
contacts GitHub. Use a fresh checkout: dirty project files or an existing stamp
are refused. An interrupted stamp is not reusable; inspect it rather than
retrying in place. To reproduce a selected version, check out its source commit,
stamp with its tag, then install the build SDK and run the normal recipe.

The standalone **Windows portable prototype** workflow accepts an optional
`release_tag` for nonpublishing build verification. Empty input preserves its
normal project version. Combining a tag with layout diagnostics is rejected
before SDK installation: `release_tag cannot be combined with layout_diagnostics.`
Diagnostics with an empty tag retain their existing behavior and do not package.
Legacy CLI `plan`/`publish` without `--tag` retain project-version behavior;
explicit-tag publication requires the stamped provenance. Tests mock GitHub.

Cross-platform tests canonicalize temporary fixture paths before comparing them
with resolved tool paths. Artifact fixtures derive both platforms' source bytes
and hashes from the fixture's Git commit and the version-stamp transformation,
not from working-tree line endings. `.gitattributes` preserves the hash-pinned
`third_party/linux-runtime/` material byte-for-byte on checkout, including with
`core.autocrlf=true`. Do not normalize retained bytes, regenerate pins or skip
Windows tests to compensate for checkout conversion.

For native OpenSSL mismatches, use the build-only **Windows portable prototype**
workflow on the investigation branch with empty `release_tag` and
`layout_diagnostics=false`. A rejected build remains failed and uploads only its
`UNQUALIFIED` diagnostic. `openssl_selection` reports recognized installation
categories only when the selected source bytes match the packaged DLL; it does
not retain absolute paths or PATH. Unknown locations remain redacted. These
facts identify collection locations, not suppliers or qualified source builds;
they never replace the native policy or authorize updating its hashes.

If the location remains unknown, the manual build-only workflow offers
`trace_openssl_origins` (default **false**). Enabling it explicitly exposes only
the selected `libcrypto-3-x64.dll` and `libssl-3-x64.dll` source paths in public
GitHub logs. It is restricted to manual GitHub-hosted Windows runs; reusable
release builds cannot enable it. It never dumps PATH, environment values or
application data, and does not change the redacted artifact or native gate.

## Combined Linux publication boundary

`publish --artifacts WINDOWS_DIR --linux-artifacts LINUX_DIR --tag vX.Y.Z`
validates both platform directories before any remote write. Linux contributes
four versioned files: AppImage, support ZIP, and both SHA256 sidecars. Its
support manifest binds the image hash and canonical source/version provenance.
All six assets must pass remote readback before the draft becomes public.
`--linux-artifacts` is a publish-only option; `plan` and `stamp` reject it.
Omitting the option preserves Windows-only publication and validation.

The joint workflow retains the existing Windows builder and adds the read-only
**Experimental Linux AppImage** reusable workflow. Both receive the same tag and
triggering commit. Publication requires both jobs to succeed, downloads their
separate artifacts from the same run, and validates both before remote writes.
Only the publisher receives write permission; no private Linux workspace is uploaded.
The existing concurrency group is retained to serialize old and new release runs.

The Linux workflow also supports manual build-only runs with a required
`release_tag`; it never publishes. It runs source tests and the committed host
recipe, including frozen worker checks and native/source association. See
[Linux build](linux-release-build.md) and [Linux distribution](linux-distribution.md).
The format validator does not certify legal material or desktop/hardware behavior.
The initial candidate's independent archive verification was unavailable and the
maintainer explicitly accepted that gap; it is not an independent verification pass.
GitHub execution and native Windows acceptance have not been newly observed locally.
