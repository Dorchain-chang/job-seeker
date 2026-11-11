@echo off
chcp 65001 >nul
title Job Seeker - AI Auto Apply Service
set "AA_BIN=%USERPROFILE%\.workbuddy\binaries\node"
set "NODE_EXE="
for /d %%D in ("%AA_BIN%\versions\*") do if exist "%%D\node.exe" set "NODE_EXE=%%D\node.exe"
if not defined NODE_EXE set "NODE_EXE=node"
set "NODE_PATH=%AA_BIN%\workspace\node_modules"
set "CHROME_EXE=%LOCALAPPDATA%\ms-playwright\chromium-1228\chrome-win64\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE="
echo [Job Seeker] AI auto-apply service starting...
echo [Job Seeker] Open this address in the page: http://127.0.0.1:8765
"%NODE_EXE%" "%~dp0auto_apply_server.js"
pause
