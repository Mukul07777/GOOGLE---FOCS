@echo off
setlocal
title Focs - admin sign-in
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Run run.bat once first, so Focs is installed.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\set_admin.py %*
pause
