"""
Synloquer 工具调用系统

7个内置工具：
1. web_search       - 博查联网搜索
2. read_file        - 读取本地文件
3. list_files       - 列出目录文件（按类型分组）
4. calculator       - 安全计算器
5. show_image       - 新窗口展示图片
6. word_frequency   - 词汇统计（中文分词+词频分析）
7. generate_wordcloud - 词云图生成（自动展示）
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
    {
        "type": "function",
        "function": {
            "name": "word_frequency",
            "description": "词汇统计分析，对文本进行中文分词（jieba）和词频统计，返回高频词汇列表。支持直接传入文本或从文件读取。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要分析的文本内容（与 filepath 二选一）"},
                    "filepath": {"type": "string", "description": "要分析的文件路径（与 text 二选一）"},
                    "top_n": {"type": "integer", "description": "返回前N个高频词，默认20", "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_wordcloud",
            "description": "生成词云图，对文本分词统计词频后生成可视化词云图片，自动在新窗口展示。支持直接传入文本或从文件读取。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要生成词云的文本内容（与 filepath 二选一）"},
                    "filepath": {"type": "string", "description": "要分析的文件路径（与 text 二选一）"},
                    "width": {"type": "integer", "description": "图片宽度，默认800", "default": 800},
                    "height": {"type": "integer", "description": "图片高度，默认600", "default": 600},
                    "background_color": {"type": "string", "description": "背景颜色，默认white", "default": "white"},
                    "max_words": {"type": "integer", "description": "词云最大词数，默认100", "default": 100},
                },
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


# ================== 词汇统计与词云图 ==================

# 中文停用词（常见无意义词）
_STOPWORDS_ZH = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "他", "她", "它", "们", "这个", "那个", "什么", "怎么",
    "可以", "因为", "所以", "但是", "如果", "虽然", "而且", "或者", "还是", "已经",
    "不是", "不会", "不要", "能", "吧", "呢", "啊", "吗", "啦", "呀", "哦", "嗯",
    "把", "被", "让", "给", "从", "向", "对", "与", "及", "等", "之", "其", "此",
    "中", "里", "内", "外", "前", "后", "上", "下", "左", "右", "之间", "以后", "以前",
    "现在", "今天", "昨天", "明天", "时候", "时间", "地方", "东西", "事情", "问题",
    "知道", "觉得", "认为", "感觉", "想", "认为", "应该", "可能", "大概", "也许",
    "通过", "进行", "开始", "结束", "需要", "使用", "利用", "采用", "选择", "决定",
}

# 英文停用词
_STOPWORDS_EN = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their", "this", "that", "these", "those",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "and", "but", "or", "if", "because", "as", "until", "while", "of", "at", "by",
    "for", "with", "about", "against", "between", "into", "through", "during",
    "before", "after", "above", "below", "to", "from", "up", "down", "in", "out",
    "on", "off", "over", "under", "again", "further", "then", "once", "here", "there",
    "just", "also", "now", "well", "back", "even", "still", "way", "take", "come",
    "make", "like", "time", "know", "think", "see", "get", "go", "one", "new",
}


def _get_text_from_input(text: str = None, filepath: str = None) -> str:
    """从文本参数或文件路径获取待分析文本"""
    if text:
        return text
    if filepath:
        p = _resolve_path(filepath)
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {p}")
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    raise ValueError("必须提供 text 或 filepath 参数")


def _tokenize(text: str) -> list:
    """中英文混合分词，返回词语列表"""
    import re
    words = []

    # 提取中文段落，用 jieba 分词
    chinese_segments = re.findall(r'[\u4e00-\u9fff]+', text)
    if chinese_segments:
        import jieba
        for seg in chinese_segments:
            for w in jieba.cut(seg):
                w = w.strip()
                if len(w) >= 2 and w not in _STOPWORDS_ZH:
                    words.append(w)

    # 提取英文单词
    english_words = re.findall(r'[a-zA-Z]+', text.lower())
    for w in english_words:
        if len(w) >= 2 and w not in _STOPWORDS_EN:
            words.append(w)

    # 提取数字
    numbers = re.findall(r'\d+', text)
    words.extend(numbers)

    return words


def _count_frequency(words: list, top_n: int = 20) -> list:
    """统计词频，返回 top_n 个 (词, 频次) 元组列表"""
    from collections import Counter
    counter = Counter(words)
    return counter.most_common(top_n)


def tool_word_frequency(text: str = None, filepath: str = None, top_n: int = 20) -> str:
    """词汇统计分析"""
    try:
        content = _get_text_from_input(text, filepath)
        words = _tokenize(content)

        if not words:
            return "未提取到有效词汇（文本可能过短或全为停用词）。"

        freq_list = _count_frequency(words, top_n)
        total_words = len(words)
        unique_words = len(set(words))

        lines = [
            f"词汇统计结果",
            f"总词数: {total_words}",
            f"不重复词数: {unique_words}",
            f"",
            f"Top {min(top_n, len(freq_list))} 高频词:",
            f"",
        ]

        # 计算最大频次用于进度条
        max_freq = freq_list[0][1] if freq_list else 1

        for idx, (word, freq) in enumerate(freq_list, 1):
            percentage = (freq / total_words * 100) if total_words > 0 else 0
            bar_len = int(freq / max_freq * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"{idx:2d}. {word:<10s} {freq:>4d}次 ({percentage:5.1f}%) {bar}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"词汇统计失败: {e}")
        return f"词汇统计失败: {str(e)}"


def _find_chinese_font() -> str:
    """自动检测系统中可用的中文字体路径"""
    font_candidates = [
        r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
        r"C:\Windows\Fonts\msyhbd.ttc",    # 微软雅黑粗体
        r"C:\Windows\Fonts\simhei.ttf",    # 黑体
        r"C:\Windows\Fonts\simsun.ttc",    # 宋体
        r"C:\Windows\Fonts\simkai.ttf",    # 楷体
        r"C:\Windows\Fonts\Deng.ttf",      # 等线
        r"C:\Windows\Fonts\Dengb.ttf",     # 等线粗体
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            return font_path
    return ""


def tool_generate_wordcloud(text: str = None, filepath: str = None,
                            width: int = 800, height: int = 600,
                            background_color: str = "white",
                            max_words: int = 100) -> str:
    """生成词云图并自动展示"""
    try:
        content = _get_text_from_input(text, filepath)
        words = _tokenize(content)

        if not words:
            return "未提取到有效词汇，无法生成词云图。"

        # 统计词频
        from collections import Counter
        freq_dict = dict(Counter(words).most_common(max_words))

        # 检测中文字体
        font_path = _find_chinese_font()
        if not font_path:
            return "未找到中文字体，无法生成中文词云图。请确保系统安装了中文字体。"

        # 生成词云
        from wordcloud import WordCloud
        wc = WordCloud(
            font_path=font_path,
            width=width,
            height=height,
            background_color=background_color,
            max_words=max_words,
            collocations=False,  # 不统计搭配，避免重复
            prefer_horizontal=0.7,
        )
        wc.generate_from_frequencies(freq_dict)

        # 保存图片
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_images")
        os.makedirs(temp_dir, exist_ok=True)
        timestamp = int(time.time())
        image_path = os.path.join(temp_dir, f"wordcloud_{timestamp}.png")
        wc.to_file(image_path)

        # 自动展示图片
        success, msg = _open_image_file(image_path)
        show_info = f"打开方式: {msg}" if success else f"展示失败: {msg}"

        return (
            f"词云图已生成\n"
            f"保存路径: {image_path}\n"
            f"图片尺寸: {width}×{height}\n"
            f"词汇数量: {len(freq_dict)}\n"
            f"{show_info}"
        )
    except Exception as e:
        logger.error(f"词云图生成失败: {e}")
        return f"词云图生成失败: {str(e)}"


# ================== 工具分发 ==================

TOOL_FUNCTIONS = {
    "web_search": tool_web_search,
    "read_file": tool_read_file,
    "list_files": tool_list_files,
    "calculator": tool_calculator,
    "show_image": tool_show_image,
    "word_frequency": tool_word_frequency,
    "generate_wordcloud": tool_generate_wordcloud,
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
