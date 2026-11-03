# Experimental Linux distribution

Linux uses an x86_64 AppImage plus a companion source/notices ZIP. Higher-level
build and release CI integration is in progress; this format does not imply a
currently available public Linux release or legal clearance.

The user reported physical image display and brightness working with the
prototype on Pop!_OS 24.04 after manually enabling USB access. This is not a
claim of new hardware testing, prolonged operation, disconnect recovery, or
qualification of every Linux distribution.

## Run as your normal user

When a qualified artifact set is provided, keep all four files together. Replace
`1.2.3` below with its actual version:

```sh
sha256sum -c MarsDisplay-1.2.3-Linux-x86_64.AppImage.sha256
sha256sum -c MarsDisplay-1.2.3-Linux-x86_64-support.zip.sha256
chmod +x MarsDisplay-1.2.3-Linux-x86_64.AppImage
./MarsDisplay-1.2.3-Linux-x86_64.AppImage
```

Stop if either checksum fails. Checksums detect changed bytes, not publisher
authenticity; obtain artifacts and checksums from the same trusted release.
Read the companion `MarsDisplay/README.md` and notices before use. Do not run the
application as root or disable the browser sandbox to work around startup errors.

USB serial access may require membership in `dialout` on Pop!_OS/Ubuntu. Check
`id -nG` and the device's group first. Ask your administrator to add your normal
account to `dialout` if appropriate, then log out and back in. This is a manual,
privileged system decision; the AppImage does not change permissions or groups.

## Offline artifact format

| File | Purpose |
| --- | --- |
| `MarsDisplay-{version}-Linux-x86_64.AppImage` | Direct runnable image |
| `MarsDisplay-{version}-Linux-x86_64.AppImage.sha256` | Image SHA256 and filename |
| `MarsDisplay-{version}-Linux-x86_64-support.zip` | Companion tree rooted at `MarsDisplay/` |
| `MarsDisplay-{version}-Linux-x86_64-support.zip.sha256` | ZIP SHA256 and filename |

The companion contains prepared `source/pyproject.toml`, nonempty `notices/`
material, `README.md` instructions and any further prepared source/legal files.
The assembler adds `inventory.json` with `target: Linux-x86_64`, `source_commit`,
canonical `release` provenance, `appimage: {name, size, sha256}`, and a `files`
mapping of every other companion member to SHA256. Unsafe paths, duplicate
case-folded names, file/directory collisions and links are rejected.

## Maintainer build-format and check commands

Run from the source Git repository, using Python 3.11 or newer. Prepare content
separately: its project TOML must equal the exact `release_version.render`
transform of the original TOML at the selected commit. Do not alter or commit
the canonical source version merely to assemble artifacts.

```sh
python -B packaging/linux/release_assets.py build --help
python -B packaging/linux/release_assets.py build --image candidate.AppImage --content prepared-companion --output new-artifacts --tag v1.2.3 --sha ORIGINAL_COMMIT_SHA
python -B packaging/linux/release_assets.py check --artifacts new-artifacts --tag v1.2.3 --sha ORIGINAL_COMMIT_SHA
```

Use a full lowercase 40-character SHA and canonical `vX.Y.Z` or `vX.Y.ZrcN` tag.
The output directory must not exist, its parent must exist, and it must be outside
the content tree. Inputs remain unchanged. An I/O failure can leave a partial new
output; inspect it and choose a fresh directory rather than retrying over it.
Validation reads all four exact assets without extraction or execution and checks
hashes, image binding and canonical provenance against Git. It creates no tag.

The portable integration API is `assets(folder, version, sha, tag=None)`, returning
absolute paths mapped to `name`, `size`, `state: uploaded` and `digest: sha256:...`.
An omitted tag is derived from the version; provenance checks remain mandatory.
Successful CLI operations print `Linux artifact format validated; legal qualification is separate.`
Invalid format/provenance returns exit 1 with `Linux artifact error: Invalid Linux artifact format or provenance.` on stderr.

This module does not build or inspect executable behavior, collect attribution,
certify legal completeness, or publish releases. The integrating build must
supply complete corresponding source, instructions and measured native notices,
resolve missing evidence, and perform runtime qualification before publication.
Windows packaging and the legacy Linux prototype remain separate and unchanged.

## Distribution runtime selection

The distribution uses `packaging/linux/Release.spec` in the pinned Noble builder.
It preserves the prototype's application analysis, USB bootstrap and Chromium
collection, but omits only files beneath the package-local standalone
`.local-browsers/ffmpeg-N/` directories. MarsDisplay captures PNG through CDP;
it does not enable Playwright video recording, the consumer of that executable.
Chromium's internal media libraries, Node, browser registry, sandbox settings and
SDK versions are unchanged. The original `MarsDisplay.spec` still builds the
original prototype layout; Windows uses its existing independent recipe.

The builder SDK still installs FFmpeg. Notice collection may therefore include
supplementary SDK material, but shipped-payload inventory must explicitly record
the standalone recorder's absence, not describe the complete SDK as the runtime.
Source inspection and selection fixtures do not substitute for the actual frozen
build and worker smoke or establish fresh physical-device qualification.
