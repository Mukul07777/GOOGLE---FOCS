@echo off
setlocal EnableExtensions
title Focs
cd /d "%~dp0"

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "VENV=%BACKEND%\.venv"
set "VPY=%VENV%\Scripts\python.exe"

echo.
echo    ___
echo   ^|  _^|___ ___ ___     Focs - every lecture, understood
echo   ^|  _^| . ^|  _^|_ -^|
echo   ^|_^| ^|___^|___^|___^|    run.bat [rebuild]
echo.

rem ------------------------------------------------------------------ 1. Python
set "PY="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12"
  if not defined PY py -3.11 -c "import sys" >nul 2>nul && set "PY=py -3.11"
)
if not defined PY (
  python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [x] Python 3.10 to 3.14 was not found.
  echo     Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^) and run this again.
  goto :fail
)

rem ------------------------------------------------------------------ 2. Backend environment
if not exist "%VPY%" (
  echo [1/4] Creating the Python environment ...
  %PY% -m venv "%VENV%"
  if errorlevel 1 goto :fail
)
fc /b "%BACKEND%\requirements.txt" "%VENV%\.requirements.installed" >nul 2>nul
if errorlevel 1 (
  echo [2/4] Installing backend packages - the first run takes a few minutes ...
  "%VPY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
  "%VPY%" -m pip install -r "%BACKEND%\requirements.txt" --quiet --disable-pip-version-check --ignore-requires-python
  if errorlevel 1 goto :fail
  copy /y "%BACKEND%\requirements.txt" "%VENV%\.requirements.installed" >nul
) else (
  echo [2/4] Backend packages are up to date
)

rem ------------------------------------------------------------------ 3. Configuration
if not exist "%BACKEND%\.env" (
  copy /y "%ROOT%.env.example" "%BACKEND%\.env" >nul
  "%VPY%" -c "import pathlib,secrets; p=pathlib.Path(r'%BACKEND%\.env'); p.write_text(p.read_text(encoding='utf-8').replace('SECRET_KEY=change-me','SECRET_KEY='+secrets.token_hex(32)), encoding='utf-8')"
  echo [3/4] Created backend\.env  - add your free GEMINI_API_KEY there to switch on the AI
) else (
  echo [3/4] Configuration found ^(backend\.env^)
)

rem ------------------------------------------------------------------ 4. Web app
set "NEED_BUILD="
if /i "%~1"=="rebuild" set "NEED_BUILD=1"
if not exist "%FRONTEND%\dist\index.html" set "NEED_BUILD=1"
if not defined NEED_BUILD (
  powershell -NoProfile -Command "$d=(Get-Item '%FRONTEND%\dist\index.html').LastWriteTime; if (Get-ChildItem '%FRONTEND%\src','%FRONTEND%\public','%FRONTEND%\index.html','%FRONTEND%\package.json' -Recurse -File | Where-Object { $_.LastWriteTime -gt $d }) { exit 1 }" >nul 2>nul
  if errorlevel 1 set "NEED_BUILD=1"
)
if defined NEED_BUILD (
  where npm.cmd >nul 2>nul
  if errorlevel 1 where npm >nul 2>nul
  if errorlevel 1 (
    if exist "%FRONTEND%\dist\index.html" (
      echo [4/4] Node.js not found - using the existing web build
      goto :launch
    )
    echo [x] Node.js 20+ is needed once to build the web app: https://nodejs.org
    goto :fail
  )
  echo [4/4] Building the web app ...
  pushd "%FRONTEND%"
  fc /b package.json node_modules\.package.installed >nul 2>nul
  if errorlevel 1 (
    call npm.cmd install --no-audit --no-fund --loglevel=error
    if errorlevel 1 ( popd & goto :fail )
    copy /y package.json node_modules\.package.installed >nul
  )
  call npm.cmd run build --silent
  if errorlevel 1 ( popd & goto :fail )
  popd
) else (
  echo [4/4] Web app is up to date
)

:launch
echo.
"%VPY%" "%BACKEND%\scripts\launch.py" %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo [x] Focs could not start. Scroll up for the first error message.
echo     Tip: delete backend\.venv and run this again for a clean reinstall.
pause
exit /b 1
