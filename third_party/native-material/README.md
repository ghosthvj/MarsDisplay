# Pinned native-source policy — offline binding, not legal certification

The default builder validates this root before compiling; it no longer consumes
manually populated build/native-material. Primary provenance/raw inputs are
unchanged. The exact registry and reviewed policy SHA256 are pinned in
packaging/native_material.py; changing either requires explicit source review.
No downloader, automatic legal approval or public override exists.

## Reviewed associations

| Policy scope | Source basis |
| --- | --- |
| 5 PySide binding files | pyside/pyside-setup f50facb83fc3dc5f3240c854668c7a6dd93871b2 |
| 4 imageformat plugins | qt/qtimageformats dc13f2fbff1d579cfb2eb2d9092e3563b4d05b8e |
| 18 Qt libraries/plugins | qt/qtbase 025bdad181de241e81bf853c8a2d7bf3d19261a9 |
| Supplemental Shiboken, 2 files | Same full PySide source, including Shiboken copyrights/terms |
| Supplemental outer SSL/crypto, 4 DLLs | OpenSSL3.5.5 67b5686b4419b4cb8caa502711c41815f5279751 and 3.5.9 45e844fa2a14ec92d146bd8f5778ac130b6625fb |

Each Qt/PySide6.12.0 source claim has a genuine annotated-tag commit reference.
OpenSSL release references and VERSION.dat are retained separately from licenses.
Explicit policy paths/hashes/PE facts/RECORD associations were curated from the
old actual Windows39038363658 inventory. No builder code reads that diagnostic;
every build must measure current facts independently, then the v2 gate measures
again. A basename or wheel owner version is not upstream version proof.

The 233 origin records/204 unmodified content-addressed files retain complete
module notice supersets: actual copyrights, conditional QtUsage, versions,
LicenseFile inputs, extra licenses, patents and authors. For example qjpeg's Qt
attribution names bundled libjpeg-turbo and its avoid/system alternatives; qwebp
names bundled libwebp if no system copy is found. Keeping their notices does not
assert every optional library/example in these full modules was compiled.
Original alternative/commercial terms remain raw notices, not a commercial grant.
The GPL3 application uses the compatible open-source route, preserving third-party
conditions. No Microsoft DLL redistribution permission is inferred from an EULA;
Microsoft runtime is external and optional Mesa must be absent, not relabeled.

## Source access and review boundary

The staged root README.txt points to notices/native/SOURCE-ACCESS.txt. That file
lists full immutable module source archives, including upstream build/configuration
and vendored code; application and local hooks are included in source/. Raw inputs,
registry, policy and this guide travel both with source and hashed notices.
Dynamic unpacked DLLs remain replaceable; no DRM/EULA overrides GPL/LGPL rights.
For GPLv3 section 6(d), keep equivalent source access next to binary access and
maintain it for the required period; mirror exact complete sources if upstream
access ceases. CI artifact expiry does not excuse source obligations.

Structural integrity plus curated association is not legal certification or
proof of ongoing source availability. Independent review must examine policy
semantics/notice sufficiency, not merely hashes. Actual Windows external-profile
assembly, fresh facts, provisioner, v2 qualification and ZIP remain unproved by
source tests; Windows11 acceptance is separate. Unknown RECORD owners elsewhere
are not automatically unlicensed. Existing CPython generated Windows LICENSE,
Node/Chromium/FFmpeg/winldd/Python-package notices and PyInstaller exception remain
mandatory; supplemental components do not replace that collection.
