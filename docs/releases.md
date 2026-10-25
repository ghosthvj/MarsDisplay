# Publish a Windows release

1. Commit the intended version in `pyproject.toml` to `main`, for example
   `0.2.0rc7` or `0.2.0`. Use a new version for every release.
2. Open **Actions → Publish Windows release → Run workflow**, select **main**,
   then run it. This explicitly requests public publication, not a dry run.
3. After success, open **Releases** and download the complete portable ZIP and
   its `.sha256` file. Do not distribute the EXE separately from its resources.

The workflow uses the exact triggering commit, not a later moving main head.
It runs the existing Windows tests (zero skips), native build, license/source
qualification and packaged smoke through the reusable portable workflow.
Only the publisher has write permission. It checks ZIP/checksum, payload hashes,
version and source commit before creating `v<version>` at that exact commit.

A temporary draft holds uploads while their names, sizes and SHA256 digests and
the tag commit are checked. The workflow then publishes automatically. `rc`
versions are prereleases; numeric `X.Y.Z` versions are regular releases.
The ZIP includes corresponding application/build source and notices; preserve
all bundled source-access directions when redistributing it.

Existing tags/releases/assets are never overwritten or deleted. A failed run
may leave a tag or draft, or an uncertain final state after a network error.
Inspect GitHub before any manual rerun; the workflow does not retry or remove
these resources. A retained draft is not a completed public release.

For local development, `python packaging/release.py --help` describes the
`plan` and `publish --artifacts <directory>` commands. Publication requires the
GitHub Actions manual-main context and a scoped GitHub CLI token. Tests mock
GitHub and do not create releases. The action itself must be on the default
branch before GitHub offers its manual Run workflow button.
