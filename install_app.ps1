$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3 -m venv .venv
}

& ".venv\Scripts\Activate.ps1"

python -m pip install --upgrade pip setuptools wheel
python -m pip install .
python -m orca_viz.cli doctor
