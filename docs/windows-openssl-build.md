# Controlled Windows OpenSSL build

The controlled build is being introduced in stages. Native DLL admission still
uses the existing static policy; measuring a new input or output does not approve it.
The MySQL-provided DLLs remain unqualified for corresponding-source provenance.

## Pinned source input

`packaging/openssl_inputs.py` accepts only this OpenSSL 3.5.9 snapshot:

- Commit: `45e844fa2a14ec92d146bd8f5778ac130b6625fb`
- URL: <https://github.com/openssl/openssl/archive/45e844fa2a14ec92d146bd8f5778ac130b6625fb.tar.gz>
- Archive SHA-256: `f54250b21795bb01240f3f9b42c384868d04460e339e39275aaaf93487f2d903`
- `VERSION.dat` SHA-256: `6dae52ea88792578bc22594ec2a0a26b2cf675b925ce81ce8792a1ccdf10cdb5`

The archive digest was measured from the upstream HTTPS commit archive; it is not
an upstream detached-signature claim. The version-file digest matches the already
retained native-material record. There are no source patches in this input stage.

Extraction verifies the same in-memory archive bytes it consumes, validates all
member paths and size limits before creating the destination, and refuses existing
output, links, Windows path aliases, special entries and file/directory conflicts.
It does not download inputs, run their contents, or modify native policy.

## Tool input measurements

`fingerprint(directory)` hashes relative file names, sizes and contents in a stable
order. Its result contains only an aggregate digest and file/byte counts, not
absolute paths or environment variables. Linked inputs, unreadable directories
and oversized trees fail rather than yielding an incomplete fingerprint.
A fingerprint is a measurement, not a supplier attestation or admission decision.

## Portable tool inputs

`packaging/openssl_tools.py` prepares only two explicitly pinned ZIP archives into
new directories. It verifies size, SHA-256, namespace, entry types, expansion bounds
and CRCs before writing. It never runs the extracted tools or consults PATH.

| Tool | Archive SHA-256 | Integrity evidence |
| --- | --- | --- |
| NASM 2.16.03 x64 | `3ee4782247bcb874378d02f7eab4e294a84d3d15f3f6ee2de2f47a46aa7226e6` | Measured official HTTPS archive; no retrieved publisher checksum/signature |
| Strawberry Perl 5.42.0.1 x64 portable | `a1cde185656cf307b51670eed69f648b9eff15b5c518cb136e027c628e650b71` | Publisher `https://strawberryperl.com/releases.json` |

Acquisition URLs and executable-relative paths are fixed in `TOOLS`. The NASM
bundled inside Strawberry differs from the selected NASM and must not substitute
for it. These are build tools, not payload files. Their pinned archive identity is
not evidence that a Windows compilation or reproducibility check has passed.

## Remaining integration

The Windows recipe, exact MSVC/SDK byte pins, narrow QtNetwork selection hook and
candidate workflow are not integrated yet. Before static admission, require two clean builds
at different workspace paths, upstream test results, matching DLL bytes, reviewed
source/tool/recipe evidence and packaged TLS checks. Preserve the CPython OpenSSL
pair and normal Qt dependency traversal. Never replace static expectations with
hashes observed during packaging, or fall back to an ambient PATH provider.
