# Builds the app folder (PyInstaller) and the installer (Inno Setup).
#
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#
# Needs the project's .venv with the dev dependencies, and Inno Setup 6
# (winget install JRSoftware.InnoSetup). Result: installer-output\VarietyWin-Setup-<version>.exe

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Missing .venv - create it and run: pip install -e .[dev]" }

$version = & $python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
Write-Host "Building Variety for Windows $version"

# Absolute, because PyInstaller resolves these relative to the spec file's folder.
$resources = Join-Path $root "src\varietywin\resources"

& $python -m PyInstaller packaging\launcher.py `
    --name VarietyWin `
    --noconsole `
    --noconfirm `
    --hidden-import winrt.windows.foundation `
    --hidden-import winrt.windows.foundation.collections `
    --hidden-import winrt.windows.storage.streams `
    --clean `
    --icon "$resources\icon.ico" `
    --add-data "$resources;varietywin\resources" `
    --specpath build `
    --workpath build\pyinstaller `
    --distpath dist
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found - install it: winget install JRSoftware.InnoSetup" }

& $iscc "/DAppVersion=$version" packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

Get-ChildItem installer-output\VarietyWin-Setup-$version.exe | ForEach-Object {
    Write-Host ("Installer: {0} ({1:N1} MB)" -f $_.FullName, ($_.Length / 1MB))
}
