# Assemble a private Linux release candidate

`packaging/linux/assemble_release.py` assembles an existing production onedir into
an AppDir and an unversioned private `MarsDisplay.AppImage`. It does not publish,
download, stamp source, run smoke tests, or certify redistribution readiness.

## Quick path

On a Linux x86_64 builder, after host canonical stamping/inspection and input checks:

```sh
python packaging/linux/assemble_release.py \
  --onedir /work/dist/MarsDisplay \
  --tool /inputs/tools/appimagetool-x86_64.AppImage \
  --runtime /inputs/tools/runtime-x86_64 \
  --notices /work/merged-notices --license /work/LICENSE \
  --release-record /work/release-record.json --output /work/assembly
```

The output parent must exist and the output itself must not exist. Supply immutable
inputs throughout assembly. The caller owns executable permissions after pinned
hash checking; the assembler never chmods host inputs. Only the copied AppRun gets
launcher permissions. Its unchanged exec behavior preserves PID, arguments and
environment. Tool extraction environment applies only to appimagetool.

## Trust and failure boundaries

- `--release-record` is the JSON returned by host `release_version.inspect`.
  Exact structure, canonical tag/version agreement and hash formats are checked;
  this does not prove Git ancestry, source identity or installed-build identity.
- `MarsDisplay.AppDir/release.json` retains that record and measured executable,
  appimagetool and runtime SHA256 values. It makes no passed-test claims.
- Copying preserves contained relative aliases and payload modes; escaping,
  dangling and looping links or special files are rejected before output creation.
- Pass only merged notices to `--notices`, not the separate downloaded tools tree.
  Presence is not legal clearance. Real native attribution and checks belong to
  the integrating build, as do host canonical inspection and smoke verification.
- Input rejection creates no output. Once assembly starts, failures retain the
  AppDir and any tool log/image for diagnosis. Never retry into that directory.
- Existing `release_assets.py` owns versioned naming, support ZIP and checksums.
  The legacy prototype assembler and pinned tool registry are unchanged.
