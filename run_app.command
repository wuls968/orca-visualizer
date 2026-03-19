#!/bin/zsh
set -e
cd /Users/a0000/Desktop/orca_visualizer
source .venv/bin/activate
exec streamlit run app.py
