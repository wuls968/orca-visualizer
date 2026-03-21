$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3 -m venv .venv
}

& ".venv\Scripts\Activate.ps1"

python -c "import importlib.util,sys;mods=['streamlit','orca_viz'];missing=[m for m in mods if importlib.util.find_spec(m) is None];sys.exit(1 if missing else 0)"
if ($LASTEXITCODE -ne 0) {
    python -m pip install --upgrade pip setuptools wheel
    python -m pip install .
}

python -m orca_viz.cli run
