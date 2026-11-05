# FireDaemon OpenSSL 3.5.9 association

This directory retains provider material separately from the strict upstream-raw
registry in `../native-material`. These scripts are evidence, **not executed by
MarsDisplay's build**. `provenance.json` records exact URLs, archive identity and
hashes of the unmodified snapshots, version and license.

## Reviewed evidence

- [Provider documentation](https://kb.firedaemon.com/support/solutions/articles/4000121705)
  publishes the 3.5.9 ZIP checksum and `openssl-3.5.9-0-g45e844fa2a` source identifier,
  states that sources come directly from OpenSSL's official repository and permits
  redistribution of its binary distribution under the OpenSSL license.
- The [versioned ZIP](https://download.firedaemon.com/FireDaemon-OpenSSL/openssl-3.5.9.zip)
  has publisher SHA256 `76da391395be029b44794857b9ff380255e02a0960a98314cd3f6a6816d82696`.
  Its `version.txt` and `LICENSE.txt` are retained verbatim.
- `x64/bin/libcrypto-3-x64.dll`: SHA256
  `5268a29c9a5e353770b894f3dbd148ee8c60971aa1620713c54d8e56563d0aca`, 7,225,016 bytes.
- `x64/bin/libssl-3-x64.dll`: SHA256
  `00520a8ca63ec624969742aa04e7db2af94ba0d3f5fe204cbd114b4ec1f24752`, 1,500,856 bytes.
- Both inspected DLLs are AMD64 with file/product version `3.5.9.0`. SSL imports
  the suffixed crypto DLL; other observed imports are Windows/UCRT.
- Complete upstream source is the immutable commit
  `45e844fa2a14ec92d146bd8f5778ac130b6625fb` archive in `provenance.json`; existing
  native material retains its upstream version and license proofs.

## Build configuration and limits

`mkopenssl-35.cmd` and `50-win-hybridcrt.conf` are verbatim reviewed snapshots from
[the mutable provider script ZIP](https://download.firedaemon.com/FireDaemon-OpenSSL/mkopenssl.zip),
measured SHA256 `8f12145e3fe430709e6ead4f974960546d8ff06a19acbcd513e6540922863316`.
This measured hash is not a publisher-signed checksum or historical attestation.

The script selects the latest stable-branch tag, not a hardcoded 3.5.9 commit.
The release association instead rests on the provider's version-specific source
declaration and distributed version marker. x64 uses `VC-WIN64A-HYBRIDCRT` with
`no-ssl3 no-zlib no-comp no-autoload-config no-makedepend`, explicit installation
paths and `/MP`. The custom target replaces `/MD[d]` with `/MT[d]`, excludes static
UCRT and links dynamic UCRT. That custom configuration must accompany the source
association; it is not an upstream OpenSSL blob. It has no explicit license header;
no additional license grant for it is invented here.

No cryptographic implementation patch is applied in these inspected scripts;
this does not prove an empty historical patch set. The script does not show how
the custom configuration enters the search path, and its test invocation is
commented out. We do not claim provider tests passed, a reproduced binary build,
or cryptographically proven historic inputs. Parsed signer names alone are not
signature validation: Windows preparation separately requires valid Authenticode.

Retain these files with `source/` and maintain complete source access alongside
binary distribution. Provider association and byte checks are not legal certification.
