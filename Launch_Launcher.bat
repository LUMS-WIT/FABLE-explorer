@echo off
rem FABLE launcher (Windows). Double-click to open the desktop launcher.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)
"%PY%" src\launcher.py
if errorlevel 1 (
    echo.
    echo The launcher did not start. Install the tool first:
    echo     python -m venv .venv
    echo     .venv\Scripts\activate
    echo     pip install -e ".[excel]"
    pause
)
