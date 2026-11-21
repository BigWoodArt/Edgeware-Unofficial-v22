# Builds the one-click Edgeware: dist\Edgeware\Edgeware.exe (+ app\ folder, + _internal\).
# Needs Python 3.12+ with Edgeware's requirements and pyinstaller installed:
#   py -m pip install -r edgeware\requirements.txt pyinstaller
# Options: -Zip also makes dist\Edgeware.zip.   -Python "3.14" picks the interpreter (default: py's default).
param([switch]$Zip, [string]$Python = "")

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $repo "dist\Edgeware"
$py = if ($Python) { @("py", "-$Python") } else { @("py") }

# Keep the user's data when rebuilding in place (packs and config must survive).
$keep = Join-Path $env:TEMP "edgeware_keep_data"
if (Test-Path "$dist\app\data") {
    if (Test-Path $keep) { Remove-Item $keep -Recurse -Force }
    Copy-Item "$dist\app\data" $keep -Recurse
}

Push-Location $repo
& $py[0] $py[1..($py.Length)] -m PyInstaller packaging\Edgeware.spec --noconfirm --distpath dist --workpath build\pyinstaller
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "PyInstaller failed" }
Pop-Location

# Edgeware's own files stay as plain files next to the exe.
$app = Join-Path $dist "app"
if (Test-Path $app) { Get-ChildItem $app -Exclude data | Remove-Item -Recurse -Force }
New-Item -ItemType Directory -Force $app | Out-Null
robocopy "$repo\edgeware" $app /E /XD __pycache__ .ruff_cache /XF EdgewareSetup.bat setup.sh debug.py *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null

# The stubs EdgewareSetup.bat normally writes. They run through Edgeware.exe (sys.executable).
foreach ($pair in @(@("edgeware", "MAIN"), @("panic", "PANIC"))) {
    @"
import subprocess
import sys
from src.paths import Process
subprocess.run([sys.executable, Process.$($pair[1])])
"@ | Set-Content -Encoding utf8 (Join-Path $app "$($pair[0]).pyw")
}

# Video engine: take it from a previous build/cache, else download it once.
$dllDest = Join-Path $app "data\libmpv-2.dll"
New-Item -ItemType Directory -Force (Split-Path $dllDest) | Out-Null
$cache = Join-Path $repo "build\libmpv-2.dll"
if (-not (Test-Path $cache)) {
    if (Test-Path "$keep\libmpv-2.dll") { Copy-Item "$keep\libmpv-2.dll" $cache }
    else {
        Write-Host "Downloading libmpv..."
        $tmp = Join-Path $env:TEMP "edgeware_mpv"
        New-Item -ItemType Directory -Force $tmp | Out-Null
        Invoke-WebRequest "https://7-zip.org/a/7zr.exe" -OutFile "$tmp\7zr.exe"
        Invoke-WebRequest "https://sourceforge.net/projects/mpv-player-windows/files/libmpv/mpv-dev-x86_64-20250420-git-3600c71.7z/download" -UserAgent "Wget" -OutFile "$tmp\mpv.7z"
        & "$tmp\7zr.exe" e "$tmp\mpv.7z" "-o$tmp" libmpv-2.dll -y | Out-Null
        New-Item -ItemType Directory -Force (Split-Path $cache) | Out-Null
        Copy-Item "$tmp\libmpv-2.dll" $cache
    }
}
Copy-Item $cache $dllDest -Force

# Put the user's data back.
if (Test-Path $keep) { Copy-Item "$keep\*" "$app\data" -Recurse -Force; Remove-Item $keep -Recurse -Force }

if ($Zip) {
    $zipPath = Join-Path $repo "dist\Edgeware.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath }
    Compress-Archive -Path $dist -DestinationPath $zipPath
}
Write-Host "Done: $dist\Edgeware.exe"
