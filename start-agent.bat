@echo off
echo Starting PC Monitor Agent...
cd /d "%~dp0agent"
python agent.py
pause
