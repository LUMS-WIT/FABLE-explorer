@echo off
setlocal
cd /d "%~dp0"
set "SCRIPT=%~dp0src\dashboard.py"

if not exist "%SCRIPT%" (
  echo Missing: %SCRIPT%
  pause
  exit /b 1
)

if exist "%~dp0.venv\Scripts\python.exe" goto run_venv

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 goto run_py

python -c "import sys" >nul 2>&1
if not errorlevel 1 goto run_python

echo.
echo Could not find a working Python installation.
echo.
echo What to do:
echo 1. Install Python 3 for Windows.
echo 2. Make sure the Python launcher ^(py^) is installed.
echo 3. Re-open this folder and run the BAT file again.
echo.
pause
exit /b 1

:run_venv
echo Starting FABLE Pakistan Dashboard...
"%~dp0.venv\Scripts\python.exe" -m streamlit run "%SCRIPT%"
if errorlevel 1 (
  echo.
  echo Dashboard exited with an error.
  pause
)
exit /b %errorlevel%

:run_py
echo Starting FABLE Pakistan Dashboard...
py -3 -m streamlit run "%SCRIPT%"
if errorlevel 1 (
  echo.
  echo Dashboard exited with an error.
  pause
)
exit /b %errorlevel%

:run_python
echo Starting FABLE Pakistan Dashboard...
python -m streamlit run "%SCRIPT%"
if errorlevel 1 (
  echo.
  echo Dashboard exited with an error.
  pause
)
exit /b %errorlevel%
