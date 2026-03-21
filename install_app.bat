@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip setuptools wheel
python -m pip install .
python -m orca_viz.cli doctor
