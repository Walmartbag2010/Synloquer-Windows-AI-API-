"""
Synloquer - 轻量级终端 LLM 对话助手

支持多服务商适配（OpenAI兼容/Anthropic/百度文心）、工具调用、长期记忆。
配置见 config.json，密钥见 .env 文件。
"""

import requests
import json
import os
import math
import time
import subprocess
import webbrowser
import ctypes
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

# ================== 配置 ==================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CONFIG_EXAMPLE = os.path.join(SCRIPT_DIR, "config.example.json")


def _load_config() -> dict:
    """加载 config.json，不存在则从 config.example.json 复制创建"""
    if not os.path.exists(CONFIG_FILE):
        if os.path.exists(CONFIG_EXAMPLE):
            import shutil
            shutil.copy2(CONFIG_EXAMPLE, CONFIG_FILE)
            print(f"[配置] 已从 config.example.json 创建 config.json")
        else:
            return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[配置] 读取 config.json 失败: {e}，使用默认配置")
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


# 加载配置
CONFIG = _load_config()

# 从配置读取 env 文件路径，加载密钥
ENV_PATH = CONFIG.get("env_file_path", "")
ENV_LOADED = _load_env_file(ENV_PATH)
if not ENV_LOADED:
    # 兜底：尝试桌面默认路径
    for fallback in [
        str(Path.home() / "Desktop" / ".env"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop", ".env"),
        r"D:\HuaweiMoveData\Users\HUAWEI\Desktop\.env",
    ]:
        if _load_env_file(fallback):
            ENV_PATH = fallback
            ENV_LOADED = True
            break

# 从配置读取 provider 和模型
PROVIDER = CONFIG.get("provider", "deepseek")
PROVIDERS = CONFIG.get("available_providers", {})
provider_config = PROVIDERS.get(PROVIDER, {})

BASE_URL = provider_config.get("base_url", "https://api.deepseek.com")
ENV_KEY_NAME = provider_config.get("env_key", "DEEPSEEK_API_KEY")
API_KEY = os.environ.get(ENV_KEY_NAME, "")

MODELS = CONFIG.get("models", {})
MODEL_CHAT = MODELS.get("chat", "deepseek-v4-pro")
MODEL_SUMMARY = MODELS.get("summary", "deepseek-v4-flash")

# 系统提示词
SYSTEM_PROMPT = CONFIG.get("system_prompt", "不要使用Markdown格式。")

# 对话前缀（可自定义）
CHAT_PREFIX_CONFIG = CONFIG.get("chat_prefix", {})
USER_PREFIX = CHAT_PREFIX_CONFIG.get("user", "我：")
AI_PREFIX = CHAT_PREFIX_CONFIG.get("assistant", "AI：")

# 搜索工具配置
SEARCH_CONFIG = CONFIG.get("search", {})
SEARCH_PROVIDER = SEARCH_CONFIG.get("provider", "bocha")
search_provider_config = SEARCH_CONFIG.get(SEARCH_PROVIDER, {})
BOCHA_BASE_URL = search_provider_config.get("base_url", "https://api.bocha.cn/v1/web-search")
BOCHA_ENV_KEY = search_provider_config.get("env_key", "BOCHA_API_KEY")
BOCHA_API_KEY = os.environ.get(BOCHA_ENV_KEY, "")

# 图片窗口配置
IMAGE_WINDOW_CONFIG = CONFIG.get("image_window", {})

# 文件路径
SUMMARY_DIR = os.path.join(SCRIPT_DIR, "summaries")
CHAT_LOG_DIR = os.path.join(SCRIPT_DIR, "chat_logs")
MEMORY_FILE = os.path.join(SCRIPT_DIR, "memory.md")
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, "workspace")

os.makedirs(SUMMARY_DIR, exist_ok=True)
os.makedirs(CHAT_LOG_DIR, exist_ok=True)
os.makedirs(WORKSPACE_DIR, exist_ok=True)

# 允许读取的文件后缀
ALLOWED_SUFFIXES = {".txt", ".md", ".log", ".py", ".json", ".csv", ".xml", ".html", ".css", ".js", ".yaml", ".yml", ".ini", ".cfg", ".bat", ".ps1"}
MAX_FILE_READ_SIZE = 50000  # 字符数

# ================== Provider 适配层 ==================
# 不同服务商的 API 调用方式有差异，这里统一适配

# OpenAI 兼容格式的服务商（端点、请求体、响应格式都兼容）
_OPENAI_COMPATIBLE_PROVIDERS = {"deepseek", "openai", "zhipu", "qwen", "moonshot", "minimax"}

# 百度文心 access_token 缓存
_baidu_access_token = None
_baidu_token_expire_time = 0


def _get_baidu_access_token() -> str:
    """百度文心需要先用 API Key + Secret Key 换取 access_token"""
    global _baidu_access_token, _baidu_token_expire_time
    if _baidu_access_token and time.time() < _baidu_token_expire_time:
        return _baidu_access_token

    api_key = os.environ.get("BAIDU_API_KEY", "")
    secret_key = os.environ.get("BAIDU_SECRET_KEY", "")
    if not api_key or not secret_key:
        raise Exception("百度文心需要 BAIDU_API_KEY 和 BAIDU_SECRET_KEY")

    token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    resp = requests.post(token_url, timeout=30)
    data = resp.json()
    _baidu_access_token = data.get("access_token", "")
    _baidu_token_expire_time = time.time() + data.get("expires_in", 2592000) - 300
    return _baidu_access_token


def _get_provider_headers() -> dict:
    """根据 provider 返回请求头"""
    if PROVIDER == "anthropic":
        return {
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    elif PROVIDER == "baidu":
        return {"Content-Type": "application/json"}
    else:
        return {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }


def _get_provider_endpoint() -> str:
    """根据 provider 返回 API 端点"""
    if PROVIDER == "anthropic":
        return f"{BASE_URL}/v1/messages"
    elif PROVIDER == "baidu":
        token = _get_baidu_access_token()
        return f"{BASE_URL}/chat/completions?access_token={token}"
    else:
        return f"{BASE_URL}/chat/completions"


def _build_chat_request(model: str, messages: list, stream: bool = False,
                         tools: list = None, tool_choice: str = None,
                         temperature: float = 0.7, max_tokens: int = 4096,
                         thinking_disabled: bool = False) -> dict:
    """根据 provider 构建请求体"""
    if PROVIDER == "anthropic":
        # Anthropic 格式：system 独立参数，max_tokens 必填
        system_content = ""
        chat_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
            elif m.get("role") in ("user", "assistant"):
                # Anthropic 不支持 tool_calls 字段的 OpenAI 格式，简化处理
                msg = {"role": m["role"], "content": m.get("content", "")}
                chat_messages.append(msg)
        body = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "stream": stream,
            "temperature": temperature,
        }
        if system_content:
            body["system"] = system_content
        # Anthropic 工具调用格式不同，暂不发送 tools（主对话时会提示）
        return body
    else:
        # OpenAI 兼容格式
        body = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"
        if thinking_disabled:
            body["thinking"] = {"type": "disabled"}
        return body


def _parse_stream_line(line: str):
    """
    根据 provider 解析流式响应的一行。
    返回 (content_chunk, tool_calls_delta) 或 None（表示跳过）。
    content_chunk 为 "__done__" 时表示流结束。
    """
    if not line:
        return None

    if PROVIDER == "anthropic":
        # Anthropic SSE 格式：event: xxx / data: {...}
        if line.startswith("event: "):
            return ("", None)  # 事件类型行，跳过
        if line.startswith("data: "):
            data = line[6:]
            try:
                obj = json.loads(data)
                obj_type = obj.get("type", "")
                if obj_type == "content_block_delta":
                    delta = obj.get("delta", {})
                    text = delta.get("text", "")
                    return (text, None)
                elif obj_type == "message_delta":
                    return ("", None)
            except json.JSONDecodeError:
                pass
        return None
    else:
        # OpenAI 兼容格式
        if not line.startswith("data: "):
            return None
        chunk = line[6:]
        if chunk == "[DONE]":
            return ("__done__", None)
        try:
            obj = json.loads(chunk)
            delta = obj.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content", "")
            tool_calls_delta = delta.get("tool_calls", [])
            return (content, tool_calls_delta)
        except json.JSONDecodeError:
            return None


def _parse_non_stream_response(resp) -> str:
    """根据 provider 解析非流式响应，返回文本内容"""
    data = resp.json()
    if PROVIDER == "anthropic":
        # Anthropic 格式：content 是数组，取第一个 text 块
        content_blocks = data.get("content", [])
        text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        return "".join(text_parts)
    else:
        # OpenAI 兼容格式
        return data["choices"][0]["message"]["content"]


def provider_supports_tools() -> bool:
    """当前 provider 是否支持工具调用"""
    return PROVIDER in _OPENAI_COMPATIBLE_PROVIDERS or PROVIDER == "baidu"


# ================== 工具定义 ==================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "使用博查搜索引擎搜索网页信息，获取最新的新闻、资料、事实数据等。当用户询问实时信息、最新动态、需要查证事实时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，简洁明确"
                    },
                    "count": {
                        "type": "integer",
                        "description": "返回结果数量，1-20，默认5",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地文本文件的内容。支持工作区内的相对路径或绝对路径。当用户要求查看、读取某个文件的内容时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "文件路径，可以是工作区相对路径或绝对路径"
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出指定目录下的文件和子目录，按类型分组显示（图片、文档、视频、音频、代码等）。当用户需要了解某个目录下有哪些文件时使用。图片文件会完整列出，其他类型超过10个会提示用file_type筛选。",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "目录路径，默认为工作区根目录"
                    },
                    "file_type": {
                        "type": "string",
                        "description": "只列出指定类型的文件，可选: all(全部), image(图片), document(文档), video(视频), audio(音频), code(代码), archive(压缩包), other(其他)",
                        "default": "all"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "安全计算数学表达式，支持加减乘除、幂运算、平方根、三角函数等。当用户需要进行数学计算时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，例如 2+2*3 或 sqrt(16)"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_image",
            "description": "在新窗口中展示图片。当用户要求查看图片、照片、示意图、截图，或你认为需要用图片辅助说明时使用。支持网络图片URL和本地文件路径。",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "图片来源，可以是网络URL（http/https开头）或本地文件路径"
                    }
                },
                "required": ["source"]
            }
        }
    }
]


# ================== 工具实现 ==================
def tool_web_search(query: str, count: int = 5) -> str:
    """博查网页搜索"""
    try:
        resp = requests.post(
            BOCHA_BASE_URL,
            headers={
                "Authorization": f"Bearer {BOCHA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "count": min(max(count, 1), 20),
                "freshness": "noLimit",
                "summary": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        web_pages = data.get("data", {}).get("webPages", {})
        results = web_pages.get("value", [])

        if not results:
            return "未找到相关搜索结果。"

        output = []
        for idx, item in enumerate(results, 1):
            name = item.get("name", "无标题")
            url = item.get("url", "")
            snippet = item.get("summary", item.get("snippet", ""))
            site_name = item.get("siteName", "")
            date_pub = item.get("datePublished", "")

            line = f"{idx}. {name}"
            if site_name:
                line += f"（来源: {site_name}）"
            if date_pub:
                line += f" [时间: {date_pub}]"
            output.append(line)
            if snippet:
                output.append(f"   {snippet}")
            if url:
                output.append(f"   链接: {url}")
            output.append("")

        return "\n".join(output).strip()

    except Exception as e:
        return f"搜索失败: {str(e)}"


def _resolve_path(filepath: str) -> Path:
    """解析文件路径，相对路径基于工作区"""
    p = Path(filepath)
    if not p.is_absolute():
        p = WORKSPACE_DIR / p
    return p.resolve()


def tool_read_file(filepath: str) -> str:
    """读取本地文件"""
    try:
        p = _resolve_path(filepath)

        if not p.exists():
            return f"错误: 文件不存在 - {p}"
        if not p.is_file():
            return f"错误: 不是一个文件 - {p}"
        if p.suffix.lower() not in ALLOWED_SUFFIXES:
            return f"错误: 不支持的文件类型 {p.suffix}，允许: {', '.join(sorted(ALLOWED_SUFFIXES))}"

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if len(content) > MAX_FILE_READ_SIZE:
            content = content[:MAX_FILE_READ_SIZE] + f"\n... (文件过大，已截断，共 {len(content)} 字符，仅显示前 {MAX_FILE_READ_SIZE} 字符)"

        return f"文件: {p}\n\n{content}"

    except Exception as e:
        return f"读取文件失败: {str(e)}"


def tool_list_files(directory: str = None, file_type: str = "all") -> str:
    """
    列出目录文件，按类型分组显示。
    file_type: all(全部) / image(图片) / document(文档) / video(视频) / audio(音频) / code(代码) / other(其他)
    """
    # 文件类型分类
    TYPE_EXTS = {
        "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg", ".psd", ".dng", ".raw", ".heic"},
        "document": {".txt", ".md", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".rtf", ".epub"},
        "video": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
        "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".ape"},
        "code": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".php", ".rb", ".sh", ".bat", ".ps1", ".json", ".xml", ".yaml", ".yml", ".ini", ".cfg"},
        "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    }

    def get_file_type(ext: str) -> str:
        ext = ext.lower()
        for type_name, exts in TYPE_EXTS.items():
            if ext in exts:
                return type_name
        return "other"

    try:
        if directory:
            p = _resolve_path(directory)
        else:
            p = Path(WORKSPACE_DIR).resolve()

        if not p.exists():
            return f"错误: 目录不存在 - {p}"
        if not p.is_dir():
            return f"错误: 不是一个目录 - {p}"

        dirs = []
        files_by_type = {k: [] for k in TYPE_EXTS.keys()}
        files_by_type["other"] = []

        for item in sorted(p.iterdir()):
            if item.is_dir():
                dirs.append(item.name)
            else:
                ftype = get_file_type(item.suffix)
                size = item.stat().st_size
                files_by_type[ftype].append((item.name, size))

        # 如果指定了类型，只显示该类型
        if file_type != "all":
            if file_type not in files_by_type:
                return f"错误: 未知的文件类型 '{file_type}'，支持: all, {', '.join(TYPE_EXTS.keys())}, other"
            target_files = files_by_type[file_type]
            if not target_files:
                return f"目录 {p} 中没有 {file_type} 类型的文件。"
            lines = [f"目录: {p}", f"类型: {file_type} ({len(target_files)} 个)", ""]
            for name, size in target_files:
                lines.append(f"  {name} ({size} 字节)")
            return "\n".join(lines)

        # 全部类型：按组显示
        lines = [f"目录: {p}", ""]

        if dirs:
            lines.append(f"[文件夹] ({len(dirs)} 个)")
            for d in dirs:
                lines.append(f"  {d}/")
            lines.append("")

        type_labels = {
            "image": "图片",
            "document": "文档",
            "video": "视频",
            "audio": "音频",
            "code": "代码",
            "archive": "压缩包",
            "other": "其他",
        }

        total_files = sum(len(v) for v in files_by_type.values())
        lines.append(f"[文件] (共 {total_files} 个)")
        lines.append("")

        for ftype, label in type_labels.items():
            files = files_by_type[ftype]
            if not files:
                continue
            lines.append(f"  {label} ({len(files)} 个):")
            # 图片类型完整列出，其他类型超过10个只显示前10个
            max_show = len(files) if ftype == "image" else 10
            for name, size in files[:max_show]:
                lines.append(f"    {name} ({size} 字节)")
            if len(files) > max_show:
                lines.append(f"    ... 还有 {len(files) - max_show} 个文件，可用 file_type='{ftype}' 查看全部")
            lines.append("")

        return "\n".join(lines).rstrip()

    except Exception as e:
        return f"列出文件失败: {str(e)}"


def tool_calculator(expression: str) -> str:
    """安全计算器"""
    try:
        # 安全的命名空间，只允许数学函数
        safe_namespace = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sqrt": math.sqrt, "pow": math.pow, "exp": math.exp,
            "log": math.log, "log2": math.log2, "log10": math.log10,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "asin": math.asin, "acos": math.acos, "atan": math.atan,
            "pi": math.pi, "e": math.e, "ceil": math.ceil, "floor": math.floor,
            "factorial": math.factorial, "gcd": math.gcd,
        }
        result = eval(expression, {"__builtins__": {}}, safe_namespace)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


def _get_image_window_size() -> tuple:
    """根据屏幕分辨率和配置计算图片窗口大小，居中显示"""
    try:
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        screen_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        width_ratio = IMAGE_WINDOW_CONFIG.get("width_ratio", 0.55)
        height_ratio = IMAGE_WINDOW_CONFIG.get("height_ratio", 0.65)
        max_width = IMAGE_WINDOW_CONFIG.get("max_width", 1100)
        max_height = IMAGE_WINDOW_CONFIG.get("max_height", 800)
        width = min(int(screen_w * width_ratio), max_width)
        height = min(int(screen_h * height_ratio), max_height)
        return (width, height)
    except Exception:
        return (900, 700)  # 兜底默认大小


def _resize_window_by_pid(pid: int, width: int, height: int) -> bool:
    """
    根据进程ID找到其顶层窗口，调整大小并居中显示。
    启动后轮询等待窗口出现（最多3秒）。
    """
    try:
        user32 = ctypes.windll.user32
        found_hwnd = []

        def enum_callback(hwnd, lParam):
            window_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if window_pid.value == pid and user32.IsWindowVisible(hwnd):
                found_hwnd.append(hwnd)
                return 0  # 停止枚举
            return 1  # 继续枚举

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        callback = WNDENUMPROC(enum_callback)

        # 轮询等待窗口出现（最多3秒）
        for _ in range(30):
            found_hwnd.clear()
            user32.EnumWindows(callback, 0)
            if found_hwnd:
                break
            time.sleep(0.1)

        if not found_hwnd:
            return False

        hwnd = found_hwnd[0]

        # 先恢复窗口（退出全屏/最小化状态）
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.1)

        # 获取屏幕分辨率，计算居中位置
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)

        # 设置窗口大小和位置（保持Z序和激活状态不变）
        # SWP_NOZORDER(0x0004) | SWP_NOACTIVATE(0x0010) = 0x0014
        user32.SetWindowPos(hwnd, 0, x, y, width, height, 0x0014)

        return True
    except Exception:
        return False


def _open_image_file(filepath: str) -> tuple:
    """
    按优先级尝试多种方式打开图片，确保进程完全分离。
    返回 (是否成功, 信息)
    """
    errors = []
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP：子进程独立于父进程
    CREATE_FLAGS = 0x00000008 | 0x00000200

    if not os.path.exists(filepath):
        return (False, f"文件不存在: {filepath}")
    if not os.path.isfile(filepath):
        return (False, f"不是文件: {filepath}")

    # 旧版 Windows 照片查看器（首选，无需文件关联，支持放大缩小）
    for pv_path in [r"C:\Program Files\Windows Photo Viewer\PhotoViewer.dll",
                     r"C:\Program Files (x86)\Windows Photo Viewer\PhotoViewer.dll"]:
        if os.path.exists(pv_path):
            try:
                proc = subprocess.Popen(
                    ['rundll32.exe', pv_path, 'ImageView_Fullscreen', filepath],
                    creationflags=CREATE_FLAGS, close_fds=True
                )
                time.sleep(0.3)
                win_w, win_h = _get_image_window_size()
                resized = _resize_window_by_pid(proc.pid, win_w, win_h)
                size_info = f"（窗口 {win_w}×{win_h}，居中）" if resized else ""
                return (True, f"Windows照片查看器打开{size_info}")
            except Exception as e:
                errors.append(f"photoviewer: {e}")
            break
    else:
        errors.append("photoviewer: 旧版照片查看器不存在")

    # 备用打开方式，按优先级尝试
    fallback_methods = [
        ("画图", ['mspaint.exe', filepath], 0.5),
        ("默认程序", None, 0.5),  # os.startfile 特殊处理
        ("资源管理器", ['explorer.exe', filepath], 0.8),
        ("浏览器", None, 0.5),    # webbrowser 特殊处理
    ]

    for name, cmd, wait_time in fallback_methods:
        try:
            if name == "默认程序":
                os.startfile(filepath)
            elif name == "浏览器":
                webbrowser.open(f'file:///{filepath.replace(os.sep, "/")}')
            else:
                subprocess.Popen(cmd, creationflags=CREATE_FLAGS, close_fds=True)
            time.sleep(wait_time)
            return (True, f"{name}打开")
        except Exception as e:
            errors.append(f"{name}: {e}")

    return (False, "所有打开方式均失败: " + "; ".join(errors))


def tool_show_image(source: str) -> str:
    """在新窗口中展示图片（支持网络URL和本地路径）"""
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg"}
    temp_dir = os.path.join(SCRIPT_DIR, "temp_images")

    try:
        if source.startswith(("http://", "https://")):
            # 网络图片：下载到临时目录
            resp = requests.get(source, timeout=30)
            resp.raise_for_status()

            # 从URL提取扩展名
            url_path = source.split("?")[0].split("#")[0]
            ext = os.path.splitext(url_path)[1].lower()
            if ext not in IMAGE_EXTS:
                # 尝试从Content-Type判断
                content_type = resp.headers.get("Content-Type", "")
                if "jpeg" in content_type or "jpg" in content_type:
                    ext = ".jpg"
                elif "png" in content_type:
                    ext = ".png"
                elif "gif" in content_type:
                    ext = ".gif"
                elif "webp" in content_type:
                    ext = ".webp"
                elif "bmp" in content_type:
                    ext = ".bmp"
                else:
                    ext = ".png"

            os.makedirs(temp_dir, exist_ok=True)
            temp_name = f"img_{int(time.time() * 1000)}{ext}"
            temp_path = os.path.join(temp_dir, temp_name)

            with open(temp_path, "wb") as f:
                f.write(resp.content)

            # 确保文件完全写入后再打开
            time.sleep(0.3)

            success, msg = _open_image_file(temp_path)
            if success:
                return f"已在新窗口中展示图片（{msg}）\n来源: {source}\n本地保存: {temp_path}"
            else:
                return f"图片已下载但自动打开失败\n{msg}\n文件已保存到: {temp_path}\n请手动打开查看"

        else:
            # 本地文件
            p = _resolve_path(source)
            if not p.exists():
                return f"错误: 文件不存在 - {p}"
            if not p.is_file():
                return f"错误: 不是一个文件 - {p}"
            if p.suffix.lower() not in IMAGE_EXTS:
                return f"错误: 不支持的图片格式 {p.suffix}，支持: {', '.join(sorted(IMAGE_EXTS))}"

            success, msg = _open_image_file(str(p))
            if success:
                return f"已在新窗口中展示图片（{msg}）\n文件: {p}"
            else:
                return f"图片打开失败\n{msg}\n文件路径: {p}\n请手动打开查看"

    except requests.exceptions.RequestException as e:
        return f"图片下载失败: {str(e)}"
    except Exception as e:
        return f"展示图片失败: {str(e)}"


# 工具分发
TOOL_FUNCTIONS = {
    "web_search": tool_web_search,
    "read_file": tool_read_file,
    "list_files": tool_list_files,
    "calculator": tool_calculator,
    "show_image": tool_show_image,
}


# ================== 长期记忆 ==================
def load_memory() -> str:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def build_system_prompt(memory: str) -> str:
    if memory:
        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"以下是你在之前对话中积累的记忆，请在回答时参考：\n{memory}"
        )
    return SYSTEM_PROMPT


def update_memory(conversation_text: str):
    """对话结束后，用 flash 模型更新长期记忆（追加保留式，不删除已有记忆点）"""
    existing_memory = load_memory()

    if existing_memory:
        prompt = (
            "以下是已有的长期记忆（必须全部保留，除非新对话明确否定了某条信息）：\n"
            f"{existing_memory}\n\n"
            "以下是本次对话的内容：\n"
            f"{conversation_text}\n\n"
            "请更新长期记忆，严格遵守以下规则：\n"
            "1. 必须保留已有记忆中的所有信息点，一条都不能删除\n"
            "2. 从本次对话中提取新的值得长期记住的信息点（如用户偏好、事实、计划、问题、情绪状态等），添加到记忆中\n"
            "3. 只有当本次对话明确否定或纠正了某条已有记忆时，才更新或删除那条记忆\n"
            "4. 输出格式：每条记忆一行，以 - 开头\n"
            "5. 只输出记忆内容本身，不要输出解释、标题或多余文字"
        )
    else:
        prompt = (
            "以下是本次对话的内容：\n"
            f"{conversation_text}\n\n"
            "请提取其中值得长期记住的关键信息点（如用户偏好、事实、计划、问题、情绪状态等），整理成记忆清单。每条一行，以 - 开头。只输出记忆内容本身。"
        )

    print("\n" + "-" * 56)
    print("  正在更新长期记忆...")
    print("-" * 56)

    try:
        resp = requests.post(
            _get_provider_endpoint(),
            headers=_get_provider_headers(),
            json=_build_chat_request(
                model=MODEL_SUMMARY,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0.3,
                max_tokens=4096,
                thinking_disabled=True,
            ),
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"[记忆更新失败] API 返回 {resp.status_code}，已有记忆保持不变")
            return

        new_memory = _parse_non_stream_response(resp).strip()

        # 安全校验：如果已有记忆且新记忆明显变短，警告可能丢失并追加
        if existing_memory and len(new_memory) < len(existing_memory) * 0.5:
            print(f"[警告] 新记忆({len(new_memory)}字符)明显短于旧记忆({len(existing_memory)}字符)，可能丢失信息")
            print("[警告] 为安全起见，保留旧记忆，新记忆追加到末尾")
            new_memory = existing_memory + "\n" + new_memory

        # 写入前备份旧记忆
        if existing_memory and os.path.exists(MEMORY_FILE):
            backup_path = MEMORY_FILE + ".bak"
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(existing_memory)

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(new_memory)

        print(f"长期记忆已更新: {MEMORY_FILE}")
        if existing_memory:
            print(f"旧记忆已备份: {MEMORY_FILE}.bak")
        print()
        print(new_memory)
    except Exception as e:
        print(f"[记忆更新失败] {e}，已有记忆保持不变")


# ================== 全局状态 ==================
memory = load_memory()
messages = [{"role": "system", "content": build_system_prompt(memory)}]


def print_header():
    print("=" * 56)
    print("  AI 终端聊天室（工具增强版）")
    print(f"  服务商: {PROVIDER} | 模型: {MODEL_CHAT}")
    print(f"  总结模型: {MODEL_SUMMARY}")
    if ENV_LOADED:
        print(f"  密钥文件: {ENV_PATH}")
    else:
        print("  [警告] 未找到 .env 密钥文件，请检查 config.json 中的 env_file_path")
    print(f"  搜索: {SEARCH_PROVIDER} | 工具: 搜索/文件读取/文件列表/计算器/图片")
    print(f"  对话前缀: 用户=\"{USER_PREFIX}\" AI=\"{AI_PREFIX}\"")
    if not provider_supports_tools():
        print(f"  [提示] 当前服务商 {PROVIDER} 暂不支持工具调用")
    if memory:
        print(f"  长期记忆: 已加载 ({len(memory)} 字符)")
    else:
        print("  长期记忆: 暂无")
    print("  输入消息开始对话，输入 exit 或 quit 结束并总结")
    print("=" * 56)
    print()


# ================== 核心聊天（支持工具调用） ==================
def chat_stream(user_input: str) -> str:
    """发送消息，支持工具调用循环，流式输出最终回复"""
    messages.append({"role": "user", "content": user_input})

    full_reply = ""
    max_tool_rounds = 8  # 最多8轮工具调用，防止死循环
    tool_round = 0

    while tool_round < max_tool_rounds:
        tool_round += 1
        print(AI_PREFIX, end="", flush=True)

        try:
            # 根据 provider 决定是否发送工具（Anthropic 暂不支持工具调用）
            use_tools = TOOLS if provider_supports_tools() else None
            resp = requests.post(
                _get_provider_endpoint(),
                headers=_get_provider_headers(),
                json=_build_chat_request(
                    model=MODEL_CHAT,
                    messages=messages,
                    stream=True,
                    tools=use_tools,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=4096,
                ),
                stream=True,
                timeout=120,
            )

            if resp.status_code != 200:
                print(f"\n[错误] API 返回 {resp.status_code}: {resp.text[:200]}")
                messages.pop()
                return ""

            # 收集流式响应
            assistant_content = ""
            tool_calls = []

            for line in resp.iter_lines(decode_unicode=True):
                parsed = _parse_stream_line(line)
                if parsed is None:
                    continue
                content, delta_tool_calls = parsed
                if content == "__done__":
                    break

                if content:
                    assistant_content += content
                    print(content, end="", flush=True)

                # 工具调用（仅 OpenAI 兼容格式，Anthropic 不返回此字段）
                if delta_tool_calls:
                    for tc in delta_tool_calls:
                        idx = tc.get("index", 0)
                        while len(tool_calls) <= idx:
                            tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})

                        if "id" in tc:
                            tool_calls[idx]["id"] = tc["id"]
                        if "type" in tc:
                            tool_calls[idx]["type"] = tc["type"]
                        fn = tc.get("function", {})
                        if "name" in fn:
                            tool_calls[idx]["function"]["name"] = fn["name"]
                        if "arguments" in fn:
                            tool_calls[idx]["function"]["arguments"] += fn["arguments"]

            print()

            if tool_calls:
                # 保存助手消息（含工具调用），供下一轮 LLM 调用使用
                assistant_msg = {"role": "assistant", "content": assistant_content or None}
                assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                for tc in tool_calls:
                    tool_name = tc["function"]["name"]
                    try:
                        tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                    except json.JSONDecodeError:
                        tool_args = {}

                    # 显示工具调用提示
                    if tool_name == "web_search":
                        print(f"  [正在搜索: {tool_args.get('query', '')}]")
                    elif tool_name == "read_file":
                        print(f"  [正在读取文件: {tool_args.get('filepath', '')}]")
                    elif tool_name == "list_files":
                        print(f"  [正在列出文件: {tool_args.get('directory', WORKSPACE_DIR)}]")
                    elif tool_name == "calculator":
                        print(f"  [正在计算: {tool_args.get('expression', '')}]")
                    elif tool_name == "show_image":
                        print(f"  [正在展示图片: {tool_args.get('source', '')}]")
                    else:
                        print(f"  [正在调用工具: {tool_name}]")

                    # 执行工具
                    func = TOOL_FUNCTIONS.get(tool_name)
                    if func:
                        try:
                            result = func(**tool_args)
                        except Exception as e:
                            result = f"工具执行出错: {str(e)}"
                    else:
                        result = f"未知工具: {tool_name}"

                    # 工具结果作为 tool 角色消息
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                    # 显示工具结果摘要（前200字符）
                    result_preview = result.replace("\n", " ")[:200]
                    if len(result) > 200:
                        result_preview += "..."
                    print(f"  [工具结果] {result_preview}")
                    print()

                # 继续循环，让模型基于工具结果生成回复
                continue

            else:
                # 没有工具调用，这是最终回复
                full_reply = assistant_content
                messages.append({"role": "assistant", "content": full_reply})
                return full_reply

        except requests.exceptions.Timeout:
            print("\n[错误] 请求超时，请检查网络后重试")
            if messages and messages[-1]["role"] == "user":
                messages.pop()
            return ""
        except requests.exceptions.ConnectionError:
            print("\n[错误] 无法连接到 DeepSeek 服务器，请检查网络")
            if messages and messages[-1]["role"] == "user":
                messages.pop()
            return ""
        except Exception as e:
            print(f"\n[错误] {e}")
            if messages and messages[-1]["role"] == "user":
                messages.pop()
            return ""

    # 超过最大工具调用轮数
    print("[提示] 已达到最大工具调用轮数，结束本次回复")
    full_reply = assistant_content if 'assistant_content' in dir() else ""
    if full_reply:
        messages.append({"role": "assistant", "content": full_reply})
    return full_reply


# ================== 总结 ==================
def summarize_conversation() -> str:
    conversation_lines = []
    for msg in messages:
        if msg["role"] == "user":
            conversation_lines.append(f"{USER_PREFIX}{msg['content']}")
        elif msg["role"] == "assistant" and msg.get("content"):
            conversation_lines.append(f"{AI_PREFIX}{msg['content']}")

    conversation_text = "\n".join(conversation_lines)
    if not conversation_text.strip():
        return "（无对话内容）"

    summary_prompt = (
        "请阅读以下对话，完成两件事：\n"
        "1. 用简洁的语言总结对话的主要内容和话题走向\n"
        "2. 列出值得记住的关键信息点\n\n"
        f"对话内容：\n{conversation_text}"
    )

    print("\n" + "-" * 56)
    print("  正在生成对话总结...")
    print("-" * 56)

    try:
        resp = requests.post(
            _get_provider_endpoint(),
            headers=_get_provider_headers(),
            json=_build_chat_request(
                model=MODEL_SUMMARY,
                messages=[{"role": "user", "content": summary_prompt}],
                stream=False,
                temperature=0.3,
                max_tokens=2048,
                thinking_disabled=True,
            ),
            timeout=60,
        )
        if resp.status_code != 200:
            return f"总结失败: API 返回 {resp.status_code}"
        return _parse_non_stream_response(resp)
    except Exception as e:
        return f"总结失败: {e}"


def save_summary(summary: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_summary_{timestamp}.md"
    filepath = os.path.join(SUMMARY_DIR, filename)

    first_user_msg = next(
        (m["content"][:30] for m in messages if m["role"] == "user"),
        "未命名对话"
    )
    msg_count = sum(1 for m in messages if m["role"] in ("user", "assistant") and m.get("content"))

    content = (
        f"# 对话总结\n\n"
        f"- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- **对话主题**: {first_user_msg}\n"
        f"- **消息轮次**: {msg_count}\n\n"
        f"---\n\n"
        f"{summary}\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n总结已保存到: {filepath}")
    return filepath


def save_chat_log():
    """保存完整的原始对话记录（逐字）到 chat_logs 目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_{timestamp}.md"
    filepath = os.path.join(CHAT_LOG_DIR, filename)

    first_user_msg = next(
        (m["content"][:30] for m in messages if m["role"] == "user"),
        "未命名对话"
    )
    msg_count = sum(1 for m in messages if m["role"] in ("user", "assistant") and m.get("content"))

    lines = []
    lines.append(f"# 对话记录")
    lines.append("")
    lines.append(f"- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **对话主题**: {first_user_msg}")
    lines.append(f"- **消息轮次**: {msg_count}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in messages:
        role = msg["role"]
        content = msg.get("content")

        if role == "system":
            continue
        elif role == "user":
            lines.append(f"## 我")
            lines.append("")
            lines.append(content)
            lines.append("")
        elif role == "assistant":
            lines.append(f"## AI")
            lines.append("")
            if content:
                lines.append(content)
                lines.append("")
            # 工具调用记录
            tool_calls = msg.get("tool_calls", [])
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                except json.JSONDecodeError:
                    tool_args = {}
                args_str = ", ".join(f"{k}={v}" for k, v in tool_args.items())
                lines.append(f"> 调用工具: `{tool_name}`({args_str})")
                lines.append("")
        elif role == "tool":
            lines.append(f"### 工具返回")
            lines.append("")
            lines.append(f"```\n{content}\n```")
            lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"完整对话记录已保存到: {filepath}")
    return filepath


# ================== 主函数 ==================
def main():
    print_header()

    while True:
        try:
            user_input = input(USER_PREFIX).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "退出"):
            break

        print()
        chat_stream(user_input)
        print()

    # 对话结束
    if any(m["role"] == "user" for m in messages):
        conversation_lines = []
        for msg in messages:
            if msg["role"] == "user":
                conversation_lines.append(f"{USER_PREFIX}{msg['content']}")
            elif msg["role"] == "assistant" and msg.get("content"):
                conversation_lines.append(f"{AI_PREFIX}{msg['content']}")
        conversation_text = "\n".join(conversation_lines)

        summary = summarize_conversation()
        print()
        print(summary)
        save_summary(summary)
        save_chat_log()
        update_memory(conversation_text)
    else:
        print("\n（未进行对话，跳过总结）")

    print("\n再见！")


if __name__ == "__main__":
    main()
