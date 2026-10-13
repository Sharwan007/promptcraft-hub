@echo off
setlocal enableextensions
cd /d "%~dp0" || (echo [ERROR] Could not open the project folder. & pause & exit /b 1)
title PromptCraft Hub - Stop
echo ==============================================================
echo  Stopping PromptCraft Hub
echo ==============================================================
if not exist ".venv\Scripts\python.exe" (
  echo [OK] Nothing to stop: the application has not been set up yet.
  goto :end
)
rem Only the process that answers http://127.0.0.1:8000/api/health as "PromptCraft Hub" and
rem matches the PID file is stopped. No other Python process is ever touched.
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" scripts\stop_server.py
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (echo  Done.) else (echo  The application was not stopped cleanly - see the message above.)
:end
if /i not "%~1"=="nopause" pause
exit /b %RC%
