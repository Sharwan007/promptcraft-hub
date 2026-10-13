@echo off
setlocal enableextensions
cd /d "%~dp0" || (echo [ERROR] Could not open the project folder. & pause & exit /b 1)
title PromptCraft Hub - Tests
echo ==============================================================
echo  PromptCraft Hub - automated tests
echo  (they use a temporary database; your data is never touched)
echo ==============================================================
set "PCH_NEED_TESTS=1"
call "%~dp0scripts\_prepare.bat"
if errorlevel 1 (
  echo [ERROR] The environment could not be prepared; tests were not run.
  if /i not "%~1"=="nopause" pause
  exit /b 1
)

echo.
echo [..] Running backend tests...
python -m pytest tests -q -p no:cacheprovider
set "T1=%errorlevel%"

echo.
echo [..] Running the smoke test...
python scripts\smoke_test.py
set "T2=%errorlevel%"

echo.
echo ==============================================================
echo  TEST SUMMARY
if "%T1%"=="0" (echo   Backend tests : PASSED) else (echo   Backend tests : FAILED)
if "%T2%"=="0" (echo   Smoke test    : PASSED) else (echo   Smoke test    : FAILED)
echo ==============================================================
set "RC=0"
if not "%T1%"=="0" set "RC=1"
if not "%T2%"=="0" set "RC=1"
if /i not "%~1"=="nopause" pause
exit /b %RC%
