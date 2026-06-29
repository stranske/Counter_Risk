@echo off
setlocal

rem Launch the Counter Risk Tkinter GUI from a double-clickable Windows shell.
rem Keep this file at the repository/release root so %~dp0 resolves to the app folder.
title Counter Risk GUI Launcher
cd /d "%~dp0"

set "COUNTER_RISK_EXIT=1"

echo Starting Counter Risk GUI...
echo.

if exist "%~dp0dist\counter-risk\counter-risk.exe" (
    "%~dp0dist\counter-risk\counter-risk.exe" gui
    set "COUNTER_RISK_EXIT=%ERRORLEVEL%"
    goto :after_run
)

if exist "%~dp0counter-risk.exe" (
    "%~dp0counter-risk.exe" gui
    set "COUNTER_RISK_EXIT=%ERRORLEVEL%"
    goto :after_run
)

if exist "%~dp0.venv\Scripts\counter-risk.exe" (
    "%~dp0.venv\Scripts\counter-risk.exe" gui
    set "COUNTER_RISK_EXIT=%ERRORLEVEL%"
    goto :after_run
)

where counter-risk >nul 2>nul
if not errorlevel 1 (
    counter-risk gui
    set "COUNTER_RISK_EXIT=%ERRORLEVEL%"
    goto :after_run
)

set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
where py >nul 2>nul
if not errorlevel 1 (
    py -m counter_risk.cli gui
    set "COUNTER_RISK_EXIT=%ERRORLEVEL%"
    goto :after_run
)

where python >nul 2>nul
if not errorlevel 1 (
    python -m counter_risk.cli gui
    set "COUNTER_RISK_EXIT=%ERRORLEVEL%"
    goto :after_run
)

echo Could not find Counter Risk or Python.
echo.
echo Try one of these fixes:
echo   1. Run this file from the Counter Risk release folder, or
echo   2. Install the project so the counter-risk command is available, or
echo   3. Ask support for a packaged Counter Risk release folder.
set "COUNTER_RISK_EXIT=9009"
goto :failure

:after_run
if "%COUNTER_RISK_EXIT%"=="0" goto :success

:failure
echo.
echo Counter Risk GUI did not start or exited with error code %COUNTER_RISK_EXIT%.
echo Leave this window open and copy the messages above when asking for help.
echo.
pause
exit /b %COUNTER_RISK_EXIT%

:success
exit /b 0
