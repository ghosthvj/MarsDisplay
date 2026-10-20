$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $root
$csc = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$framework = Split-Path $csc
$references = @('System.dll', 'System.Core.dll', 'System.Management.dll')
foreach ($file in @($csc) + @($references | ForEach-Object { Join-Path $framework $_ })) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required inbox Framework file missing: $file" }
}
Write-Host "Compiler: $csc"
Write-Host "OS: $([Environment]::OSVersion.VersionString); image: $env:ImageOS $env:ImageVersion"
$out = Join-Path $root 'build/native-usb-probe'
# Refuse reuse: never accidentally package an old executable or old evidence.
if (Test-Path -LiteralPath $out) { throw "Output already exists: $out. Use a fresh checkout for a qualified build." }
New-Item -ItemType Directory -Path $out | Out-Null
$package = Join-Path $out 'package'
New-Item -ItemType Directory -Path $package | Out-Null
$results = [Collections.Generic.List[object]]::new()

function Invoke-Bounded([string] $File, [string[]] $Arguments, [string] $InputText = '', [int] $Timeout = 30000) {
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $File
    # All arguments are repository-controlled paths or fixed test inputs, never shell commands.
    $info.Arguments = (($Arguments | ForEach-Object { '"' + $_ + '"' }) -join ' ')
    $info.UseShellExecute = $false
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $p = [Diagnostics.Process]::new()
    $p.StartInfo = $info
    try {
        if (-not $p.Start()) { throw "Could not start $File" }
        $stdout = $p.StandardOutput.ReadToEndAsync()
        $stderr = $p.StandardError.ReadToEndAsync()
        $p.StandardInput.Write($InputText)
        $p.StandardInput.Close()
        if (-not $p.WaitForExit($Timeout)) {
            # Kill this process tree only; the production supervisor also owns a kill-on-close job.
            $p.Kill($true)
            if (-not $p.WaitForExit(5000)) { throw "Termination unconfirmed: $File" }
            throw "Timed out: $File $($info.Arguments)"
        }
        if (-not $stdout.Wait(5000) -or -not $stderr.Wait(5000)) { throw "Output handles did not close: $File" }
        $record = [ordered]@{ file = [IO.Path]::GetFileName($File); arguments = $Arguments; exit = $p.ExitCode; stdout = $stdout.Result; stderr = $stderr.Result }
        $results.Add($record)
        Write-Host "$($record.file) $($Arguments -join ' '): exit $($record.exit)"
        if ($record.stdout) { Write-Host $record.stdout }
        if ($record.stderr) { Write-Host $record.stderr }
        return $record
    } finally { $p.Dispose() }
}
function Assert-Result($Result, [int] $Code, [string] $Stdout, [string] $Stderr) {
    if ($Result.exit -ne $Code -or $Result.stdout -cne $Stdout -or $Result.stderr -cne $Stderr) {
        throw "Unexpected public result: $($Result | ConvertTo-Json -Depth 5 -Compress)"
    }
}
function Hash([string] $Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
$fixture = Join-Path $PSScriptRoot 'pattern.rgb565'
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'pattern.json') -Raw | ConvertFrom-Json
if ((Get-Item $fixture).Length -ne 307200 -or (Hash $fixture) -ne '8cbbb7e39485e211548a4f3f448ca14eeb9358286e5eadf7079a324fdc97ed1d' -or
    $manifest.payload_sha256 -ne (Hash $fixture) -or $manifest.png_sha256 -ne (Hash (Join-Path $PSScriptRoot 'pattern.png'))) {
    throw 'Canonical fixture hash/length mismatch.'
}
$app = Join-Path $package 'UsbScreenProbe.exe'
$tests = Join-Path $out 'ProbeTests.exe'
$common = @('/nologo', '/target:exe', '/platform:x64', '/optimize+', '/warnaserror+', '/langversion:5',
    "/resource:$fixture,pattern.rgb565") + @($references | ForEach-Object { '/reference:' + (Join-Path $framework $_) })
$sources = @((Join-Path $PSScriptRoot 'Program.cs'), (Join-Path $PSScriptRoot 'Probe.cs'))
# The inbox Framework compiler requires output/target options before source paths.
$r = Invoke-Bounded $csc ($common + @('/main:UsbScreenProbe.Program', "/out:$app") + $sources)
Assert-Result $r 0 '' ''
$r = Invoke-Bounded $csc ($common + @('/main:UsbScreenProbe.ProbeTests', "/out:$tests") + $sources + @((Join-Path $PSScriptRoot 'ProbeTests.cs')))
Assert-Result $r 0 '' ''
$r = Invoke-Bounded $tests @()
if ($r.exit -ne 0 -or $r.stderr -ne '' -or $r.stdout -notmatch '\APASS [0-9]+ native checks; no USB opened\.\r\n\z') {
    throw "Native harness failed: $($r | ConvertTo-Json -Depth 5)"
}
$nl = "`r`n"
$banner = "UsbScreenProbe 1.0.0$nl"
$help = "Usage: UsbScreenProbe.exe [--help | --list | --self-test | --port COMn]$nl" +
    "No arguments: choose a current COM port interactively. Sending requires typed SEND COMn.$nl" +
    "90-second total worker budget includes input, inventory, transfer and cleanup. No retries.$nl"
$argumentError = "E2: Invalid arguments. Use an explicit COM number (COM1 or higher).$nl"
$inventoryError = "E3: Serial inventory unavailable. Check Windows Device Manager and reconnect; do not install drivers or elevate for this probe.$nl"
$r = Invoke-Bounded $app @('--help')
Assert-Result $r 0 ($banner + $help) ''
$r = Invoke-Bounded $app @('--self-test')
Assert-Result $r 0 ($banner + "PASS: embedded pattern and protocol: 122 writes, 307222 bytes; no USB opened.$nl") ''
$r = Invoke-Bounded $app @('--unknown')
Assert-Result $r 2 '' ($argumentError + $help)
$r = Invoke-Bounded $app @('--port', 'COM0')
Assert-Result $r 2 '' ($argumentError + $help)
$r = Invoke-Bounded $app @('--owned-worker', 'untrusted')
Assert-Result $r 2 '' ($argumentError + $help)
# Inventory is passive. A runner need not expose Win32_SerialPort or any device.
$list = Invoke-Bounded $app @('--list') '' 100000
if ($list.exit -eq 3) { Assert-Result $list 3 $banner $inventoryError }
elseif ($list.exit -ne 0 -or $list.stderr -ne '' -or -not $list.stdout.StartsWith($banner)) { throw 'Unexpected passive inventory result.' }
$cancel = Invoke-Bounded $app @() '' 100000
if ($cancel.exit -eq 3) { Assert-Result $cancel 3 $banner $inventoryError }
else {
    # Same passive inventory must be reported, then EOF cancels without a port choice/open.
    Assert-Result $cancel 0 ($list.stdout + "Choose COMn (Enter cancels): Cancelled; no port opened.$nl") ''
}

# Evidence and source are packaged only after every native test has passed.
$commitResult = Invoke-Bounded 'git' @('rev-parse', 'HEAD')
if ($commitResult.exit -ne 0 -or $commitResult.stderr -ne '') { throw 'Cannot identify source commit.' }
$sourceCommit = $commitResult.stdout.Trim()
$dirty = Invoke-Bounded 'git' @('status', '--porcelain', '--untracked-files=no')
Assert-Result $dirty 0 '' ''
$sourcePaths = @('tools/windows-usb-probe/Program.cs', 'tools/windows-usb-probe/Probe.cs',
    'tools/windows-usb-probe/ProbeTests.cs', 'tools/windows-usb-probe/build.ps1', 'tools/windows-usb-probe/README.md',
    'tools/windows-usb-probe/pattern.rgb565', 'tools/windows-usb-probe/pattern.png', 'tools/windows-usb-probe/pattern.json',
    '.github/workflows/windows-usb-probe.yml', 'tests/test_native_probe_fixture.py', 'LICENSE')
$sourceHashes = [ordered]@{}
foreach ($path in $sourcePaths) { $sourceHashes[$path] = Hash (Join-Path $root $path) }
$compilerHashes = [ordered]@{}
foreach ($file in @($csc) + @($references | ForEach-Object { Join-Path $framework $_ })) { $compilerHashes[$file] = Hash $file }
$evidence = [ordered]@{
    code_unit = 'N1 / S1-S4 native USB diagnostic'; source_commit = $sourceCommit; version = '1.0.0'
    os = [Environment]::OSVersion.VersionString; image_os = $env:ImageOS; image_version = $env:ImageVersion
    compiler = $csc; compiler_version = (Get-Item $csc).VersionInfo.FileVersion; compiler_fingerprints = $compilerHashes
    source_hashes = $sourceHashes; exe_sha256 = Hash $app; tests = $results.ToArray()
    limitations = 'No physical USB open or rendering verified. WMI chooser/driver compatibility remains owner acceptance.'
}
$evidence | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $package 'nativeverification.json') -Encoding utf8
foreach ($file in @('README.md', 'pattern.png', 'pattern.json')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $package }
Copy-Item -LiteralPath (Join-Path $root 'LICENSE') -Destination $package
Add-Type -AssemblyName System.IO.Compression.FileSystem
$sourceZip = [IO.Compression.ZipFile]::Open((Join-Path $package 'source.zip'), [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($path in $sourcePaths) { [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($sourceZip, (Join-Path $root $path), $path) | Out-Null }
} finally { $sourceZip.Dispose() }
Get-ChildItem -LiteralPath $package -File | Sort-Object Name | ForEach-Object { "$(Hash $_.FullName)  $($_.Name)" } |
    Set-Content -LiteralPath (Join-Path $package 'SHA256SUMS') -Encoding ascii
$zip = Join-Path $out 'UsbScreenProbe-1.0.0-Windows-x64.zip'
[IO.Compression.ZipFile]::CreateFromDirectory($package, $zip)
"$(Hash $zip)  $([IO.Path]::GetFileName($zip))" | Set-Content -LiteralPath "$zip.sha256" -Encoding ascii
Write-Host "Qualified USB-free native artifact: $zip"
