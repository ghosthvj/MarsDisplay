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

## Remaining integration

The Windows recipe, exact tool pins, narrow QtNetwork selection hook and candidate
workflow are not integrated yet. Before static admission, require two clean builds
at different workspace paths, upstream test results, matching DLL bytes, reviewed
source/tool/recipe evidence and packaged TLS checks. Preserve the CPython OpenSSL
pair and normal Qt dependency traversal. Never replace static expectations with
hashes observed during packaging, or fall back to an ambient PATH provider.
