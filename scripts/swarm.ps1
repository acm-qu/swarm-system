# Windows launcher, run through swarm.cmd in the repo root:
#   .\swarm setup              install the hub's packages (once) and create your login
#   .\swarm                    start the hub
#   .\swarm adduser <name>     any other hub command (token, rotate, --headless, ...)
# Finds Python by itself, even if it isn't on PATH. No virtual environment needed.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

function Test-Python($exe, $extra) {
    try {
        $out = & $exe @extra -c "import sys; print(sys.executable if sys.version_info >= (3, 9) else '')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -Last 1).Trim() }
    } catch {}
    return $null
}

function Find-Python {
    # 1. On PATH (skip the Microsoft Store stub in WindowsApps, which only opens the Store)
    foreach ($try in @(@("py", "-3"), @("python"), @("python3"))) {
        $cmd = Get-Command $try[0] -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike "*\WindowsApps\*") {
            $found = Test-Python $cmd.Source @($try | Select-Object -Skip 1)
            if ($found) { return $found }
        }
    }
    # 2. The usual install folders, newest version first
    $dirs = @("$env:LOCALAPPDATA\Programs\Python\Python3*", "$env:ProgramFiles\Python3*", "C:\Python3*")
    $candidates = Get-ChildItem $dirs -Directory -ErrorAction SilentlyContinue |
        Sort-Object { [int]($_.Name -replace "\D", "") } -Descending
    foreach ($dir in $candidates) {
        $found = Test-Python (Join-Path $dir.FullName "python.exe") @()
        if ($found) { return $found }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Host "Python 3.9 or newer wasn't found. Install it from https://www.python.org/downloads/ and run this again." -ForegroundColor Red
    exit 1
}

if ($args.Count -ge 1 -and $args[0] -eq "setup") {
    Write-Host "Using $python"
    & $python -m pip install --user --disable-pip-version-check --no-warn-script-location -r hub\requirements.txt
    if ($LASTEXITCODE -ne 0) { Write-Host "Installing the packages failed (see above)." -ForegroundColor Red; exit 1 }
    if (-not (Test-Path data\users.json)) {
        $name = Read-Host "Pick a username for your hub login"
        & $python -m hub adduser $name
    }
    Write-Host "Ready. Start the hub with:  .\swarm" -ForegroundColor Green
    exit 0
}

& $python -m hub @args
exit $LASTEXITCODE
