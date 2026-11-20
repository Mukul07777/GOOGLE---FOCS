@echo off
rem Train FocsOCR, export it to the backend and benchmark it end to end.
rem   train_ocr.bat                 full run (22k steps, ~1 h on an RTX 4050)
rem   train_ocr.bat --steps 3000    quick run; any extra arguments go to focs_ocr.train
setlocal EnableExtensions
cd /d "%~dp0"
set "MLVENV=%~dp0ml\.venv"
set "MLPY=%MLVENV%\Scripts\python.exe"

if not exist "%MLPY%" (
  echo [1/5] Creating the training environment ...
  py -3.12 -m venv "%MLVENV%" 2>nul || python -m venv "%MLVENV%"
  if errorlevel 1 goto :fail
)
"%MLPY%" -c "import torch" >nul 2>nul
if errorlevel 1 (
  echo [2/5] Installing PyTorch ...
  where nvidia-smi >nul 2>nul
  if errorlevel 1 (
    echo       No NVIDIA GPU found - installing the CPU build. Training will be much slower.
    "%MLPY%" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  ) else (
    "%MLPY%" -m pip install torch --index-url https://download.pytorch.org/whl/cu126
  )
  if errorlevel 1 goto :fail
)
"%MLPY%" -m pip install -r ml\requirements-train.txt --quiet --disable-pip-version-check
if errorlevel 1 goto :fail

echo [3/5] Fetching fonts and word list from GitHub ...
"%MLPY%" ml\scripts\download_assets.py
if errorlevel 1 goto :fail

echo [4/5] Training (checkpoints in ml\runs\focsocr-v1) ...
pushd ml
"%MLPY%" -m focs_ocr.train --name focsocr-v1 %*
if errorlevel 1 ( popd & goto :fail )
"%MLPY%" -m focs_ocr.scenes --n 240
popd

echo [5/5] Benchmarking against PP-OCRv4 on full lecture frames ...
if exist "backend\.venv\Scripts\python.exe" (
  backend\.venv\Scripts\python.exe backend\scripts\benchmark_ocr.py
) else (
  echo       Run run.bat once, then: backend\.venv\Scripts\python.exe backend\scripts\benchmark_ocr.py
)
echo.
echo Done. Restart Focs (run.bat) to load the new model.
pause
exit /b 0

:fail
echo.
echo [x] Training failed - see the error above.
pause
exit /b 1
