@echo off
setlocal enableextensions
cd /d "%~dp0" || (echo [ERROR] Could not open the project folder. & pause & exit /b 1)
title PromptCraft Hub - Backup
echo ==============================================================
echo  PromptCraft Hub - database backup
echo ==============================================================
call "%~dp0scripts\_prepare.bat"
if errorlevel 1 (
  echo [ERROR] The environment could not be prepared; no backup was made.
  if /i not "%~1"=="nopause" pause
  exit /b 1
)
python scripts\backup_database.py
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (echo  Backup finished.) else (echo  Backup FAILED - see the message above and logs\promptcraft.log)
if /i not "%~1"=="nopause" pause
exit /b %RC%
