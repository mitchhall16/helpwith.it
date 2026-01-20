@echo off
echo ============================================
echo PC Monitor - InfluxDB + Grafana Setup
echo ============================================
echo.

:: Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed!
    echo.
    echo Please install Docker Desktop from:
    echo https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)

echo Starting InfluxDB and Grafana...
echo.

cd /d "%~dp0"
docker-compose up -d

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo SUCCESS! Services are starting...
    echo ============================================
    echo.
    echo Wait 30 seconds for services to initialize, then:
    echo.
    echo   Grafana:   http://localhost:3000
    echo             Login: admin / admin
    echo.
    echo   InfluxDB:  http://localhost:8086
    echo             Login: admin / pcmonitor123
    echo             Token: pc-monitor-super-secret-token
    echo.
    echo Next steps:
    echo   1. Install Telegraf on each computer you want to monitor
    echo   2. Copy telegraf/telegraf.conf and update the token
    echo   3. Run: telegraf --config telegraf.conf
    echo.
) else (
    echo.
    echo FAILED! Check if Docker is running.
)

pause
