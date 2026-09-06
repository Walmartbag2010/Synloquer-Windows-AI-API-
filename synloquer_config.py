"""
Synloquer 配置模块

负责加载 config.json 和 .env 文件，提供统一的配置访问接口。
"""

import json
import os
import shutil
from pathlib import Path

import synloquer_logger as logger

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CONFIG_EXAMPLE = os.path.join(SCRIPT_DIR, "config.example.json")


def _load_config() -> dict:
    """加载 config.json，不存在则从 config.example.json 复制创建"""
    if not os.path.exists(CONFIG_FILE):
        if os.path.exists(CONFIG_EXAMPLE):
            shutil.copy2(CONFIG_EXAMPLE, CONFIG_FILE)
            logger.info(f"已从 config.example.json 创建 config.json")
        else:
            return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取 config.json 失败: {e}，使用默认配置")
        return {}


def _load_env_file(env_path: str) -> bool:
    """从指定路径加载 .env 文件到环境变量"""
    if not env_path or not os.path.exists(env_path):
        return False
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
        return True
    except Exception:
        return False


class Config:
    """统一配置访问类，加载后所有配置通过属性访问"""

    def __init__(self):
        self.raw = _load_config()

        # .env 加载
        self.env_path = self.raw.get("env_file_path", "")
        self.env_loaded = _load_env_file(self.env_path)
        if not self.env_loaded:
            for fallback in [
                str(Path.home() / "Desktop" / ".env"),
                os.path.join(os.environ.get("USERPROFILE", ""), "Desktop", ".env"),
            ]:
                if _load_env_file(fallback):
                    self.env_path = fallback
                    self.env_loaded = True
                    break

        # Provider 和模型
        self.provider = self.raw.get("provider", "deepseek")
        self.providers = self.raw.get("available_providers", {})
        provider_config = self.providers.get(self.provider, {})
        self.base_url = provider_config.get("base_url", "https://api.deepseek.com")
        self.env_key_name = provider_config.get("env_key", "DEEPSEEK_API_KEY")
        self.api_key = os.environ.get(self.env_key_name, "")

        models = self.raw.get("models", {})
        self.model_chat = models.get("chat", "deepseek-v4-pro")
        self.model_summary = models.get("summary", "deepseek-v4-flash")

        # 对话设置
        self.system_prompt = self.raw.get("system_prompt", "不要使用Markdown格式。")
        prefix_config = self.raw.get("chat_prefix", {})
        self.user_prefix = prefix_config.get("user", "我：")
        self.ai_prefix = prefix_config.get("assistant", "AI：")

        # 搜索配置
        search_config = self.raw.get("search", {})
        self.search_provider = search_config.get("provider", "bocha")
        search_provider_config = search_config.get(self.search_provider, {})
        self.bocha_base_url = search_provider_config.get("base_url", "https://api.bocha.cn/v1/web-search")
        self.bocha_env_key = search_provider_config.get("env_key", "BOCHA_API_KEY")
        self.bocha_api_key = os.environ.get(self.bocha_env_key, "")

        # 图片窗口配置
        self.image_window = self.raw.get("image_window", {})

        # 记忆系统配置
        memory_config = self.raw.get("memory", {})
        self.memory_max_items = memory_config.get("max_items", 100)
        self.memory_retrieval_top_k = memory_config.get("retrieval_top_k", 15)
        self.memory_forget_days_low = memory_config.get("forget_days_low", 30)
        self.memory_forget_days_normal = memory_config.get("forget_days_normal", 60)
        self.memory_compress_threshold = memory_config.get("compress_threshold", 80)

        # 目录路径
        self.summary_dir = os.path.join(SCRIPT_DIR, "summaries")
        self.chat_log_dir = os.path.join(SCRIPT_DIR, "chat_logs")
        self.memory_file = os.path.join(SCRIPT_DIR, "memory.json")
        self.memory_file_legacy = os.path.join(SCRIPT_DIR, "memory.md")
        self.workspace_dir = os.path.join(SCRIPT_DIR, "workspace")

        for d in [self.summary_dir, self.chat_log_dir, self.workspace_dir]:
            os.makedirs(d, exist_ok=True)

        # 文件读取限制
        self.allowed_suffixes = {
            ".txt", ".md", ".log", ".py", ".json", ".csv", ".xml", ".html",
            ".css", ".js", ".yaml", ".yml", ".ini", ".cfg", ".bat", ".ps1"
        }
        self.max_file_read_size = 50000


# 全局单例
config = Config()
