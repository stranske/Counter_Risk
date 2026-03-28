@echo off
setlocal EnableDelayedExpansion

:: ============================================================
:: process_counter_risk_remote.cmd
::
:: Worker script: polls a shared folder for .request files
:: submitted by request_counter_risk_remote.cmd and runs the
:: Counter Risk pipeline for each one.
::
:: Run this on the machine that has full pipeline access.
:: Leave it running; it will loop every 30 seconds.
:: Press Ctrl+C to stop.
:: ============================================================

set "SCRIPT_DIR=%~dp0"

:: Locate the executable
set "EXE=%SCRIPT_DIR%bin\counter-risk.exe"
if not exist "%EXE%" set "EXE=%SCRIPT_DIR%bin\counter-risk"
if not exist "%EXE%" (
    echo ERROR: counter-risk executable not found under %SCRIPT_DIR%bin\
    echo Make sure you are running this from the release bundle folder.
    pause
    exit /b 1
)

echo Counter Risk - Remote Request Processor
echo ==========================================
echo Executable: %EXE%
echo.

set /p REQUEST_FOLDER=Enter shared request folder path to watch:
if "%REQUEST_FOLDER%"=="" (
    echo ERROR: Request folder is required.
    pause
    exit /b 1
)

if not exist "%REQUEST_FOLDER%" (
    echo ERROR: Folder does not exist: %REQUEST_FOLDER%
    pause
    exit /b 1
)

echo.
echo Watching: %REQUEST_FOLDER%
echo Scanning every 30 seconds. Press Ctrl+C to stop.
echo.

:scan_loop
set "FOUND=0"

for %%F in ("%REQUEST_FOLDER%\*.request") do (
    set "FOUND=1"
    set "REQ=%%F"
    set "BASE=%%~nF"
    set "DIR=%%~dpF"

    echo [%TIME%] Found: %%~nxF

    :: Claim the file atomically by renaming to .processing
    ren "%%F" "!BASE!.processing" 2>nul
    if errorlevel 1 (
        echo [%TIME%] Already claimed by another worker, skipping.
    ) else (
        set "PROC_FILE=!DIR!!BASE!.processing"

        :: Parse key=value pairs from the request file
        set "AS_OF_DATE="
        set "MODE="
        set "OUTPUT_DIR="
        set "INPUT_ROOT="

        for /f "usebackq tokens=1,* delims==" %%A in ("!PROC_FILE!") do (
            if "%%A"=="as_of_date"  set "AS_OF_DATE=%%B"
            if "%%A"=="mode"        set "MODE=%%B"
            if "%%A"=="output_dir"  set "OUTPUT_DIR=%%B"
            if "%%A"=="input_root"  set "INPUT_ROOT=%%B"
        )

        :: Validate required fields
        if "!AS_OF_DATE!"=="" (
            echo [%TIME%] ERROR: as_of_date missing in request file.
            ren "!PROC_FILE!" "!BASE!.failed"
            goto :next_file
        )
        if "!MODE!"=="" set "MODE=all"
        if "!OUTPUT_DIR!"=="" (
            echo [%TIME%] ERROR: output_dir missing in request file.
            ren "!PROC_FILE!" "!BASE!.failed"
            goto :next_file
        )

        :: Map mode to config file
        set "CONFIG="
        if /i "!MODE!"=="all"      set "CONFIG=%SCRIPT_DIR%config\all_programs.yml"
        if /i "!MODE!"=="ex_trend" set "CONFIG=%SCRIPT_DIR%config\ex_trend.yml"
        if /i "!MODE!"=="trend"    set "CONFIG=%SCRIPT_DIR%config\trend.yml"

        if "!CONFIG!"=="" (
            echo [%TIME%] ERROR: Unknown mode '!MODE!' in request file.
            ren "!PROC_FILE!" "!BASE!.failed"
            goto :next_file
        )

        :: Build and write a settings JSON to TEMP
        set "SETTINGS_FILE=%TEMP%\counter-risk-runner-settings.json"
        set "INPUT_ROOT_VAL=!INPUT_ROOT!"
        if "!INPUT_ROOT_VAL!"=="" set "INPUT_ROOT_VAL=%SCRIPT_DIR%"
        (
            echo {
            echo   "discovery_mode": "manual",
            echo   "formatting_profile": "default",
            echo   "input_root": "!INPUT_ROOT_VAL:\=\\!",
            echo   "output_root": "!OUTPUT_DIR:\=\\!",
            echo   "strict_policy": "warn"
            echo }
        ) > "!SETTINGS_FILE!"

        echo [%TIME%] Running: !MODE! / !AS_OF_DATE!
        echo [%TIME%] Output:  !OUTPUT_DIR!

        "!EXE!" run ^
            --config "!CONFIG!" ^
            --as-of-date "!AS_OF_DATE!" ^
            --output-dir "!OUTPUT_DIR!" ^
            --settings "!SETTINGS_FILE!"

        if errorlevel 1 (
            echo [%TIME%] FAILED: !BASE!
            ren "!PROC_FILE!" "!BASE!.failed"
        ) else (
            echo [%TIME%] DONE:   !BASE!
            ren "!PROC_FILE!" "!BASE!.done"
        )
    )
    :next_file
)

if "!FOUND!"=="0" echo [%TIME%] No pending requests.

timeout /t 30 /nobreak > nul
goto :scan_loop
