@echo off
echo Starting PC Monitor Server...
cd /d "%~dp0server"
python server.py
pause
