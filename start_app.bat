@echo off
setlocal enableextensions
cd /d "%~dp0" || (echo [ERROR] Could not open the project folder. & pause & exit /b 1)
title PromptCraft Hub
echo ==============================================================
echo  PromptCraft Hub  -  Build better prompts. Get better results.
echo ==============================================================

call "%~dp0scripts\_prepare.bat"
if errorlevel 1 goto :failed

rem The launcher initialises the database (seed data only into empty tables), checks that
rem port 8000 is free or already used by PromptCraft Hub, starts the server, waits for
rem /api/health and opens the browser. This window stays open while the server runs.
python scripts\launcher.py
set "RC=%errorlevel%"
if "%RC%"=="0" goto :done
echo.
if "%RC%"=="3" echo [ERROR] The database could not be prepared. See the message above and logs\promptcraft.log
if "%RC%"=="4" echo [ERROR] Port 8000 is used by another program. Nothing was stopped. See the message above.
if "%RC%"=="5" echo [ERROR] The server could not start. See logs\promptcraft.log
goto :failed_pause

:failed
set "RC=%errorlevel%"
:failed_pause
echo.
echo  Start-up did not complete (code %RC%). Fix the problem described above and run start_app.bat again.
echo  The README has a Troubleshooting section for every message shown here.
if /i not "%~1"=="nopause" pause
exit /b %RC%

:done
exit /b 0
