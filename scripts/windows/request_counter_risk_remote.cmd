@echo off
setlocal EnableDelayedExpansion

:: ============================================================
:: request_counter_risk_remote.cmd
::
:: Submits a Counter Risk run request to a shared folder.
:: A worker machine running process_counter_risk_remote.cmd
:: will pick it up and execute the pipeline.
::
:: Usage: double-click or run from the bundle folder.
:: ============================================================

set "SCRIPT_DIR=%~dp0"

echo Counter Risk - Remote Request
echo ==============================
echo.

:: --- As-of date ---
set /p AS_OF_DATE=Enter as-of date (YYYY-MM-DD, e.g. 2025-12-31):
if "%AS_OF_DATE%"=="" (
    echo ERROR: As-of date is required.
    goto :error
)

:: --- Mode ---
echo.
echo Modes:  all  /  ex_trend  /  trend
set /p MODE=Enter mode [all]:
if "%MODE%"=="" set "MODE=all"
if /i not "%MODE%"=="all" if /i not "%MODE%"=="ex_trend" if /i not "%MODE%"=="trend" (
    echo ERROR: Mode must be all, ex_trend, or trend.
    goto :error
)

:: --- Output directory ---
echo.
set /p OUTPUT_DIR=Enter output directory for results (UNC or local path):
if "%OUTPUT_DIR%"=="" (
    echo ERROR: Output directory is required.
    goto :error
)

:: --- Input root (optional) ---
echo.
set /p INPUT_ROOT=Enter input root directory (leave blank to use worker default - bundle folder):

:: --- Shared request folder ---
echo.
set /p REQUEST_FOLDER=Enter shared request folder path (where worker will look):
if "%REQUEST_FOLDER%"=="" (
    echo ERROR: Shared request folder is required.
    goto :error
)

:: --- Build timestamp for unique filename ---
set "DT="
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "DT=%%I"
if defined DT (
    set "TIMESTAMP=%DT:~0,8%_%DT:~8,6%"
) else (
    for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul') do set "TIMESTAMP=%%I"
)
if "%TIMESTAMP%"=="" (
    echo ERROR: Could not generate timestamp for request filename.
    echo Ensure WMIC or PowerShell is available on this system.
    goto :error
)

:: --- Write request file ---
set "REQUEST_FILE=%REQUEST_FOLDER%\counter_risk_%AS_OF_DATE%_%MODE%_%TIMESTAMP%.request"

(
    echo as_of_date=%AS_OF_DATE%
    echo mode=%MODE%
    echo output_dir=%OUTPUT_DIR%
    echo input_root=%INPUT_ROOT%
    echo requested_by=%USERNAME%
    echo requested_at=%DATE% %TIME%
) > "%REQUEST_FILE%"

if errorlevel 1 (
    echo ERROR: Could not write request file to: %REQUEST_FOLDER%
    echo Make sure the folder exists and you have write access.
    goto :error
)

echo.
echo Request submitted successfully.
echo File: %REQUEST_FILE%
echo.
echo The worker machine running process_counter_risk_remote.cmd will
echo pick it up shortly. Check the output directory for results:
echo   %OUTPUT_DIR%
echo.
goto :done

:error
echo.
echo Request was not submitted. Correct the issue and try again.
echo.

:done
pause
endlocal
