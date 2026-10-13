@echo off
setlocal enableextensions
cd /d "%~dp0" || (echo [ERROR] Could not open the project folder. & pause & exit /b 1)
title PromptCraft Hub - Setup
echo ==============================================================
echo  PromptCraft Hub - setup
echo ==============================================================
echo  Prepares the Python environment and the local database.
echo  Only Python is needed: no Docker and no administrator rights.
echo.

set "PCH_FORCE_INSTALL=1"
call "%~dp0scripts\_prepare.bat"
if errorlevel 1 goto :failed

echo.
echo [..] Initialising the database (existing data is never overwritten)...
python scripts\initialize_database.py
if errorlevel 1 goto :failed

echo.
echo [..] Running the configuration check...
python scripts\check_environment.py --config
if errorlevel 1 goto :failed

echo.
echo ==============================================================
echo  [OK] Setup finished successfully.
echo       Start the application by double-clicking start_app.bat
echo ==============================================================
echo.
pause
exit /b 0

:failed
echo.
echo ==============================================================
echo  [ERROR] Setup did not finish. Read the messages above, fix the
echo          problem, and run setup_app.bat again.
echo          Technical details: logs\promptcraft.log
echo ==============================================================
echo.
pause
exit /b 1
