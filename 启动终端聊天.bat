@echo off
chcp 65001 >nul
title DeepSeek 终端聊天室

cd /d "%~dp0"

set PYTHON="..\agent_env\Scripts\python.exe"

if not exist %PYTHON% (
    set PYTHON=python
)

%PYTHON% terminal_chat.py

echo.
pause
