@echo off
title PC Monitor - Starting...
cd /d "%~dp0"

echo.
echo  ============================================
echo   PC Monitor - One-Click Start
echo  ============================================
echo.

:: Install dependencies
echo [1/3] Installing dependencies...
pip install psutil websockets uvicorn fastapi --quiet 2>nul
if %errorlevel% neq 0 (
    echo      Installing with pip3...
    pip3 install psutil websockets uvicorn fastapi --quiet 2>nul
)
echo      Done!
echo.

:: Start server in new window
echo [2/3] Starting server...
start "PC Monitor Server" cmd /k "cd /d "%~dp0" && python server/server.py"
echo      Server starting in new window...
echo.

:: Wait for server to start
echo [3/3] Waiting for server to initialize...
timeout /t 3 /nobreak >nul
echo      Done!
echo.

:: Start agent in new window
echo [4/4] Starting agent on this computer...
start "PC Monitor Agent" cmd /k "cd /d "%~dp0" && python agent/agent.py"
echo      Agent starting in new window...
echo.

echo  ============================================
echo   ALL DONE!
echo  ============================================
echo.
echo   Dashboard: http://localhost:8000
echo.
echo   Check the server window for login credentials
echo   (or see server/config.json)
echo.
echo   Press any key to close this window...
pause >nul
