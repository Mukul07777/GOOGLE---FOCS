@echo off
rem Development mode: API with auto-reload on :8000 + Vite hot reload on :5173.
rem Run run.bat once first so the Python environment and node_modules exist.
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
  echo Run run.bat once first to set everything up.
  pause
  exit /b 1
)
if not exist "frontend\node_modules" (
  pushd frontend & call npm.cmd install --no-audit --no-fund & popd
)
start "Focs API (reload)" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
start "Focs web (vite)" cmd /k "cd /d "%~dp0frontend" && npm.cmd run dev"
timeout /t 4 >nul
start "" http://localhost:5173
