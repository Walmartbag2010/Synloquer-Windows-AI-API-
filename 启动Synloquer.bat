@echo off
chcp 65001 >nul
title Synloquer

cd /d "%~dp0"

set PYTHON="agent_env\Scripts\python.exe"

if not exist %PYTHON% (
    set PYTHON=python
)

%PYTHON% synloquer.py

echo.
pause
