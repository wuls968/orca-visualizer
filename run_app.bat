@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -c "import importlib.util,sys;mods=['streamlit','orca_viz'];missing=[m for m in mods if importlib.util.find_spec(m) is None];sys.exit(1 if missing else 0)"
if errorlevel 1 (
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install .
)

python -m orca_viz.cli run
