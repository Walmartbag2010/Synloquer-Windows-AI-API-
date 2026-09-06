import os
from pathlib import Path
import re
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_tavily import TavilySearch
from rich.console import Console
from rich.markdown import Markdown

# ================== 全局设置 ==================
ALLOW_WRITE = True   # 文件写入开关，用完可改回 False

# ------------------ API 密钥（从桌面 .env 文件读取，勿硬编码） ------------------
import os as _os
from pathlib import Path as _Path
for _env_path in [_Path.home() / "Desktop" / ".env", _Path(_os.environ.get("USERPROFILE", "")) / "Desktop" / ".env", _Path(r"D:\HuaweiMoveData\Users\HUAWEI\Desktop\.env")]:
    if _env_path.exists():
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _os.environ.setdefault(_k.strip(), _v.strip())
        break

DEEPSEEK_KEY = _os.environ.get("DEEPSEEK_API_KEY", "")
TAVILY_KEY   = _os.environ.get("TAVILY_API_KEY", "")

# ------------------ 大模型（思考模式）------------------
llm = ChatOpenAI(
    model="deepseek-v4-flash",
    base_url="https://api.deepseek.com",
    api_key=DEEPSEEK_KEY,
    temperature=0,
    # 将思考参数通过 extra_body 显式传入（消除警告）
    extra_body={
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high"
    }
)

# ================== 工具 1：计算器 ==================
@tool
def calculator(expression: str) -> str:
    """计算数学表达式，例如 2+2 或 sqrt(16)"""
    try:
        import math
        result = eval(expression, {"__builtins__": None}, {"math": math, "abs": abs, "round": round})
        return str(result)
    except Exception as e:
        return f"计算出错: {e}"

# ================== 工具 2：Tavily 搜索 ==================
search = TavilySearch(
    tavily_api_key=TAVILY_KEY,
    max_results=2,
    include_answer=True,
)

# ================== 文件操作基础设置 ==================
WORKSPACE = Path("D:/My_Agent/workspace")
WORKSPACE.mkdir(parents=True, exist_ok=True)
ALLOWED_SUFFIXES = {".txt", ".md", ".log", ".py", ".json", ".csv"}

def safe_path(path_str: str) -> Path:
    """解析路径，确保在 workspace 内，防止目录穿越"""
    p = Path(path_str)
    if not p.is_absolute():
        p = WORKSPACE / p
    p = p.resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise ValueError(f"Access denied: {path_str} is outside workspace")
    return p

# ================== 工具 3：列出文件 ==================
@tool
def list_files(directory: str = ".") -> str:
    """列出指定目录下的文件和子目录。参数 directory 默认为当前工作区根目录。"""
    try:
        target = safe_path(directory)
        if not target.is_dir():
            return f"错误: {directory} 不是一个目录"
        items = []
        for item in sorted(target.iterdir()):
            t = "📁" if item.is_dir() else "📄"
            items.append(f"{t} {item.name}")
        return "\n".join(items) if items else "(空目录)"
    except Exception as e:
        return f"列出文件出错: {e}"

# ================== 工具 4：读取文件 ==================
@tool
def read_file(filepath: str) -> str:
    """读取指定文件的全部内容（仅限文本文件）。"""
    try:
        target = safe_path(filepath)
        if not target.is_file():
            return f"错误: {filepath} 不是一个文件"
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 10000:
            content = content[:10000] + "\n... (文件内容过长，已截断)"
        return content
    except UnicodeDecodeError:
        return "错误: 无法以文本方式读取该文件（可能是二进制文件）"
    except Exception as e:
        return f"读取文件出错: {e}"

# ================== 工具 5：写入文件 ==================
@tool
def write_file(filepath: str, content: str, mode: str = "w") -> str:
    """写入文件内容。参数 mode 为 'w'（覆盖）或 'a'（追加）。默认覆盖。
    注意：此操作需要用户确认，且仅允许在 workspace 内操作 .txt, .md, .log, .py, .json, .csv 文件。
    """
    if not ALLOW_WRITE:
        return "❌ 文件写入功能已被管理员禁用。如需启用请修改 ALLOW_WRITE = True"
    try:
        target = safe_path(filepath)
        if target.suffix.lower() not in ALLOWED_SUFFIXES:
            return f"错误: 禁止编辑此类型文件（允许: {', '.join(ALLOWED_SUFFIXES)}）"
        if mode not in ("w", "a"):
            return "错误: mode 只能是 'w' 或 'a'"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)
        return f"✅ 成功写入文件: {target.name}"
    except Exception as e:
        return f"写入文件出错: {e}"

# ================== 整合工具与 Agent ==================
tools = [calculator, search, list_files, read_file, write_file]

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=(
        "你是一个全能的中文智能助手。你可以使用计算器、搜索引擎，还能操作本地文件。"
        "文件操作时，所有路径都相对于工作区 D:\\My_Agent\\workspace。"
        "读取文件前可先用 list_files 查看目录。"
        "写入文件请确保内容安全，不要修改系统关键文件。"
        "始终用中文回复。"
    ),
)

# ================== 终端渲染（Rich） ==================
console = Console()

def simple_markdown_to_rich(text: str) -> str:
    """将 Markdown 转为 Rich markup，确保样式能正确显示"""
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'[bold italic]\1[/bold italic]', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'[bold]\1[/bold]', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'[italic]\1[/italic]', text)
    text = re.sub(r'`([^`]+?)`', r'[yellow]\1[/yellow]', text)
    text = re.sub(r'~~(.+?)~~', r'[strike]\1[/strike]', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'[link=\2]\1[/link]', text)
    return text

def render_markdown(text: str):
    """尝试 Rich Markdown 渲染，降级到简单转换"""
    try:
        console.print(Markdown(text))
    except Exception:
        console.print(simple_markdown_to_rich(text))

# ================== 主循环 + 聊天记录保存 ==================
print("🤖 DeepSeek AI Agent (思考模式·文件版) 已启动！输入 'exit' 退出。")
while True:
    user_input = input("\n你：")
    if user_input.lower() == "exit":
        break
    result = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
    final_message = result["messages"][-1].content
    render_markdown(final_message)

    # 保存聊天记录到文件
    try:
        with open("D:/My_Agent/chat_history.md", "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"## {timestamp}\n\n")
            f.write(f"**你：** {user_input}\n\n")
            f.write(f"**Agent：** {final_message}\n\n")
            f.write("---\n\n")
    except Exception as e:
        print(f"⚠️ 聊天记录保存失败: {e}")
