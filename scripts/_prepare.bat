@echo off
rem ============================================================================
rem  Shared preparation used by setup_app.bat, start_app.bat, run_tests.bat and
rem  backup_data.bat. Not meant to be started by hand.
rem    - finds Python 3.11+ and verifies pip
rem    - creates .venv if missing, activates it
rem    - installs the packages from requirements.txt when they are missing
rem    - creates the data, logs and backups folders
rem  Options (environment variables set by the caller):
rem    PCH_FORCE_INSTALL=1   always upgrade pip and run "pip install -r requirements.txt"
rem    PCH_NEED_TESTS=1      also require the test packages (pytest, httpx)
rem  Exit codes: 0 ok, 10 no Python, 11 Python too old, 12 pip missing,
rem              13 venv failed, 14 dependency install failed, 15 folder not writable
rem ============================================================================
cd /d "%~dp0.." || (echo [ERROR] Could not open the project folder. & exit /b 15)
set "PYTHONUTF8=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

if exist ".venv\Scripts\python.exe" goto :have_venv

rem ---- 1. find a suitable system Python ---------------------------------------
set "SYS_PY="
call :try "py -3.13"
call :try "py -3.12"
call :try "py -3.11"
call :try "py -3"
call :try "python"
if defined SYS_PY goto :have_python

python --version >nul 2>&1
if not errorlevel 1 goto :too_old
py -3 --version >nul 2>&1
if not errorlevel 1 goto :too_old
echo.
echo [ERROR] Python is not installed, or it is not on your PATH.
echo         1. Install Python 3.11 or later from https://www.python.org/downloads/
echo            (tick "Add python.exe to PATH" in the installer; no administrator rights are needed
echo            when you choose "Install for me only").
echo         2. Close this window and double-click the script again.
echo         Note: if typing "python" opens the Microsoft Store, install Python from python.org instead.
exit /b 10

:too_old
echo.
echo [ERROR] The Python version found on this computer is older than 3.11.
echo         Install Python 3.11 or later from https://www.python.org/downloads/ and run this script again.
exit /b 11

:have_python
echo [OK] Using system Python: %SYS_PY%
%SYS_PY% -m pip --version >nul 2>&1
if errorlevel 1 (
  echo [..] pip was not found; trying to enable it with ensurepip...
  %SYS_PY% -m ensurepip --upgrade >nul 2>&1
  %SYS_PY% -m pip --version >nul 2>&1
  if errorlevel 1 (
    echo.
    echo [ERROR] pip is not available for this Python installation.
    echo         Re-run the Python installer, choose "Modify" and make sure "pip" is ticked, then try again.
    exit /b 12
  )
)
echo [..] Creating the virtual environment in .venv (first run only)...
%SYS_PY% -m venv ".venv"
if errorlevel 1 goto :venv_failed
if not exist ".venv\Scripts\python.exe" goto :venv_failed
echo [OK] Virtual environment created.
goto :activate

:venv_failed
echo.
echo [ERROR] The virtual environment could not be created.
echo         - Make sure this folder is writable (move the project to Documents if it is not).
echo         - Delete a half-created ".venv" folder, if present, and try again.
exit /b 13

:have_venv
echo [OK] Virtual environment found.

:activate
call ".venv\Scripts\activate.bat"
python -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
  echo.
  echo [ERROR] The existing ".venv" folder was created with a Python older than 3.11.
  echo         Delete the ".venv" folder and run this script again.
  exit /b 11
)

rem ---- 2. folders ---------------------------------------------------------------
if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"
if not exist "backups" mkdir "backups"
echo test>"data\.write_test" 2>nul
if not exist "data\.write_test" (
  echo.
  echo [ERROR] The application cannot write to the project folder.
  echo         Move the PromptCraft-Hub folder to a location you own, for example Documents, and try again.
  exit /b 15
)
del "data\.write_test" >nul 2>&1

rem ---- 3. Python packages -------------------------------------------------------
set "DEP_ARGS=--deps"
if "%PCH_NEED_TESTS%"=="1" set "DEP_ARGS=--deps --tests"
if "%PCH_FORCE_INSTALL%"=="1" goto :install
python scripts\check_environment.py %DEP_ARGS% >nul 2>&1
if not errorlevel 1 (
  echo [OK] Python packages are installed.
  exit /b 0
)

:install
echo [..] Installing Python packages from requirements.txt (this needs an internet connection the first time)...
python -m pip install --upgrade pip >nul 2>&1
if errorlevel 1 echo [WARN] pip could not be upgraded; continuing with the current version.
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERROR] The Python packages could not be installed.
  echo         - Check your internet connection and any proxy or firewall settings.
  echo         - Then run the script again; already downloaded packages are reused.
  echo         - Corporate network? Ask IT for a PyPI mirror and set it with: pip config set global.index-url ^<url^>
  exit /b 14
)
python scripts\check_environment.py %DEP_ARGS% >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Some packages are still missing after installation. See the messages above.
  exit /b 14
)
echo [OK] Python packages installed.
exit /b 0

:try
if defined SYS_PY exit /b 0
%~1 -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "SYS_PY=%~1"
exit /b 0
