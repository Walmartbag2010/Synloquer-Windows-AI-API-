@echo off
chcp 65001 >nul
title Synloquer

cd /d "%~dp0"

set PYTHON="agent_env\Scripts\python.exe"

if not exist %PYTHON% (
    set PYTHON=python
)

rem 首次运行：如果 config.json 不存在，自动运行配置向导
if not exist "config.json" (
    echo 检测到首次运行，正在启动配置向导...
    echo.
    %PYTHON% setup.py
    if errorlevel 1 (
        echo.
        echo 配置向导退出，按任意键关闭...
        pause >nul
        exit /b
    )
)

%PYTHON% synloquer.py

echo.
pause
