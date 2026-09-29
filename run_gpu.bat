@echo off
REM ==============================================================================
REM run_gpu.bat — Quick runner for scraper and pipeline with venv313 (GPU support)
REM Usage:
REM   .\run_gpu.bat
REM   .\run_gpu.bat --site "Työmarkkinatori" --limit 2
REM ==============================================================================

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0venv313\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment not found at: %PYTHON_EXE%
    echo Falling back to system python...
    set "PYTHON_EXE=python"
)

echo [1/2] Running Scraper...
"%PYTHON_EXE%" scraper\run_scraper.py %*
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Scraper failed!
    exit /b %ERRORLEVEL%
)

echo.
echo [2/2] Running Pipeline (Translation + AI + Site Gen)...
"%PYTHON_EXE%" scraper\run_pipeline.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Pipeline failed!
    exit /b %ERRORLEVEL%
)

echo.
echo [DONE] Scraper and Pipeline completed successfully.
