@echo off
echo ============================================
echo   PC Monitor - Windows Service Installer
echo ============================================
echo.
echo This will install PC Monitor as a Windows service
echo that starts automatically on boot.
echo.
echo Run this as Administrator!
echo.

:: Check for admin privileges
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Please run this script as Administrator
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

set /p CHOICE="Install (S)erver or (A)gent service? [S/A]: "

if /i "%CHOICE%"=="S" (
    echo.
    echo Installing Server service...

    :: Use NSSM (Non-Sucking Service Manager) for better service support
    echo Downloading NSSM...
    powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/release/nssm-2.24.zip' -OutFile '%TEMP%\nssm.zip'"
    powershell -Command "Expand-Archive -Path '%TEMP%\nssm.zip' -DestinationPath '%TEMP%\nssm' -Force"
    copy "%TEMP%\nssm\nssm-2.24\win64\nssm.exe" "%~dp0nssm.exe"

    :: Install service
    "%~dp0nssm.exe" install PCMonitorServer "%~dp0dist\windows\pc-monitor-server.exe"
    "%~dp0nssm.exe" set PCMonitorServer AppDirectory "%~dp0dist\windows"
    "%~dp0nssm.exe" set PCMonitorServer DisplayName "PC Monitor Server"
    "%~dp0nssm.exe" set PCMonitorServer Description "PC Monitor Dashboard Server"
    "%~dp0nssm.exe" set PCMonitorServer Start SERVICE_AUTO_START

    echo.
    echo Starting service...
    net start PCMonitorServer

    echo.
    echo Server service installed! It will start automatically on boot.
    echo Dashboard available at: http://localhost:8000

) else if /i "%CHOICE%"=="A" (
    echo.
    echo Installing Agent service...

    :: Download NSSM if not exists
    if not exist "%~dp0nssm.exe" (
        echo Downloading NSSM...
        powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/release/nssm-2.24.zip' -OutFile '%TEMP%\nssm.zip'"
        powershell -Command "Expand-Archive -Path '%TEMP%\nssm.zip' -DestinationPath '%TEMP%\nssm' -Force"
        copy "%TEMP%\nssm\nssm-2.24\win64\nssm.exe" "%~dp0nssm.exe"
    )

    :: Install service
    "%~dp0nssm.exe" install PCMonitorAgent "%~dp0dist\windows\pc-monitor-agent.exe"
    "%~dp0nssm.exe" set PCMonitorAgent AppDirectory "%~dp0dist\windows"
    "%~dp0nssm.exe" set PCMonitorAgent DisplayName "PC Monitor Agent"
    "%~dp0nssm.exe" set PCMonitorAgent Description "PC Monitor Agent - Reports to central server"
    "%~dp0nssm.exe" set PCMonitorAgent Start SERVICE_AUTO_START

    echo.
    echo Starting service...
    net start PCMonitorAgent

    echo.
    echo Agent service installed! It will start automatically on boot.

) else (
    echo Invalid choice. Please run again and enter S or A.
)

echo.
pause
