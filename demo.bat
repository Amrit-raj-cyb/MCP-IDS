@echo off
rem Double-click to run the MCP-IDS demo. Extra options are passed on, e.g. demo.bat -Live
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo.ps1" %*
echo.
pause
