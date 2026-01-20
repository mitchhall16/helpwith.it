@echo off
echo Removing PC Monitor from Windows startup...

schtasks /delete /tn "PCMonitorServer" /f 2>nul
schtasks /delete /tn "PCMonitorAgent" /f 2>nul

del "%~dp0run-server-hidden.vbs" 2>nul
del "%~dp0run-agent-hidden.vbs" 2>nul

echo.
echo Done! PC Monitor will no longer start automatically.
pause
