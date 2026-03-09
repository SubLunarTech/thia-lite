@echo off
REM Debug wrapper for thia-lite.exe on Windows
REM Keeps console open and shows error messages

echo Starting Thia-Lite...
echo.

thia-lite.exe %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo THIA-LITE EXITED WITH ERROR CODE: %ERRORLEVEL%
    echo ========================================
    echo.
    echo Press any key to close this window...
    pause >nul
)
