@echo off
echo Installing PC Monitor Agent as Windows startup task...

:: Get the directory where this script is located
set SCRIPT_DIR=%~dp0

:: Create a VBS script to run Python hidden
echo Set WshShell = CreateObject("WScript.Shell") > "%SCRIPT_DIR%run-agent-hidden.vbs"
echo WshShell.Run "python ""%SCRIPT_DIR%agent\agent.py""", 0, False >> "%SCRIPT_DIR%run-agent-hidden.vbs"

:: Create scheduled task to run at startup
schtasks /create /tn "PCMonitorAgent" /tr "wscript.exe \"%SCRIPT_DIR%run-agent-hidden.vbs\"" /sc onlogon /rl highest /f

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS! PC Monitor Agent will start automatically on login.
    echo.
    echo To remove: schtasks /delete /tn "PCMonitorAgent" /f
) else (
    echo.
    echo FAILED! Try running this script as Administrator.
)

pause
