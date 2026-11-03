# Experimental Linux prototype

Target: **x86_64 Pop!_OS based on Ubuntu 24.04**, with a working system tray.
This is a prototype for private testing, not qualified Linux support or a public
release. The kit is generated under `dist/linux-prototype-42feea4/`; copy the whole
directory, including notices and source material. No remote hardware acceptance
is required before preparing it.

## Run the delivered artifact

Keep the supplied notices, source material and checksum with the AppImage.
From its directory, as your normal desktop user (never root):

```sh
sha256sum -c MarsDisplay-x86_64.AppImage.sha256
chmod u+x MarsDisplay-x86_64.AppImage
./MarsDisplay-x86_64.AppImage
```

If FUSE is unavailable, the type-2 runtime's alternative is
`./MarsDisplay-x86_64.AppImage --appimage-extract-and-run` (verified with the
included runtime for private-route rejection and ordinary Qt admission). This extracts to temporary storage; allow room
for the roughly 1 GB payload. No login registration or system installation occurs.
Use the tray's Status / Settings and Exit actions. USB access must already be
configured manually by the machine owner; the app never changes permissions.
Chromium's sandbox is required: do not disable it to bypass an error.

**Known limitations:** the production frozen worker smoke passed in Noble.
A separate, non-shipping browser probe hit a container sandbox denial; browser
capture has NOT passed. COSMIC/Wayland tray behavior, physical image/brightness,
sustained capture, disconnect cleanup and current native Windows remain unqualified.

## Parent build recipe (offline, in the verified Noble image)

Use the production `build/linux-onedir.tar` from `42feea4`, never the probe tar or
current staged probe files. Extract that trusted archive into a fresh work area;
pass its `MarsDisplay` directory, not the tar. Do not rebuild with host libraries.
The verified builder is `marsdisplay-linux-build:t5a` (Python 3.13.5, glibc 2.39).
Keep the existing nonroot/read-only/network-none/cap-drop container restrictions.
Mount only explicit public inputs and a fresh writable work area, not the checkout.

Tool bytes already verified by parent are under
`build/appimage-tools-ijHACz/{appimagetool-x86_64.AppImage,runtime-x86_64}`.
The JSON pins are independently checked again before any output creation. `--tool`
means the ORIGINAL AppImage, not extracted AppRun. Only that build subprocess gets
`APPIMAGE_EXTRACT_AND_RUN=1`; product launch and workers never get an override.

With input mounts at `/inputs` and a fresh writable `/work`, run:

```sh
python -B /inputs/packaging/linux/build_appimage.py \
  --onedir /work/production/MarsDisplay \
  --tool /inputs/appimagetool-x86_64.AppImage --runtime /inputs/runtime-x86_64 \
  --license /inputs/LICENSE --notices /work/notices --output /work/prototype
cd /work/prototype
sha256sum -c MarsDisplay-x86_64.AppImage.sha256
```

The output contains AppDir, image, checksum and tool log. Failures retain their
output for diagnosis; reruns need a NEW destination. Inputs must remain immutable
throughout the command. The manifest records the caller's source/builder contract,
not independent proof of an arbitrary input's origin. Existing payload notices,
modes and contained relative symlinks are preserved. AppRun execs the inner binary
with unchanged arguments/environment/PID, preserving the frozen worker launch path.

## Attribution and source material

Reuse `packaging/notices.py` on the **same verified builder**, with committed
`packaging/payload.py` and `third_party/license-material` available in `/inputs`.
This passive collection command produces the Python/vendor subset, not clearance:

```sh
cd /inputs
python -B - <<'PY'
import json, runpy, tomllib
from pathlib import Path
from packaging.requirements import Requirement
import playwright
n = runpy.run_path('packaging/notices.py')
roots = tomllib.loads(Path('pyproject.toml').read_text())['project']['dependencies']
deps, material = n['collect_distributions']([Requirement(r).name for r in roots] + ['pyinstaller'])
browsers, vendor = n['collect_vendor'](Path(playwright.__file__).parent / 'driver')
assert not material.keys() & vendor.keys()
material.update(vendor)
material['inventory.json'] = (json.dumps({'dependencies': deps, 'browsers': browsers}, indent=2) + '\n').encode()
out = Path('/work/notices')
out.mkdir()
for name, data in material.items():
    path = out / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
PY
```

The test kit supplements that subset with CPython's license, builder provenance,
installed wheel license/notice/attribution material, Noble library owner candidates
and their copyright/common-license texts. Candidate ownership is not an exact ELF
byte-equivalence certification. Browser/FFmpeg binaries use the vendor collector's
material rather than Noble package attribution.

Runtime source, libfuse source and its runtime patch, dependency notices and source
references accompany the kit. `SOURCE-REFERENCES.md` explains source locations and
replacement/rebuild paths. Production source is archived from `42feea4`, never
from the dirty checkout or the non-shipping probe. The packaging recipe is supplied
separately. These records do not claim legal clearance or a completed public-release
license audit; retain them with the prototype and do not publish it as a supported
release.

Observed artifact checks: SHA256 verification, no-FUSE private-route rejection,
extracted AppRun's real frozen worker lifecycle, and ordinary Qt startup rejecting
an absent tray with the documented diagnostic and no settings creation. FUSE mount,
real desktop capture, USB hardware and native Windows were not tested here.
