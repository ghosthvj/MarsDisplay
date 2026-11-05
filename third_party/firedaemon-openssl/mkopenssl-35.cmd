@echo off
verify other 2>nul
setlocal enableextensions
if errorlevel 1 echo unable to enable extensions & exit /b 1


set cwd=%CD%\
set scriptdir=%~dp0

set openssl-src=%CD%
set openssl-dst=%openssl-src%\..\openssl-3.5
set tmp-install-destdir-path=%openssl-src%\.destdir


call "%scriptdir%..\toolbox\utilities\deployment\vswhere.bat" ^:determine_vsinstalldir
if errorlevel 1 exit /b errorlevel
:: save VSINSTALLDIR because vcvarsall.bat will overwrite it
set "saved-VSINSTALLDIR=%VSINSTALLDIR%"


:: sanity checks
if not exist "%saved-VSINSTALLDIR%" echo Visual Studio not found & exit /b 1


if not exist "%openssl-dst%" md "%openssl-dst%"

call :checkout
if errorlevel 1 echo getting openssl source code failed & exit /b 1

call :collect-sundries
if errorlevel 1 echo creating version.txt failed & exit /b 1

call :build-x64
if errorlevel 1 exit /b 1

call :build-x86
if errorlevel 1 exit /b 1

call :build-arm64
if errorlevel 1 exit /b 1

REM call :test-x64
REM if errorlevel 1 exit /b 1

exit /b 0


:: sets the following variables:
:: - toolset
:: - installdir
:: - commoninstalldir
:: - relative_installdir
:: - relative_commoninstalldir
:setvars
    if "%Platform%"=="x64" (
        set toolset=VC-WIN64A-HYBRIDCRT
        set "installdir=%ProgramFiles%\FireDaemon OpenSSL 3.5"
        set "commoninstalldir=%CommonProgramFiles%\FireDaemon SSL 3.5"
        set CL=/MP
    )
    if "%Platform%"=="x86" (
        set toolset=VC-WIN32-HYBRIDCRT
        if defined ProgramFiles^(x86^) (
            set "installdir=%ProgramFiles(x86)%\FireDaemon OpenSSL 3.5"
        ) else (
            set "installdir=%ProgramFiles%\FireDaemon OpenSSL 3.5"
        )
        :: share SSL stuff with x64
        if defined CommonProgramW6432 (
            set "commoninstalldir=%CommonProgramW6432%\FireDaemon SSL 3.5"
        ) else (
            set "commoninstalldir=%CommonProgramFiles%\FireDaemon SSL 3.5"
        )
        set CL=/MP
    )
    if "%Platform%"=="arm64" (
        REM set toolset=VC-WIN64-ARM
        set toolset=VC-CLANG-WIN64-CLANGASM-ARM
        set "installdir=%ProgramFiles%\FireDaemon OpenSSL 3.5"
        set "commoninstalldir=%CommonProgramFiles%\FireDaemon SSL 3.5"
    )

    for %%d in ("%installdir%") do set relative_installdir=%%~pnxd
    for %%d in ("%commoninstalldir%") do set relative_commoninstalldir=%%~pnxd

    exit /b 0


:checkout
    setlocal

    if exist "%openssl-src%\.git" (
        pushd "%openssl-src%"
        git reset --hard
        git submodule foreach --recursive git reset --hard
        git fetch & git switch openssl-3.5
        git pull
        if errorlevel 1 endlocal & exit /b 1
    ) else (
        git clone --recurse-submodules -b openssl-3.5 https://github.com/openssl/openssl.git "%openssl-src%"
        if errorlevel 1 endlocal & exit /b 1
        pushd "%openssl-src%"
    )

    for /f "delims=" %%g in ('git describe --always --tag --first-parent "--abbrev=0"') do set recenttag=%%g
    git checkout "%recenttag%" & git submodule update --init --recursive
	if errorlevel 1 endlocal & exit /b 1

    endlocal & exit /b 0


:build-x86
    setlocal

    rem add `-vcvars_ver=14.14` if you need to use specific toolset 14.14 (VC 15.7)
    call "%saved-VSINSTALLDIR%VC\Auxiliary\Build\vcvarsall.bat" x64_x86
    
    call :setvars
    call :make
    if errorlevel 1 echo building openssl x86 failed & endlocal & exit /b 1
    call :sign-and-collect
    if errorlevel 1 echo signing or collecting openssl x86 failed & endlocal & exit /b 1

	endlocal & exit /b 0


:build-arm64
    setlocal

    rem add `-vcvars_ver=14.14` if you need to use specific toolset 14.14 (VC 15.7)
    call "%saved-VSINSTALLDIR%VC\Auxiliary\Build\vcvarsall.bat" amd64_arm64

    call :setvars
    call :make
    if errorlevel 1 echo building openssl arm64 failed & endlocal & exit /b 1
    call :sign-and-collect
    if errorlevel 1 echo signing or collecting openssl arm64 failed & endlocal & exit /b 1

	endlocal & exit /b 0


:build-x64
    setlocal

    rem add `-vcvars_ver=14.14` if you need to use specific toolset 14.14 (VC 15.7)
    call "%saved-VSINSTALLDIR%VC\Auxiliary\Build\vcvarsall.bat" x64

    call :setvars
    call :make
    if errorlevel 1 echo building openssl x64 failed & endlocal & exit /b 1
    call :sign-and-collect
    if errorlevel 1 echo signing or collecting openssl x64 failed & endlocal & exit /b 1
    call :make-and-collect-ssldirs
    if errorlevel 1 echo building ssldirs failed & endlocal & exit /b 1

	endlocal & exit /b 0


:: note: requires VS build environment
:make
    setlocal

    for /d %%n in ("%openssl-src%\.build%Platform%" "%tmp-install-destdir-path%\%Platform%") do rmdir /q /s "%%~fn" 2>nul
    timeout /t 1
    mkdir "%openssl-src%\.build%Platform%"
    if errorlevel 1 echo can't create directory & endlocal & exit /b 1

    cd "%openssl-src%\.build%Platform%"
    perl ..\Configure %toolset% no-ssl3 no-zlib no-comp no-autoload-config no-makedepend --prefix="%installdir%" --openssldir="%commoninstalldir%"
    if errorlevel 1 endlocal & exit /b 1
    
    nmake
    if errorlevel 1 endlocal & exit /b 1
    
    endlocal & exit /b 0


:: note: requires VS build environment
:sign-and-collect
    setlocal

    cd "%openssl-src%\.build%Platform%"
    nmake install_sw DESTDIR="%tmp-install-destdir-path%\%Platform%"
    if errorlevel 1 endlocal & exit /b 1

    cd "%tmp-install-destdir-path%\%Platform%%relative_installdir%"
    signtool.exe sign /v /fd sha256 /n "FireDaemon Technologies Limited" /a /du "https://www.firedaemon.com" /tr http://timestamp.comodoca.com/rfc3161 /td sha256 lib\engines-3\*.dll lib\ossl-modules\*.dll bin\*.dll bin\*.exe
    if errorlevel 1 endlocal & exit /b 1

    :: move include,lib,bin subdirectories under platform-specific subdirectories; 
    :: note: the include folder also contains platform-specific items like CPP definitions
    cd "%openssl-dst%" 
    if exist "%Platform%" rd /s /q %Platform% 
    mkdir %Platform% 
    for /d %%d in ("%tmp-install-destdir-path%\%Platform%%relative_installdir%") do ( 
        xcopy "%%~d" %Platform% /y /s /e /k /i 
    ) 
    if errorlevel 1 endlocal & exit /b 1

	endlocal & exit /b 0


:: note: requires VS build environment
:make-and-collect-ssldirs
    setlocal

    cd "%openssl-src%\.build%Platform%"
    nmake install_ssldirs DESTDIR="%tmp-install-destdir-path%"
    if errorlevel 1 endlocal & exit /b 1
    
    cd "%openssl-dst%" 
    if exist ssl rd /s /q ssl 
    mkdir ssl 
    xcopy "%tmp-install-destdir-path%\%relative_commoninstalldir%" ssl /y /s /e /k /i 
    if errorlevel 1 endlocal & exit /b 1

	endlocal & exit /b 0


:: note: requires git to be in PATH
:collect-sundries
    setlocal
    set ret=0

    cd "%openssl-src%"
    git describe --always --tag --long --first-parent --dirty > "%openssl-dst%\version.txt"
    if errorlevel 1 set ret=1
    xcopy LICENSE.txt "%openssl-dst%" /f /y
    if errorlevel 1 set ret=1

    endlocal & exit /b %ret%


:test-x64
    setlocal

    call "%saved-VSINSTALLDIR%VC\Auxiliary\Build\vcvarsall.bat" x64

    call :setvars
    cd "%openssl-src%\.build%Platform%"
    nmake test
    if errorlevel 1 endlocal & exit /b 1

    endlocal & exit /b 0
