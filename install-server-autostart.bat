@echo off
echo Installing PC Monitor Server as Windows startup task...

:: Get the directory where this script is located
set SCRIPT_DIR=%~dp0

:: Create a VBS script to run Python hidden
echo Set WshShell = CreateObject("WScript.Shell") > "%SCRIPT_DIR%run-server-hidden.vbs"
echo WshShell.Run "python ""%SCRIPT_DIR%server\server.py""", 0, False >> "%SCRIPT_DIR%run-server-hidden.vbs"

:: Create scheduled task to run at startup
schtasks /create /tn "PCMonitorServer" /tr "wscript.exe \"%SCRIPT_DIR%run-server-hidden.vbs\"" /sc onlogon /rl highest /f

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS! PC Monitor Server will start automatically on login.
    echo.
    echo To remove: schtasks /delete /tn "PCMonitorServer" /f
) else (
    echo.
    echo FAILED! Try running this script as Administrator.
)

pause
