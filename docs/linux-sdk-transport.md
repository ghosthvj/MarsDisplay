# Stream the Linux SDK build

`packaging/linux/sdk_transport.py` provides the host-side Python API:

```python
result = run_sdk(source, release_record_path, image, output, sudo=False)
```

Supply curated, Git-less source containing `packaging/linux/build_sdk.py`, the
host-verified canonical release record, and an already-built SDK image. There is
no standalone CLI or image download: Docker uses `--pull=never`. The integrating
host remains responsible for image identity and Git provenance.

Inputs stay unchanged; output must be fresh, with an existing unlinked parent and
no overlap with source/record. The API streams source and record through stdin,
never a host mount. Docker runs UID/GID 10001 with read-only rootfs, all capabilities
dropped, no network, and `/work`/`/tmp` tmpfs. No USB/display/home/socket mounts,
root application execution or sandbox bypass is introduced. `sudo=True` explicitly
wraps only the Docker client with `sudo -n`; it never changes the container user.

Success returns `output/extracted/result`. Recovery accepts only `onedir/`,
`notices/` and `build.json`. Before extraction it checks the entire tar namespace,
case/path conflicts, supported file types, contained file aliases (including
chains), and required outputs. Directory, dangling, looping, absolute and escaping
aliases reject. The returned record must match the provided release, installed
version, original SDK UID, completed checks and measured executable digest.
Extraction uses Python's data filter as an additional boundary.

Failures retain private `sdk-input.tar`, `sdk-output.tar` and `docker.log`; nothing
is retried or removed. A failed SDK command may return its private `build.log`
inside the output tar, but the API never extracts failed results. Validation
failure creates no extraction directory; I/O failure during extraction may retain
partial private output. Never publish transport diagnostics or treat a partial
result as qualified. A successful transport validates its declared boundaries,
not legal clearance or a cryptographic build attestation.
