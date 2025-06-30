@echo off
setlocal

:: ==== CONFIGURATION ====
set ROBOT_DIR=%~dp0
set RUN_CMD=uv run python -m robocorp.tasks run tasks.py -t main
set OUTPUT_DIR=%ROBOT_DIR%output
set LOGS_DIR=%ROBOT_DIR%logs

:: ==== RUN ROBOT ====
echo [INFO] Running robot...
%RUN_CMD%
echo [INFO] Robot run complete.

:: ==== READ STATUS FROM FILE ====
set STATUS=UNKNOWN
if exist "%OUTPUT_DIR%\status.txt" (
    for /f %%s in (%OUTPUT_DIR%\status.txt) do set STATUS=%%s
)
echo [INFO] Robot run status: %STATUS%

:: ==== CREATE OUTPUT FILENAME (locale independent) ====
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TIMESTAMP=%%i
set ARCHIVE_DIR=%LOGS_DIR%\%TIMESTAMP%_%STATUS%

:: ==== ARCHIVE OUTPUT ====
echo [INFO] Archiving output to: %ARCHIVE_DIR%
mkdir "%ARCHIVE_DIR%"
xcopy /E /I /Y "%OUTPUT_DIR%\*" "%ARCHIVE_DIR%\" >nul

:: ==== CLEAN UP OUTPUT ====
echo [INFO] Cleaning up output folder...
rmdir /S /Q "%OUTPUT_DIR%"

echo [SUCCESS] All done.
endlocal