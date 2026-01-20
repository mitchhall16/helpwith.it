@echo off
echo ============================================
echo   PC Monitor - Windows Build Script
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python first.
    pause
    exit /b 1
)

:: Install PyInstaller if needed
echo Installing/updating PyInstaller...
pip install pyinstaller --quiet

:: Create dist directory
if not exist "dist" mkdir dist
if not exist "dist\windows" mkdir dist\windows

echo.
echo Building Server...
pyinstaller --onefile --name pc-monitor-server --icon=NUL --add-data "dashboard;dashboard" --distpath dist\windows --workpath build\server --specpath build server\server.py

echo.
echo Building Agent...
pyinstaller --onefile --name pc-monitor-agent --icon=NUL --distpath dist\windows --workpath build\agent --specpath build agent\agent.py

:: Copy config
if exist "server\config.json" copy "server\config.json" "dist\windows\config.json"

echo.
echo ============================================
echo   Build Complete!
echo ============================================
echo.
echo Files created in dist\windows\:
dir /b dist\windows\
echo.
echo To use:
echo   1. Copy pc-monitor-server.exe to your server computer
echo   2. Copy pc-monitor-agent.exe to computers you want to monitor
echo   3. Run the server first, then agents
echo.
pause
