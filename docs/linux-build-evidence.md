# Measure Linux native build associations

This diagnostic slice matches shipped ELF bytes to unique literal COLLECT TOC
originals and checks installed wheel RECORD hashes and sizes. It does not acquire
source/legal material or produce qualified notices. Ownership is not legal approval.

Run in the same SDK that produced the payload and TOC:

```sh
python packaging/linux/build_evidence.py \
  --payload dist/MarsDisplay/_internal \
  --toc build/MarsDisplay/COLLECT-00.toc \
  --project . --output build/native-evidence
```

The output must be new and its parent must exist. Inputs remain unchanged.
Literal TOC parsing never executes input; missing, changed or ambiguous originals,
invalid/ambiguous RECORDs, and unsafe aliases reject. Contained file aliases are
recorded separately; escaping and directory aliases reject.

Exit 1 prints measured/associated/unresolved counts and retains `acquisition.json`,
`association/inventory.json` and private `evidence/`/`payload/` regular-file views.
No owner is qualified and no `notices/` directory is created. Never publish these
intermediate ELF copies. Exit 2 prints `build-evidence: <reason>` for invalid input;
preflight rejection creates no output, while later I/O failures may retain partial
output. No cleanup, overwrite or retries are performed.

Public-main fixtures verify literal parsing, original/RECORD matching, refusal to
qualify byte associations alone and preservation of existing output/input bytes.
Package/CPython and wheel/vendor acquisition are subsequent functional units.
Generated application/bootloader and outer runtime qualification remain separate
integrating-build obligations.
