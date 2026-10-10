@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0src;%PYTHONPATH%
python -m paradox_export
if errorlevel 1 pause
