@echo off
echo Installing PC Monitor Agent...
echo.

:: Create directory
mkdir "%USERPROFILE%\pc-monitor-agent" 2>nul
cd /d "%USERPROFILE%\pc-monitor-agent"

:: Download agent
echo Downloading agent...
powershell -Command "Invoke-WebRequest -Uri 'http://192.168.12.125:8000/install/agent.py?key=5UmcdWxWlyER7snzbIbFlslNoapREZYh' -OutFile 'agent.py'"

:: Configure
echo Configuring...
powershell -Command "(Get-Content agent.py) -replace 'SERVER_URL = .*', 'SERVER_URL = \"http://192.168.12.125:8000\"' -replace 'API_KEY = .*', 'API_KEY = \"5UmcdWxWlyER7snzbIbFlslNoapREZYh\"' | Set-Content agent.py"

:: Install dependencies
echo Installing dependencies...
pip install psutil websockets

echo.
echo ========================================
echo Installation complete!
echo.
echo To run the agent:
echo   python "%USERPROFILE%\pc-monitor-agent\agent.py"
echo.
echo To run at startup, use install-agent-autostart.bat
echo ========================================
pause
