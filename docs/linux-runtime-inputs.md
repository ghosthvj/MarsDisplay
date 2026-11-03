# Prepare pinned AppImage runtime inputs

`packaging/linux/fetch_inputs.py` prepares tools and runtime notices independently
of native payload attribution. It verifies bytes, not legal clearance or full Linux
release qualification. It never executes tools, extracts archives or changes modes.

## Run

```sh
python packaging/linux/fetch_inputs.py --output build/runtime-inputs
```

The output must not exist; its parent must already exist and contain no symlink
ancestors. Success exits 0 and prints `Prepared pinned Linux inputs.` to stdout.
`--help` describes the fresh-output and failure-retention contract.

| Output | Purpose |
| --- | --- |
| `tools/appimagetool-x86_64.AppImage` | Build tool, unchanged existing pin |
| `tools/runtime-x86_64` | Outer runtime, unchanged existing pin |
| `notices/runtime/` | Three source archives, eight verbatim legal/build texts, selected API metadata, provenance and hash registry |

Only `notices/` belongs in the support ZIP. **Never include `tools/` there.**
Archives and binaries remain downloaded inputs, not committed files. The caller
owns later execution permissions and assembly; this helper does neither.

## Integrity and failures

Tool routes use GitHub asset IDs from unchanged `appimage-tools.json`, with the
API octet-stream Accept header and mandatory SHA256 checks. No latest fallback.
`runtime-inputs.json` lists the three exact archive names/URLs/digests and all
retained filenames/digests. Retained inputs live in `third_party/linux-runtime/`.
Unknown, duplicate, missing or unsafe names, invalid hashes, unsafe URLs,
symlinked local inputs, missing material and changed bytes fail closed.
HTTPS hosts are restricted to GitHub download infrastructure and Alpine distfiles;
redirects receive the same host/scheme checks (signed redirect queries allowed).

Validation and fetching finish in memory before output creation. Failure exits 1,
leaves stdout empty and prints `fetch_inputs: <reason>` to stderr. Rejected inputs
and failed downloads create no output. Filesystem write failures instead print
`fetch_inputs: output I/O failed; any partial output is retained`; inspect that
partial directory and use a different fresh destination. There is no retry,
overwrite or automatic cleanup. Stderr is the diagnostic record; no log file is
created. Existing caller data and local inputs are never rewritten.

## Provenance and rebuilding

`provenance.json` preserves source-route bases and limits. The runtime source at
`fedfad51acc2860b2916a1eef32ba4a500ff31ef` includes `BUILD.md` and its build/relink
scripts. Use that source tree with the libfuse 3.15.0 source and mount patch to
rebuild a modified runtime; repack via appimagetool's `--runtime-file` and
intentionally revise production pins. The loose dependency recipe is a verbatim
reference: its relative paths require the original tree. No rebuild was run here.

Selected asset/run API fields bind the retained parent-record hashes and report
asset digest/size and successful run head commit. They are metadata association,
not a verified signature/attestation. The eight raw texts retain prototype bytes;
mutable component notice references do not establish exact compiled versions.
The parent verified the selected Alpine 3.21 musl 1.2.5 route against retained
SHA256 in job36. This supplementary upstream archive is **not exact APK build
source** or historical acquisition proof. Actual musl/zlib/zstd Alpine build
revisions remain unconfirmed; no new rebuild gate is implied.

Portable tests inject transport and fixture paths through Python `main`, never
CLI proof-bypass flags. Actual tool/source fetch validation and release assembly
remain parent-owned; native acquisition is a separate unit.
