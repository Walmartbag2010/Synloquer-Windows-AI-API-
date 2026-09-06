"""
Synloquer 配置向导

交互式配置脚本，替代原 bat 配置向导。
功能：
1. 检测 Python 环境，创建虚拟环境（可选）
2. 安装依赖
3. 生成 config.json 并引导填写
4. 引导填写 .env 密钥
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CONFIG_EXAMPLE = os.path.join(SCRIPT_DIR, "config.example.json")
ENV_EXAMPLE = os.path.join(SCRIPT_DIR, ".env.example")
VENV_DIR = os.path.join(SCRIPT_DIR, "agent_env")
REQUIREMENTS = os.path.join(SCRIPT_DIR, "requirements.txt")

# 预配置的服务商列表
PROVIDERS = ["deepseek", "openai", "anthropic", "zhipu", "qwen", "moonshot", "minimax", "baidu"]
PROVIDER_LABELS = {
    "deepseek": "DeepSeek",
    "openai": "OpenAI",
    "anthropic": "Anthropic (Claude)",
    "zhipu": "智谱 AI (GLM)",
    "qwen": "通义千问",
    "moonshot": "Moonshot (Kimi)",
    "minimax": "MiniMax",
    "baidu": "百度文心",
}


def print_banner():
    print("=" * 56)
    print("  Synloquer 配置向导")
    print("=" * 56)
    print()


def ask(prompt: str, default: str = "") -> str:
    """交互式提问，支持默认值"""
    if default:
        result = input(f"{prompt} [默认: {default}]: ").strip()
        return result if result else default
    else:
        return input(f"{prompt}: ").strip()


def ask_choice(prompt: str, choices: list, labels: dict = None) -> str:
    """从列表中选择"""
    print(f"\n{prompt}")
    for i, choice in enumerate(choices, 1):
        label = labels.get(choice, choice) if labels else choice
        print(f"  {i}. {label} ({choice})")
    while True:
        try:
            idx = int(input(f"请选择 (1-{len(choices)}): ").strip())
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
        except ValueError:
            pass
        print(f"请输入 1-{len(choices)} 之间的数字")


def setup_python_env():
    """设置 Python 虚拟环境"""
    print("\n--- Python 环境 ---")

    # 检测虚拟环境
    venv_python = os.path.join(VENV_DIR, "Scripts", "python.exe")
    if os.path.exists(venv_python):
        print(f"检测到已有虚拟环境: {VENV_DIR}")
        use_existing = ask("是否使用已有虚拟环境？", "y").lower()
        if use_existing in ("y", "yes", "是"):
            return venv_python

    # 询问是否创建虚拟环境
    create_venv = ask("是否创建虚拟环境？（推荐）", "y").lower()
    if create_venv in ("y", "yes", "是"):
        print(f"正在创建虚拟环境: {VENV_DIR}")
        try:
            subprocess.run([sys.executable, "-m", "ven", VENV_DIR], check=True)
            print("虚拟环境创建成功")
        except Exception as e:
            print(f"虚拟环境创建失败: {e}，将使用系统 Python")
            return sys.executable

        # 安装依赖
        if os.path.exists(REQUIREMENTS):
            print("正在安装依赖...")
            try:
                subprocess.run([venv_python, "-m", "pip", "install", "-r", REQUIREMENTS], check=True)
                print("依赖安装成功")
            except Exception as e:
                print(f"依赖安装失败: {e}")
        return venv_python
    else:
        print("使用系统 Python")
        return sys.executable


def setup_config():
    """生成并配置 config.json"""
    print("\n--- 配置文件 ---")

    # 从模板复制
    if not os.path.exists(CONFIG_FILE):
        if os.path.exists(CONFIG_EXAMPLE):
            shutil.copy2(CONFIG_EXAMPLE, CONFIG_FILE)
            print(f"已从模板创建 config.json")
        else:
            print("警告: 未找到 config.example.json，将创建空配置")
            return {}

    # 读取配置
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 引导填写
    print("\n请填写以下配置项（直接回车使用默认值）：")

    # env 文件路径
    default_env = config.get("env_file_path", str(Path.home() / "Desktop" / ".env"))
    config["env_file_path"] = ask("API 密钥 .env 文件路径", default_env)

    # 服务商选择
    default_provider = config.get("provider", "deepseek")
    config["provider"] = ask_choice("选择 AI 服务商", PROVIDERS, PROVIDER_LABELS)
    if config["provider"] != default_provider:
        print(f"已切换到 {PROVIDER_LABELS[config['provider']]}，请确保 .env 中配置了对应密钥")

    # 模型
    models = config.get("models", {})
    default_chat = models.get("chat", "deepseek-v4-pro")
    default_summary = models.get("summary", "deepseek-v4-flash")
    models["chat"] = ask("对话模型", default_chat)
    models["summary"] = ask("总结/记忆模型（需支持快速响应）", default_summary)
    config["models"] = models

    # 对话前缀
    prefix = config.get("chat_prefix", {})
    prefix["user"] = ask("用户对话前缀", prefix.get("user", "我："))
    prefix["assistant"] = ask("AI 对话前缀", prefix.get("assistant", "AI："))
    config["chat_prefix"] = prefix

    # 保存
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"\n配置已保存到: {CONFIG_FILE}")

    return config


def setup_env(config: dict):
    """引导填写 .env 密钥"""
    print("\n--- API 密钥 ---")

    env_path = config.get("env_file_path", "")
    if not env_path:
        print("未配置 env_file_path，跳过密钥配置")
        return

    # 检测 .env 文件
    if os.path.exists(env_path):
        print(f"检测到 .env 文件: {env_path}")
        edit = ask("是否需要修改密钥？", "n").lower()
        if edit not in ("y", "yes", "是"):
            return
    else:
        create = ask(f"未找到 .env 文件，是否创建？({env_path})", "y").lower()
        if create not in ("y", "yes", "是"):
            return
        # 确保目录存在
        os.makedirs(os.path.dirname(env_path), exist_ok=True)

    # 读取已有内容
    existing = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    existing[key.strip()] = value.strip()

    # 根据当前 provider 引导填写
    provider = config.get("provider", "deepseek")
    providers_config = config.get("available_providers", {})
    provider_config = providers_config.get(provider, {})
    env_key = provider_config.get("env_key", "DEEPSEEK_API_KEY")

    print(f"\n当前服务商: {PROVIDER_LABELS.get(provider, provider)}")
    print(f"需要配置密钥: {env_key}")

    existing_value = existing.get(env_key, "")
    new_value = ask(f"请输入 {env_key}", existing_value)
    existing[env_key] = new_value

    # 百度文心需要额外的 SECRET_KEY
    if provider == "baidu":
        existing["BAIDU_SECRET_KEY"] = ask("请输入 BAIDU_SECRET_KEY", existing.get("BAIDU_SECRET_KEY", ""))

    # 搜索密钥
    search_config = config.get("search", {})
    search_provider = search_config.get("provider", "bocha")
    if search_provider == "bocha":
        bocha_key = search_config.get("bocha", {}).get("env_key", "BOCHA_API_KEY")
        existing[bocha_key] = ask(f"请输入博查搜索 API Key ({bocha_key})", existing.get(bocha_key, ""))

    # 写入 .env
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# Synloquer API 密钥配置\n")
        f.write("# 请将以下密钥替换为你自己的\n\n")
        for key, value in existing.items():
            if value:
                f.write(f"{key}={value}\n")
            else:
                f.write(f"# {key}=\n")

    print(f"\n密钥已保存到: {env_path}")


def print_next_steps(config: dict):
    """打印后续步骤"""
    print("\n" + "=" * 56)
    print("  配置完成！")
    print("=" * 56)
    print()
    print("启动方式：")
    print(f"  1. 双击 启动Synloquer.bat")
    print(f"  2. 或在命令行运行: agent_env\\Scripts\\python.exe synloquer.py")
    print()
    print("配置文件：")
    print(f"  config.json: {CONFIG_FILE}")
    print(f"  .env: {config.get('env_file_path', '未配置')}")
    print()
    print("如需重新配置，运行: python setup.py")
    print()


def main():
    print_banner()

    # 1. Python 环境
    python_path = setup_python_env()

    # 2. 配置文件
    config = setup_config()

    # 3. API 密钥
    setup_env(config)

    # 4. 完成
    print_next_steps(config)

    # 询问是否立即启动
    launch = ask("\n是否立即启动 Synloquer？", "y").lower()
    if launch in ("y", "yes", "是"):
        print("\n正在启动 Synloquer...\n")
        subprocess.run([python_path, os.path.join(SCRIPT_DIR, "synloquer.py")])


if __name__ == "__main__":
    main()
