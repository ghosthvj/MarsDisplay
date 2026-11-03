# Build a Linux AppImage release

## Host command

From a Linux x86_64 checkout with Python 3.13 and Docker available:

```sh
mkdir -p dist
python -B packaging/linux/build_release.py --tag v0.0.0 --output dist/linux-candidate
```

`v0.0.0` is a local validation example; choose the intended canonical tag for a
real build. No tag, remote release, push or publication is performed. Add
`--sudo-docker` only when explicitly choosing `sudo -n` for the Docker client;
the application build still runs as UID/GID 10001, never root.

The command builds committed HEAD only. It clones without hardlinks, stamps the
disposable checkout and exports exact source; original files and index, including
uncommitted changes, remain untouched and are not packaged. The output parent must
already exist and be unlinked; the output directory must not exist.

SDK provisioning and verified input acquisition need network access. Application
installation, freezing, worker smoke and native collection run in the offline,
read-only SDK through the [stream transport](linux-sdk-transport.md). Only original
public TOML, toolchain JSON and Dockerfile enter the SDK build context. The image
is inspected and run by its measured local image ID, not a mutable tag. Pinned
tool bytes are checked before making appimagetool executable.

Success returns four files: versioned AppImage and support ZIP, each with SHA256.
The support ZIP contains instructions, canonical stamped source and merged public
notices; the published SDK build record must equal the checked sidecar. Measured
AppImage/SDK records and recipe identity accompany them. Existing asset build and
check CLIs validate canonical Git/source/hash bindings before success is reported.

Private `.linux-release-*` workspaces beside the output retain diagnostics,
source copies, downloaded tools and SDK tar files. Docker images are also retained.
Publish only the explicitly returned four-asset directory, never its parent or a
failed/partial output. Failures exit 2 and name retained diagnostics; no automatic
retry or cleanup. This command does not establish new desktop/hardware support or
legal clearance. Integrated candidate qualification remains separate.

## Inner SDK stage

`packaging/linux/build_sdk.py` is the inner build stage, not a publisher or the
host-side Git/stamping orchestrator. Run it in the pinned Noble SDK, as a nonroot
user, with read-only SDK/root filesystem and a dedicated writable workspace.
Use the image's original `builder` user (UID 10001): some browser input files are
owner-readable only, so mapping the caller UID does not provide complete SDK access.
Stream selected inputs into `/work` tmpfs owned by UID/GID 10001; do not relax
SDK file permissions or run the application as root.
The host must first validate the original Git revision and canonical release
stamp. Export selected source bytes without `.git`, credentials or a host venv.

```sh
python -B /work/source/packaging/linux/build_sdk.py \
  --project /work/source --release-record /work/release.json \
  --output /work/result
```

`release.json` is the host-verified `release_version.inspect` result. The SDK
checks record structure, stamped TOML hash/version, CPython version/source pin and
installed PyInstaller identity/legal inputs. It does not establish Git ancestry,
verify the container image identity or certify binary-build provenance.

## Build and outputs

The output must be fresh, outside the source tree, with an existing unlinked
parent. Source bytes are copied into private `result/project/` before building;
pip/setuptools cannot mutate the supplied source. Application installation uses
`--target result/application`, no index, no dependency resolution and no build
isolation. Installed metadata must match the requested version before freezing.
The SDK venv is never modified. Its existing build requirements must be present.

The stage runs `Release.spec`, the existing production worker smoke and native
source acquisition. It does not add a browser probe, USB permission changes or a
sandbox bypass. Build-tool notices retain installed PyInstaller legal material,
including its bootloader exception, and version-specific source directions.
The generated executable is measured separately, not called an unchanged wheel.

After exit zero (`Prepared Linux SDK build.`), export only `onedir/`, `notices/`
and `build.json`. The latter records actual installed version, executable hash,
SDK Python/nonroot UID, PyInstaller version and successfully completed checks.
The main application LICENSE and record are also under `notices/application/`.
Runtime notices are merged later by the host; tool downloads never enter notices.

Exit 2 reports `error: <reason>` on stderr. Preflight rejection runs no commands
and creates no output. Later failures retain private output and `build.log`; no
retry or cleanup occurs. Never publish a partial result, compiler work, application
install target, source copy, acquisition ELF views, caches, home or build log.
A zero exit is measured build evidence, not legal clearance or final release
qualification. Apt/transitive wheels remain incompletely locked: this is a pinned
recipe with recorded provenance, not a promise of byte-reproducible artifacts.
