@echo off
setlocal EnableExtensions

rem Launch the Counter Risk Tkinter GUI from a double-clickable Windows shell.
rem Keep this file at the repository/release root so %~dp0 resolves to the app folder.
title Counter Risk GUI Launcher
cd /d "%~dp0"

set "COUNTER_RISK_EXIT=1"
set "COUNTER_RISK_LAUNCHER_LOG=%TEMP%\counter-risk-gui-launcher.log"

>"%COUNTER_RISK_LAUNCHER_LOG%" echo Counter Risk GUI launcher started at %DATE% %TIME%
>>"%COUNTER_RISK_LAUNCHER_LOG%" echo Launcher folder: %CD%

echo Starting Counter Risk GUI...
echo Launcher log: %COUNTER_RISK_LAUNCHER_LOG%
echo.

if exist "%~dp0dist\counter-risk\counter-risk.exe" (
    call :run_and_log "%~dp0dist\counter-risk\counter-risk.exe" gui
    goto :after_run
)

if exist "%~dp0counter-risk.exe" (
    call :run_and_log "%~dp0counter-risk.exe" gui
    goto :after_run
)

if exist "%~dp0.venv\Scripts\counter-risk.exe" (
    call :run_and_log "%~dp0.venv\Scripts\counter-risk.exe" gui
    goto :after_run
)

rem Prefer the source tree next to this launcher before any stale global install.
if exist "%~dp0src\counter_risk\cli\__init__.py" (
    set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
    if exist "%~dp0.venv\Scripts\python.exe" (
        call :run_and_log "%~dp0.venv\Scripts\python.exe" -m counter_risk.cli gui
        goto :after_run
    )
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3.12 --version >nul 2>nul
        if not errorlevel 1 (
            call :run_and_log py -3.12 -m counter_risk.cli gui
            goto :after_run
        )
        call :run_and_log py -m counter_risk.cli gui
        goto :after_run
    )
    where python >nul 2>nul
    if not errorlevel 1 (
        call :run_and_log python -m counter_risk.cli gui
        goto :after_run
    )
)

where counter-risk >nul 2>nul
if not errorlevel 1 (
    call :run_and_log counter-risk gui
    goto :after_run
)

echo Could not find Counter Risk or Python.
echo.
echo Try one of these fixes:
echo   1. Run this file from the Counter Risk release folder, or
echo   2. Install the project so the counter-risk command is available, or
echo   3. Ask support for a packaged Counter Risk release folder.
>>"%COUNTER_RISK_LAUNCHER_LOG%" echo Could not find Counter Risk or Python.
set "COUNTER_RISK_EXIT=9009"
goto :failure

:run_and_log
echo Command: %*
>>"%COUNTER_RISK_LAUNCHER_LOG%" echo.
>>"%COUNTER_RISK_LAUNCHER_LOG%" echo Command: %*
%* 1>>"%COUNTER_RISK_LAUNCHER_LOG%" 2>>&1
set "COUNTER_RISK_EXIT=%ERRORLEVEL%"
>>"%COUNTER_RISK_LAUNCHER_LOG%" echo Exit code: %COUNTER_RISK_EXIT%
exit /b 0

:after_run
if "%COUNTER_RISK_EXIT%"=="0" goto :success

:failure
echo.
echo Counter Risk GUI did not start or exited with error code %COUNTER_RISK_EXIT%.
echo The launcher wrote details to:
echo   %COUNTER_RISK_LAUNCHER_LOG%
echo.
echo Last launcher log lines:
type "%COUNTER_RISK_LAUNCHER_LOG%"
echo.
echo Leave this window open and copy the messages above when asking for help.
echo.
pause
exit /b %COUNTER_RISK_EXIT%

:success
echo.
echo Counter Risk GUI closed normally.
echo Launcher log: %COUNTER_RISK_LAUNCHER_LOG%
echo.
if /i not "%COUNTER_RISK_NO_PAUSE%"=="1" pause
exit /b 0
