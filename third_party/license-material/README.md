# Versioned upstream license material

These files are unmodified upstream legal texts and leading source-file
copyright/license headers. `provenance.json` records their exact source commits,
URLs, versions and SHA-256 digests. There are 56 registered raw inputs (the
original 52 plus four winldd inputs), or 58 shared files including this README
and the registry. They are not executable dependencies.

## Scope

- **pyserial 3.5:** the complete upstream `LICENSE.txt` was checked against both
  the commit-pinned file and the PyPI source archive, whose published SHA-256
  was independently verified against downloaded archive bytes.
- **Qt for Python 6.12.0:** the release's complete `LICENSES` directory and
  selected binding copyright headers. The recorded Python package mappings
  identify binding material, not complete native Qt/WebEngine/Pdf coverage.
- **qtbase 6.12.0:** upstream license texts and selected source copyright headers,
  retained as additional material for native-payload qualification.
- **Playwright core 1.64.0-beta-1791568591000 / winldd 1007:** complete root
  LICENSE/NOTICE, `browser_patches/winldd/PrintDeps.cpp` and BUILD_NUMBER from
  official npm gitHead `1b2924712024804936dbcfe9fabaa655d52325e5`. Root texts
  byte-match the installed driver; the source retains Julien Waechter's complete
  MIT text and Microsoft's Apache-2.0 header. BUILD_NUMBER is provenance only,
  not a license. The Windows tool is `winldd-1007/PrintDeps.exe`, not `winldd.exe`.
  Python Playwright 1.64.0 does not identify the stable JavaScript 1.64.0 tag;
  the actual embedded core beta and its source commit are checked separately.

The Qt for Python source archive's digest is the value published by Qt; its
archive bytes were not downloaded during this retrieval. Commit-pinned legal
texts were downloaded directly from Qt's official source server.

## Collection rules

The packaging collector must use an explicit package/version mapping and verify
file hashes before using this material as a fallback for incomplete wheel
metadata. Missing, modified, unsafe or unmapped material must fail collection.
Do not substitute a generic license name for missing text or copy one version's
mapping to an unverified package version.

The four winldd records have `packages: []`: supplementary tool-specific material
must never satisfy a missing whole-Playwright distribution license. The vendor
collector alone may use them when local winldd legal files are absent and the
exact core identity, tool revision/executable, installed root texts and immutable
source/provenance hashes match. Genuine installed local texts take precedence;
empty, broken, linked or altered inputs fail instead of selecting fallback.
These records do not qualify Qt or certify license compatibility.

The commercial-license reference is preserved from upstream; it grants no
commercial rights. Alternative license texts are retained without representing
that all alternatives have been granted or selected for every component.

The actual Windows payload still needs exact binary/component provenance and
corresponding-source directions. These source materials alone are not a legal
certification, a native-binary attribution audit, or permission to distribute.
