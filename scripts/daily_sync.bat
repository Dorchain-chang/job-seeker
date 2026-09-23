@echo off
REM Daily sync launcher (Windows Task Scheduler friendly).
REM Pure ASCII on purpose: keeps the file readable under any console codepage.
REM It locates itself via %~dp0, so the repo can live in any path (spaces / CJK ok).
setlocal
REM Keep console output readable (the script logs Chinese company names).
chcp 65001 >nul 2>nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

cd /d "%~dp0.."

REM Prefer the managed/embedded python, then PATH python, then py launcher.
set "PY="
if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
  set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
)
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  where py >nul 2>nul && set "PY=py"
)
if not defined PY (
  echo [ERROR] Python not found. Install Python 3.9+ and retry.
  exit /b 1
)

"%PY%" scripts\daily_sync.py %*
set "RC=%ERRORLEVEL%"

REM 0 = updated, 2 = nothing new (both fine), 1 = error
if "%RC%"=="0" echo [OK] sync done, artifacts rebuilt.
if "%RC%"=="2" echo [OK] nothing new.
if "%RC%"=="1" echo [FAIL] see scripts\daily_sync_last.log
exit /b %RC%
