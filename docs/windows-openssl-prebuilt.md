# Windows OpenSSL: use the pinned prebuilt pair

Windows packaging uses FireDaemon OpenSSL **3.5.9 x64**, not whichever DLLs happen
to be installed on the runner. There is no OpenSSL compilation, Perl/NASM setup,
two-build comparison or automatic native-policy approval.

## Prepare once, then package

After installing the project's pinned Windows x64 SDK:

```powershell
python -B packaging/openssl_prebuilt.py
python packaging/build_portable.py
```

Preparation identifies its HTTP client as `MarsDisplay-build/1.0`, downloads the
fixed 43 MB vendor ZIP, verifies its published SHA256,
then checks and extracts only `x64/bin/libcrypto-3-x64.dll` and
`x64/bin/libssl-3-x64.dll`. Windows Authenticode must report `Valid` with signer
`FireDaemon Technologies Limited`; merely parsing a certificate is insufficient.
The Windows PowerShell child omits inherited `PSModulePath` so it reconstructs its
own compatible module paths. This follows Microsoft's guidance for
[PowerShell 7 → Python → Windows PowerShell launches](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_psmodulepath#starting-windows-powershell-from-powershell-7).
The parent environment, PATH and signature/trust requirements remain unchanged.
An existing output directory is never overwritten. Reuse a successfully prepared
directory for subsequent builds: the hook rechecks both DLL hashes each time.

For an already downloaded ZIP, use `--archive PATH`; the same size/hash checks
apply. `--output PATH` selects a new preparation directory; normal builders use
only the default project directory `build/openssl-prebuilt`. No ambient fallback,
DLL renaming or global PATH modification is performed. A preparation failure
returns nonzero; do not proceed to packaging after it. Failure messages identify
only a fixed operation phase, exception type and HTTP status when available.
Signature failures may report allowlisted DLL/status pairs, never raw subprocess
errors, certificate subjects, private paths or environment contents.

Both portable and USB grouping workflows prepare this input before PyInstaller.
The builder commands themselves still perform no downloads. The local QtNetwork
hook preserves `add_qt6_dependencies` and replaces only ambient OpenSSL collection.
CPython's separate unsuffixed DLLs, Qt traversal, native scope/PE/RECORD checks,
source/notices and the zero-skip Windows application gate remain unchanged.

## What establishes this association

See [retained provider evidence](../third_party/firedaemon-openssl/README.md).
The provider publishes the ZIP checksum and source release identifier;
`version.txt`, DLL hashes, AMD64 PE facts and 3.5.9.0 versions agree. The reviewed
build configuration explains HYBRIDCRT and its static MSVC/dynamic UCRT linkage.
Only the two reviewed suffixed entries were changed in the static native policy.

The mutable script snapshot is not cryptographic proof of the historical recipe.
Its upstream test command is commented out: no provider-test success or reproduced
binary result is claimed. Existing policy requires reviewed supplier/source
association, not rebuilding vendor binaries. This remains distinct from legal
certification, ongoing source availability and hardware acceptance.
