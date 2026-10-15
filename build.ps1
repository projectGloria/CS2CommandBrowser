$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$packagedApp = Join-Path $PSScriptRoot 'portable-v1.1\CS2 Command Browser\CS2 Command Browser.exe'
if (Get-CimInstance Win32_Process -Filter "Name='CS2 Command Browser.exe'" | Where-Object { $_.ExecutablePath -eq $packagedApp }) {
    throw 'Close CS2 Command Browser v1.1 before rebuilding its package.'
}

if (-not (Test-Path -LiteralPath '.\.buildenv\Scripts\python.exe')) {
    python -m venv '.\.buildenv'
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python build environment.' }
}
$python = Join-Path $PSScriptRoot '.buildenv\Scripts\python.exe'
& $python -m pip install 'cmake==4.4.4' 'pyinstaller==6.22.3'
if ($LASTEXITCODE -ne 0) { throw 'Could not install the local build dependencies.' }

$extractorSource = Join-Path $PSScriptRoot 'vendor\DumpSource2'
if (-not (Test-Path -LiteralPath (Join-Path $extractorSource 'vendor\hl2sdk-cs2\public\tier0\convar.h'))) {
    if (-not (Test-Path -LiteralPath (Join-Path $extractorSource '.git'))) {
        throw 'The extractor dependency source is incomplete. Restore the full Source.zip contents.'
    }
    Push-Location -LiteralPath $extractorSource
    try {
        git submodule update --init --depth 1 vendor/hl2sdk-cs2 vendor/fmt vendor/spdlog vendor/json
        if ($LASTEXITCODE -ne 0) { throw 'Could not fetch the extractor dependencies.' }
    } finally { Pop-Location }
}

$cmake = Join-Path $PSScriptRoot '.buildenv\Scripts\cmake.exe'
& $cmake -S $extractorSource -B '.\build\extractor' -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE -ne 0) { throw 'Extractor configuration failed. Check that the Visual Studio C++ tools are installed.' }
& $cmake --build '.\build\extractor' --config Release --target DumpSource2-CS2 -j 4
if ($LASTEXITCODE -ne 0) { throw 'Extractor compilation failed.' }
New-Item -ItemType Directory -Path '.\tools' -Force | Out-Null
Copy-Item -LiteralPath '.\build\extractor\Release\DumpSource2-CS2.exe' -Destination '.\tools\DumpSource2-CS2.exe'
& $python '.\record_build.py'
if ($LASTEXITCODE -ne 0) { throw 'Could not record build provenance.' }

& $python -m unittest -v test_core.py
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
$binaryArgument = (Join-Path $PSScriptRoot 'tools\DumpSource2-CS2.exe') + ';tools'
$metadataArgument = (Join-Path $PSScriptRoot 'tools\extractor-build.json') + ';tools'
& $python -m PyInstaller --noconfirm --windowed --onedir --name 'CS2 Command Browser' --distpath '.\portable-v1.1' --workpath '.\build\pyinstaller' --specpath '.\build' --add-binary $binaryArgument --add-data $metadataArgument '.\app.py'
if ($LASTEXITCODE -ne 0) { throw 'Desktop app packaging failed.' }
& $python '.\package_source.py'
if ($LASTEXITCODE -ne 0) { throw 'Source and license packaging failed.' }
Write-Output 'Ready: portable-v1.1\CS2 Command Browser\CS2 Command Browser.exe'
