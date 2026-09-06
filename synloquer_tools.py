"""
Synloquer 工具调用系统

5个内置工具：
1. web_search - 博查联网搜索
2. read_file  - 读取本地文件
3. list_files - 列出目录文件（按类型分组）
4. calculator - 安全计算器
5. show_image - 新窗口展示图片
"""

import json
import math
import os
import subprocess
import time
import webbrowser
import ctypes
from ctypes import wintypes
from pathlib import Path

import requests

import synloquer_logger as logger
from synloquer_config import config


# ================== 工具定义（OpenAI function calling 格式） ==================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "使用博查搜索引擎搜索互联网信息，返回搜索结果列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地文本文件内容，支持相对路径（基于workspace目录）和绝对路径",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "文件路径，相对路径基于workspace目录"},
                },
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出指定目录下的文件和文件夹，按类型分组显示",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "目录路径，默认为workspace目录"},
                    "file_type": {
                        "type": "string",
                        "description": "筛选文件类型：all/image/document/video/audio/code/archive/other",
                        "default": "all",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "安全数学计算器，支持基本运算和常用数学函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如 sqrt(16) + 2^3"},
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_image",
            "description": "在新窗口中展示图片，支持网络URL和本地路径，窗口自动调整大小居中",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "图片URL或本地文件路径"},
                },
                "required": ["source"],
            },
        },
    },
]


# ================== 工具实现 ==================

def tool_web_search(query: str) -> str:
    """博查联网搜索"""
    try:
        resp = requests.post(
            config.bocha_base_url,
            headers={"Authorization": f"Bearer {config.bocha_api_key}", "Content-Type": "application/json"},
            json={"query": query, "summary": True},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("data", {}).get("webPages", {}).get("value", [])
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
        logger.error(f"搜索失败: {e}")
        return f"搜索失败: {str(e)}"


def _resolve_path(filepath: str) -> Path:
    """解析文件路径，相对路径基于工作区"""
    p = Path(filepath)
    if not p.is_absolute():
        p = Path(config.workspace_dir) / p
    return p.resolve()


def tool_read_file(filepath: str) -> str:
    """读取本地文件"""
    try:
        p = _resolve_path(filepath)
        if not p.exists():
            return f"错误: 文件不存在 - {p}"
        if not p.is_file():
            return f"错误: 不是一个文件 - {p}"
        if p.suffix.lower() not in config.allowed_suffixes:
            return f"错误: 不支持的文件类型 {p.suffix}，允许: {', '.join(sorted(config.allowed_suffixes))}"

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if len(content) > config.max_file_read_size:
            content = content[:config.max_file_read_size] + f"\n... (文件过大，已截断，共 {len(content)} 字符，仅显示前 {config.max_file_read_size} 字符)"

        return f"文件: {p}\n\n{content}"
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        return f"读取文件失败: {str(e)}"


def tool_list_files(directory: str = None, file_type: str = "all") -> str:
    """列出目录文件，按类型分组显示"""
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
        p = _resolve_path(directory) if directory else Path(config.workspace_dir).resolve()
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
                files_by_type[ftype].append((item.name, item.stat().st_size))

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

        lines = [f"目录: {p}", ""]
        if dirs:
            lines.append(f"[文件夹] ({len(dirs)} 个)")
            for d in dirs:
                lines.append(f"  {d}/")
            lines.append("")

        type_labels = {"image": "图片", "document": "文档", "video": "视频",
                       "audio": "音频", "code": "代码", "archive": "压缩包", "other": "其他"}
        total_files = sum(len(v) for v in files_by_type.values())
        lines.append(f"[文件] (共 {total_files} 个)")
        lines.append("")

        for ftype, label in type_labels.items():
            files = files_by_type[ftype]
            if not files:
                continue
            lines.append(f"  {label} ({len(files)} 个):")
            max_show = len(files) if ftype == "image" else 10
            for name, size in files[:max_show]:
                lines.append(f"    {name} ({size} 字节)")
            if len(files) > max_show:
                lines.append(f"    ... 还有 {len(files) - max_show} 个文件，可用 file_type='{ftype}' 查看全部")
            lines.append("")

        return "\n".join(lines).rstrip()
    except Exception as e:
        logger.error(f"列出文件失败: {e}")
        return f"列出文件失败: {str(e)}"


def tool_calculator(expression: str) -> str:
    """安全计算器"""
    try:
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


# ================== 图片展示 ==================

def _get_image_window_size() -> tuple:
    """根据屏幕分辨率和配置计算图片窗口大小"""
    try:
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        width_ratio = config.image_window.get("width_ratio", 0.55)
        height_ratio = config.image_window.get("height_ratio", 0.65)
        max_width = config.image_window.get("max_width", 1100)
        max_height = config.image_window.get("max_height", 800)
        width = min(int(screen_w * width_ratio), max_width)
        height = min(int(screen_h * height_ratio), max_height)
        return (width, height)
    except Exception:
        return (900, 700)


def _resize_window_by_pid(pid: int, width: int, height: int) -> bool:
    """通过 Windows API 根据进程 PID 查找窗口并调整大小居中"""
    try:
        user32 = ctypes.windll.user32
        EnumWindows = user32.EnumWindows
        GetWindowThreadProcessId = user32.GetWindowThreadProcessId
        SetWindowPos = user32.SetWindowPos
        GetSystemMetrics = user32.GetSystemMetrics

        found_hwnd = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_callback(hwnd, lparam):
            window_pid = wintypes.DWORD()
            GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if window_pid.value == pid:
                if user32.IsWindowVisible(hwnd):
                    found_hwnd.append(hwnd)
                    return False
            return True

        EnumWindows(enum_callback, 0)
        if not found_hwnd:
            return False

        hwnd = found_hwnd[0]
        screen_w = GetSystemMetrics(0)
        screen_h = GetSystemMetrics(1)
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        # SWP_NOZORDER | SWP_NOACTIVATE
        SetWindowPos(hwnd, 0, x, y, width, height, 0x0004 | 0x0010)
        return True
    except Exception:
        return False


def _open_image_file(filepath: str) -> tuple:
    """按优先级尝试多种方式打开图片，返回 (是否成功, 信息)"""
    errors = []
    CREATE_FLAGS = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    if not os.path.exists(filepath):
        return (False, f"文件不存在: {filepath}")
    if not os.path.isfile(filepath):
        return (False, f"不是文件: {filepath}")

    # 首选：旧版 Windows 照片查看器（无需文件关联，支持放大缩小）
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

    # 备用打开方式
    fallback_methods = [
        ("画图", ['mspaint.exe', filepath], 0.5),
        ("默认程序", None, 0.5),
        ("资源管理器", ['explorer.exe', filepath], 0.8),
        ("浏览器", None, 0.5),
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
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_images")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        if source.startswith(("http://", "https://")):
            # 下载网络图片
            ext = os.path.splitext(source.split("?")[0])[1].lower()
            if ext not in IMAGE_EXTS:
                ext = ".jpg"
            filename = f"img_{int(time.time())}{ext}"
            filepath = os.path.join(temp_dir, filename)
            resp = requests.get(source, timeout=30)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            source_desc = f"网络图片 ({source[:50]}...)"
        else:
            filepath = source
            source_desc = f"本地文件 ({source})"

        success, msg = _open_image_file(filepath)
        if success:
            return f"图片已展示: {source_desc}\n打开方式: {msg}"
        else:
            return f"展示图片失败: {msg}"
    except Exception as e:
        logger.error(f"展示图片失败: {e}")
        return f"展示图片失败: {str(e)}"


# ================== 工具分发 ==================

TOOL_FUNCTIONS = {
    "web_search": tool_web_search,
    "read_file": tool_read_file,
    "list_files": tool_list_files,
    "calculator": tool_calculator,
    "show_image": tool_show_image,
}


def execute_tool(tool_name: str, tool_args: dict) -> str:
    """执行指定工具，返回结果字符串"""
    func = TOOL_FUNCTIONS.get(tool_name)
    if not func:
        return f"错误: 未知工具 '{tool_name}'"
    try:
        return func(**tool_args)
    except Exception as e:
        logger.error(f"工具 {tool_name} 执行失败: {e}")
        return f"工具执行失败: {str(e)}"
