# Acquire Linux build evidence and retained notices

`packaging/linux/build_evidence.py` measures the ELF files actually shipped under
`_internal`, acquires installed SDK ownership and source/legal inputs, and composes
the unchanged `attribution.py` collector. Exit zero means those required inputs
are present, **not legal certification or independently attested binary builds**.

## Run on the Noble builder

Use the SDK Python environment that produced the COLLECT TOC:

```sh
python packaging/linux/build_evidence.py \
  --payload dist/MarsDisplay/_internal \
  --toc build/MarsDisplay/COLLECT-00.toc \
  --project . --output build/native-evidence
```

The output must not exist; its parent must exist. The project supplies
`pyproject.toml`, `packaging/linux/toolchain.json`, and the reviewed material
registries. The SDK supplies installed wheel metadata, dpkg records and raw
copyright files, the retained CPython archive, and package-local Playwright files.
The ignored `native-associations.json` is diagnostic context, never trusted input.
There is no CLI owner override or proof-bypass option. No download is performed.

## Evidence acquired

| Input | Measurement and retained provenance |
| --- | --- |
| COLLECT | Literal parsing, exact destination/original bytes, unique resolved original; no basename approval. |
| Wheel RECORD | Exact installed path, SHA256 and size; multiple matching owners reject. Raw licenses and dependency closure use unchanged `notices.collect_distributions`. |
| Noble packages | Exact `dpkg-query --search` path, installed binary/source package versions, matching package md5sums, raw copyright and referenced common licenses. Version-specific Launchpad source routes identify Ubuntu source packages. |
| CPython | Running SDK version matches toolchain pin; retained `Python.tar.xz` SHA256 is checked before reading its regular LICENSE member, without extraction. Only the SDK libpython and lib-dynload paths qualify this way. |
| Node | Original is the installed Playwright driver node with verified RECORD bytes; `node --version` supplies actual version and versioned source archive route. Vendor notices retained. |
| Chromium | Original is inside an exact installed registry directory; revision and four-part browser version supply source tag/DEPS directions. Other shipped vendor families reject. |
| Qt/PySide | Exact wheel release and existing reviewed native-source registry are required. Immutable module sources, raw legal inputs and the full Qt release source route are retained. Windows PE byte policies are never applied to Linux ELF files. |

Pillow and greenlet retain version-specific release source routes and installed
wheel licenses, including wheel-provided bundled notices. Unknown native wheel
source families fail explicitly rather than acquiring an invented generic owner.
Qt/PySide source references describe distribution releases and the retained full
source routes, not separately attested build revisions of every bundled library.
Existing registry coverage limits remain in the retained provenance files.

`notices.collect_vendor` runs unchanged against the installed SDK. Thus SDK FFmpeg
must still be installed with its notices, even though the screenshot build omits
standalone FFmpeg. `installed.json` distinguishes the installed browser inventory
from the shipped native browser set; no FFmpeg source association is invented for
an absent executable. The exact beta Playwright core source commit from
`notices.py` is preserved, never replaced by the stable v1.64.0 tag.

## Outputs and failures

- **Exit 0:** collector prints `measured=N associated=N unresolved=0`; `notices/`
  contains the native inventory, raw referenced legal/evidence inputs, installed
  Python/vendor metadata and `SOURCE-ACCESS.txt`.
- **Exit 1:** collector prints measured/associated/unresolved counts. Per-file
  acquisition failures remain in `acquisition.json`; collector diagnostics remain
  in `association/inventory.json`. No `notices/` directory is created.
- **Exit 2:** invalid input or a global acquisition failure prints
  `build-evidence: <reason>` on stderr. Preflight rejection creates no output.
  Later filesystem failures can retain partial output; there is no cleanup, retry,
  overwrite or input mutation. A partially written notices directory is not success.

**Publish only `notices/`, and only after exit zero.** The output root also retains
private `evidence/` and `payload/` regular-file views for the collector's unchanged
no-symlinks contract. Never include these ELF copies in public notices. Inventory
original paths are identifiers relative to the private evidence view, not exported
binaries. Safe in-payload file aliases are recorded separately; directory aliases,
escaping aliases and ambiguous original/RECORD associations reject.

Public notes contain no original absolute SDK paths or environment dumps. Dpkg
package paths are relative package-owned paths. Local filesystem errors can name
host paths and are not public notes. The generated main application/PyInstaller
bootloader and outer AppImage runtime remain explicit separate integrating-build
obligations, not universally exempt components.

## Verification and review boundaries

Portable temporary fixtures drive the public `main` using a Python-only SDK
context seam. Tests cover complete package, CPython, wheel, Node and Chromium
acquisition; missing/changed originals, invalid RECORD hashes, wrong package and
Node owners, missing copyright/source identity, and CPython archive corruption.
Parent-owned Noble execution is still required to verify actual installed inputs.

Measurement diagnostics, package/CPython acquisition, and additional wheel/vendor
acquisition form separate functional review units, each with its public-main tests
and documentation. No upstream legal bytes are committed by these units: existing
collectors copy registered/installed bytes into generated output at execution time.
