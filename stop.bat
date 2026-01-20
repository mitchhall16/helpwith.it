@echo off
echo Stopping PC Monitor...
echo.

:: Kill Python processes running our scripts
taskkill /FI "WINDOWTITLE eq PC Monitor Server" >nul 2>&1
taskkill /FI "WINDOWTITLE eq PC Monitor Agent" >nul 2>&1

:: Also try to kill by script name
wmic process where "commandline like '%%server.py%%'" delete >nul 2>&1
wmic process where "commandline like '%%agent.py%%'" delete >nul 2>&1

echo Done! PC Monitor stopped.
pause
