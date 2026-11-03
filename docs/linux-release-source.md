# Collect Linux release source

`packaging/linux/release_source.py` exposes `collect_source(root)`, returning a
repository-relative path-to-bytes mapping. The host build must call it from a
**disposable, clean, canonically stamped Git checkout** before streaming source
into the SDK. There is no CLI, download, output directory or publication step.

## Selection

- Reuse the unchanged Windows source collector, retaining only Git-tracked paths.
  Its existing source, Windows fixture and legal-material validation remains in
  force; its suffix allowlist is not broadened globally.
- Require the production Linux recipe files enumerated in `RECIPE`, including
  Dockerfile, AppRun, desktop/SVG assets, specs, pins and build helpers.
  Nonshipping `SmokeProbe.spec` and `smoke_probe.py` are not prerequisites.
  If tracked, they follow the normal base source selection; their absence does
  not prevent production source export.
- Include only the exact Linux guides enumerated in `OPTIONAL` when tracked.
  This includes future `docs/linux-release-assembly.md`,
  `docs/linux-release-build.md` and `.github/workflows/linux-appimage.yml`.
- Require every retained file named by `packaging/linux/runtime-inputs.json`
  under `third_party/linux-runtime/`, with the exact namespace and SHA256 checks
  shared with `fetch_inputs`. No arbitrary third-party recursion or source
  archive download occurs.

Missing, empty, untracked required inputs, links, unsafe paths, case collisions,
unmerged index entries and inconsistent runtime registries raise `ValueError`.
The call is read-only and silent, including on rejection. Untracked source
neighbors and arbitrary docs/assets are not exported; `.git` and private paths
are never source-map members. The shared collector can reject unsafe workspace
neighbors even when they would not be exported: use the disposable checkout.

## Limits

Tracked membership is not release provenance. Bytes come from the working tree
(not Git blobs) so the canonical version stamp is preserved. The caller owns
clean-checkout, original-commit and stamp validation. Hash matching establishes
retained-material integrity, not upstream attestation, exact compiled-source
identity or legal clearance. Windows packaging behavior is unchanged.
