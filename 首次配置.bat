@echo off
chcp 65001 >nul
title AI 终端聊天室 - 首次配置向导
setlocal enabledelayedexpansion

echo ============================================================
echo            AI 终端聊天室 - 首次配置向导
echo ============================================================
echo.

:: ========== 1. 获取工作目录 ==========
set "WORK_DIR=%~dp0"
:: 去掉末尾反斜杠
if "%WORK_DIR:~-1%"=="\" set "WORK_DIR=%WORK_DIR:~0,-1%"

echo [步骤 1/4] 获取工作目录
echo   项目路径: %WORK_DIR%
echo.

:: ========== 2. 检查 Python 环境 ==========
echo [步骤 2/4] 检查 Python 环境
set "PYTHON_EXE=%WORK_DIR%\agent_env\Scripts\python.exe"
if exist "%PYTHON_EXE%" (
    echo   虚拟环境: 已存在 ^(agent_env^)
) else (
    echo   虚拟环境: 未找到，正在创建...
    python -m venv "%WORK_DIR%\agent_env"
    if exist "%PYTHON_EXE%" (
        echo   虚拟环境创建成功，正在安装依赖...
        "%PYTHON_EXE%" -m pip install -r "%WORK_DIR%\requirements.txt" -q
        echo   依赖安装完成
    ) else (
        echo   [错误] 虚拟环境创建失败，请确认已安装 Python 3.10+
        pause
        exit /b 1
    )
)
echo.

:: ========== 3. 创建 config.json ==========
echo [步骤 3/4] 初始化配置文件
set "CONFIG_FILE=%WORK_DIR%\config.json"
set "CONFIG_EXAMPLE=%WORK_DIR%\config.example.json"

if exist "%CONFIG_FILE%" (
    echo   config.json: 已存在，跳过创建
) else (
    if exist "%CONFIG_EXAMPLE%" (
        copy "%CONFIG_EXAMPLE%" "%CONFIG_FILE%" >nul
        echo   config.json: 已从模板创建
    ) else (
        echo   [错误] 未找到 config.example.json
        pause
        exit /b 1
    )
)
echo.

:: ========== 4. 打开配置文件引导填写 ==========
echo [步骤 4/4] 打开配置文件
echo.
echo ============================================================
echo   请在记事本中填写以下关键配置项：
echo.
echo   1. env_file_path  : 你的 .env 密钥文件完整路径
echo                        （建议放在桌面，如: C:\Users\你的用户名\Desktop\.env）
echo.
echo   2. provider       : AI 服务商，可选:
echo                        deepseek / openai / anthropic / zhipu
echo                        qwen / moonshot / minimax / baidu
echo.
echo   3. models.chat    : 对话模型名称（如 deepseek-v4-pro）
echo   4. models.summary : 总结模型名称（如 deepseek-v4-flash）
echo.
echo   5. image_window   : 图片窗口大小比例（可选修改）
echo.
echo   填写完成后，保存并关闭记事本，程序将继续...
echo ============================================================
echo.

:: 用记事本打开配置文件，等待关闭后继续
notepad "%CONFIG_FILE%"

echo.
echo ============================================================
echo   配置文件已保存！
echo ============================================================
echo.
echo 接下来你还需要完成：
echo.
echo   1. 创建 .env 密钥文件
echo      复制项目目录下的 .env.example 为 .env
echo      填入你在 env_file_path 中指定的路径
echo      填入对应的 API 密钥（如 DEEPSEEK_API_KEY、BOCHA_API_KEY）
echo.
echo   2. 启动程序
echo      双击项目目录下的 "启动终端聊天.bat"
echo.
echo   3. 验证配置
echo      启动后会显示当前服务商、模型和密钥文件路径
echo      如显示 [警告] 未找到 .env 密钥文件，请检查 env_file_path
echo.
echo ============================================================
echo.
pause
endlocal
