# Measure Linux native attribution inputs

`packaging/linux/attribution.py` binds every regular ELF payload file to an
exact original file by SHA256. It validates required attribution records and
hashes their local inputs. **Exit 0 is measured coverage, not legal approval.**
Ownership and source statements remain supplied claims, not independently
verified package-manager or registry facts. No network access or host discovery
occurs; this portable unit does not parse ELF architecture or prove rebuildability.

## Run

```sh
.venv/bin/python -B packaging/linux/attribution.py \
  --payload /work/payload --build /work/evidence --output /work/attribution-new
```

All roots must be local, stable during execution, and free of symlink ancestors.
Output must not exist or overlap either input; its parent must already exist.
All symlinks are rejected, including contained runtime aliases: use a prepared
regular-file inventory, not a second copy of each alias counted as another ELF.
Non-ELF files are ignored for coverage. Empty ELF inventories are errors.

| Exit | stdout / stderr | Output |
|---|---|---|
| 0 | `measured=N associated=N unresolved=0` / empty | `inventory.json` |
| 1 | `measured=N associated=M unresolved=K` / empty | Inventory with per-file unresolved reasons |
| 2 | empty / `attribution: REASON` | Input validation creates no output; I/O failures may retain diagnostics |

Each message ends with a newline. Inputs are never modified. Inventory records
all measured hashes, accepted associations, original relative paths, complete
owner records, material hashes, and the evidence manifest hash. Diagnostics are
not a companion notice bundle: preserve the referenced inputs separately.

## Explicit evidence schema

Place `evidence.json` under `--build`. This minimal example uses illustrative
values, not acquired upstream facts:

```json
{
  "schema_version": 1,
  "records": [{
    "file": "_internal/libexample.so",
    "original": "originals/libexample.so",
    "owners": [{
      "kind": "package", "name": "libexample", "version": "1.2-3",
      "source": {"name": "example", "version": "1.2-3",
                 "reference": "https://example.org/source/1.2-3"},
      "licenses": ["legal/example/copyright"],
      "evidence": ["metadata/example-package.txt"]
    }]
  }]
}
```

`file` is relative to payload; all other file paths are relative to build.
Exactly one owner is required. Supported kind labels are `wheel`, `package`,
`vendor`, and `cpython`; none grants exemptions. Name/version and source
name/version/public HTTPS reference are mandatory, as are nonempty legal and
ownership input lists. Source URLs are syntax-checked, not fetched or certified
as corresponding source. Unknown schema fields and duplicate mappings are
rejected. Missing material or hash mismatch remains unresolved. Unsafe paths,
symlinks, duplicate JSON keys and mappings to non-ELF files are input errors.
Existing `notices.py` material-reading and public-source policies are reused;
this adds no license compatibility policy or vendor exception.

## T2c: acquire and generate, then qualify

Generate normalized `file`/`original` mappings from the actual PyInstaller TOC,
retaining original files without changing bytes. No basename matching qualifies.
For wheels, retain exact RECORD membership and installed name/version metadata;
use `notices.collect_distributions` for legal inputs. For system packages,
retain exact file ownership, binary/source package versions and copyright inputs.
For browser/vendor files, retain registry revision, exact file identity and
per-bundle legal inputs using `notices.collect_vendor`, not root-license blanket
coverage. For CPython, retain the actual build version, source reference and
license. Acquire version-specific source references/material where absent.

Automatic generation and independent verification of those supplied claims,
source-obligation fulfillment, real-build coverage, and composition with the
AppImage release assets remain T2c work. The earlier basename-candidate inventory
cannot supply measured associations or clear the five reported browser gaps.
Do not promote missing source facts into exemptions or claim complete S1–S2
release qualification from this standalone collector.
