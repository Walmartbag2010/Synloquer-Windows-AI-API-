"""
DeepSeek AI Agent - 博查搜索增强版
基于 LangChain + DeepSeek V4 Pro + 博查 Web Search API 的智能研究助手

功能特性：
- 深度思考模式（reasoning_effort: high）
- 中英文双语搜索与信息整合
- 安全的文件操作（沙箱限制在 workspace 内）
- 数学表达式安全计算
- 聊天记录自动保存
- Markdown 终端渲染

使用前请配置环境变量（或在同目录下创建 .env 文件）：
    DEEPSEEK_API_KEY=your_deepseek_key
    BOCHA_API_KEY=your_bocha_key
"""

import os
import re
import ast
import math
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rich.console import Console
from rich.markdown import Markdown
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool

# ================== 日志配置 ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MyAgent")

# ================== 配置管理 ==================


def load_env_file(env_path: Path) -> None:
    """简易 .env 文件加载器（无需 python-dotenv 依赖）"""
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        logger.info("已加载 .env 配置文件")
    except Exception as e:
        logger.warning("加载 .env 文件失败: %s", e)


# 加载同目录下的 .env 文件
load_env_file(Path(__file__).parent / ".env")


class Config:
    """集中管理所有配置项"""

    # ---- API 密钥（从环境变量读取）----
    DEEPSEEK_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    BOCHA_API_KEY: str = os.getenv("BOCHA_API_KEY", "")

    # ---- DeepSeek 模型配置 ----
    MODEL_NAME: str = "deepseek-v4-pro"
    BASE_URL: str = "https://api.deepseek.com"
    TEMPERATURE: float = 0.0
    REQUEST_TIMEOUT: int = 180  # 思考模式可能耗时较长
    REASONING_EFFORT: str = "high"

    # ---- 博查搜索配置 ----
    BOCHA_BASE_URL: str = "https://api.bocha.cn/v1/web-search"
    SEARCH_RESULT_COUNT: int = 10
    SEARCH_TIMEOUT: int = 30

    # ---- 文件操作配置 ----
    WORKSPACE: Path = Path("D:/My_Agent/workspace")
    CHAT_HISTORY_FILE: Path = Path("D:/My_Agent/chat_history.md")
    ALLOWED_SUFFIXES: set = {".txt", ".md", ".log", ".py", ".json", ".csv"}
    MAX_FILE_READ_SIZE: int = 10000  # 字符数
    ALLOW_WRITE: bool = True

    # ---- 重试配置 ----
    HTTP_MAX_RETRIES: int = 3
    HTTP_BACKOFF_FACTOR: float = 0.5

    @classmethod
    def validate(cls) -> List[str]:
        """校验必要配置，返回缺失项列表"""
        missing = []
        if not cls.DEEPSEEK_KEY:
            missing.append("DEEPSEEK_API_KEY")
        if not cls.BOCHA_API_KEY:
            missing.append("BOCHA_API_KEY")
        return missing

    @classmethod
    def ensure_directories(cls) -> None:
        """确保必要目录存在"""
        cls.WORKSPACE.mkdir(parents=True, exist_ok=True)


# ================== HTTP 会话（带重试） ==================


def create_retry_session(
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple = (429, 500, 502, 503, 504),
) -> requests.Session:
    """创建带自动重试的 requests Session"""
    session = requests.Session()
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ================== 工具 1：安全计算器 ==================

# 允许的数学函数白名单
_SAFE_MATH_FUNCS = {
    name: getattr(math, name)
    for name in dir(math)
    if not name.startswith("_") and callable(getattr(math, name))
}
_SAFE_BUILTINS = {"abs": abs, "round": round, "min": min, "max": max, "pow": pow}


def _safe_eval_node(node: ast.AST) -> Any:
    """递归安全求值 AST 节点"""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in _SAFE_MATH_FUNCS:
            return _SAFE_MATH_FUNCS[node.id]
        if node.id in _SAFE_BUILTINS:
            return _SAFE_BUILTINS[node.id]
        raise ValueError(f"不允许的标识符: {node.id}")
    if isinstance(node, ast.BinOp):
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        op = node.op
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Mod):
            return left % right
        if isinstance(op, ast.Pow):
            return left ** right
        raise ValueError(f"不支持的运算符: {type(op).__name__}")
    if isinstance(node, ast.UnaryOp):
        operand = _safe_eval_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
    if isinstance(node, ast.Call):
        func = _safe_eval_node(node.func)
        args = [_safe_eval_node(arg) for arg in node.args]
        kwargs = {kw.arg: _safe_eval_node(kw.value) for kw in node.keywords}
        return func(*args, **kwargs)
    raise ValueError(f"不支持的表达式类型: {type(node).__name__}")


@tool
def calculator(expression: str) -> str:
    """
    安全计算数学表达式。
    支持：加减乘除、幂运算、取模、math 模块函数（sqrt, sin, cos, log 等）。
    示例：2+2、sqrt(16)、sin(pi/2)、log(100, 10)
    """
    try:
        # 先尝试用受限 eval（兼容旧用法）
        result = eval(
            expression,
            {"__builtins__": {}},
            {**_SAFE_MATH_FUNCS, **_SAFE_BUILTINS, "pi": math.pi, "e": math.e},
        )
        return str(result)
    except Exception:
        # 降级到 AST 安全求值
        try:
            tree = ast.parse(expression, mode="eval")
            result = _safe_eval_node(tree)
            return str(result)
        except Exception as e:
            return f"计算出错: {e}"


# ================== 工具 2：博查 Web Search API ==================


class BochaSearchClient:
    """博查 Web Search API 客户端（v1/web-search）"""

    def __init__(self, api_key: str, k: int = 10, timeout: int = 30):
        self.api_key = api_key
        self.base_url = Config.BOCHA_BASE_URL
        self.k = k
        self.timeout = timeout
        self.session = create_retry_session(
            max_retries=Config.HTTP_MAX_RETRIES,
            backoff_factor=Config.HTTP_BACKOFF_FACTOR,
        )

    def search(
        self,
        query: str,
        freshness: str = "noLimit",
        summary: bool = True,
    ) -> str:
        """
        执行搜索，返回格式化的结果字符串

        参数:
            query: 搜索关键词
            freshness: 时间范围
                ("noLimit", "oneDay", "oneWeek", "oneMonth", "oneYear")
            summary: 是否返回文本摘要
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "freshness": freshness,
            "summary": summary,
            "count": self.k,
        }

        try:
            response = self.session.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            # 按官方文档解析：结果在 data.webPages.value 里
            web_pages = data.get("data", {}).get("webPages", {})
            results = web_pages.get("value", [])

            if not results:
                return "未找到相关结果。"

            output_lines = []
            for idx, item in enumerate(results, 1):
                name = item.get("name", "无标题")
                url = item.get("url", "")
                snippet = item.get("snippet", "")
                # 如果开启了 summary，优先使用 summary；否则用 snippet
                desc = item.get("summary", snippet) if summary else snippet
                date_pub = item.get("datePublished", "")
                site_name = item.get("siteName", "")

                output_lines.append(f"{idx}. [{name}]({url})")
                if site_name:
                    output_lines.append(f"   来源: {site_name}")
                if date_pub:
                    output_lines.append(f"   时间: {date_pub}")
                output_lines.append(f"   {desc}")
                output_lines.append("")  # 空行分隔

            return "\n".join(output_lines)

        except requests.RequestException as e:
            logger.error("搜索请求失败: %s", e)
            return f"搜索请求失败: {e}"
        except Exception as e:
            logger.error("搜索处理出错: %s", e)
            return f"搜索处理出错: {e}"


# 实例化搜索客户端
bocha_client = BochaSearchClient(
    api_key=Config.BOCHA_API_KEY,
    k=Config.SEARCH_RESULT_COUNT,
    timeout=Config.SEARCH_TIMEOUT,
)


@tool
def search(query: str) -> str:
    """使用博查搜索引擎搜索网页信息。返回带标题、链接、摘要和时间的结果列表。"""
    return bocha_client.search(query)


# ================== 文件操作安全工具 ==================


def safe_path(path_str: str) -> Path:
    """
    解析路径，确保在 workspace 内，防止目录穿越攻击

    参数:
        path_str: 文件路径（相对或绝对）
    返回:
        解析后的安全 Path 对象
    异常:
        ValueError: 路径超出 workspace 范围
    """
    p = Path(path_str)
    if not p.is_absolute():
        p = Config.WORKSPACE / p
    p = p.resolve()
    workspace_resolved = Config.WORKSPACE.resolve()
    if not str(p).startswith(str(workspace_resolved)):
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
            icon = "📁" if item.is_dir() else "📄"
            size_info = ""
            if item.is_file():
                size_bytes = item.stat().st_size
                if size_bytes < 1024:
                    size_info = f" ({size_bytes}B)"
                elif size_bytes < 1024 * 1024:
                    size_info = f" ({size_bytes // 1024}KB)"
                else:
                    size_info = f" ({size_bytes // (1024 * 1024)}MB)"
            items.append(f"{icon} {item.name}{size_info}")

        return "\n".join(items) if items else "(空目录)"
    except Exception as e:
        logger.error("列出文件出错: %s", e)
        return f"列出文件出错: {e}"


# ================== 工具 4：读取文件 ==================


@tool
def read_file(filepath: str) -> str:
    """读取指定文件的全部内容（仅限文本文件，超过 10000 字符自动截断）。"""
    try:
        target = safe_path(filepath)
        if not target.is_file():
            return f"错误: {filepath} 不是一个文件"

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if len(content) > Config.MAX_FILE_READ_SIZE:
            truncated = content[: Config.MAX_FILE_READ_SIZE]
            return f"{truncated}\n... (文件内容过长，已截断，共 {len(content)} 字符)"
        return content

    except UnicodeDecodeError:
        return "错误: 无法以文本方式读取该文件（可能是二进制文件）"
    except Exception as e:
        logger.error("读取文件出错: %s", e)
        return f"读取文件出错: {e}"


# ================== 工具 5：写入文件 ==================


@tool
def write_file(filepath: str, content: str, mode: str = "w") -> str:
    """
    写入文件内容。

    参数:
        filepath: 文件路径（仅限 workspace 内）
        content: 要写入的内容
        mode: 'w'（覆盖）或 'a'（追加），默认覆盖
    注意:
        仅允许操作 .txt, .md, .log, .py, .json, .csv 文件
    """
    if not Config.ALLOW_WRITE:
        return "❌ 文件写入功能已被管理员禁用。如需启用请修改 Config.ALLOW_WRITE = True"

    try:
        target = safe_path(filepath)

        if target.suffix.lower() not in Config.ALLOWED_SUFFIXES:
            allowed = ", ".join(sorted(Config.ALLOWED_SUFFIXES))
            return f"错误: 禁止编辑此类型文件（允许: {allowed}）"

        if mode not in ("w", "a"):
            return "错误: mode 只能是 'w' 或 'a'"

        # 确保父目录存在
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, mode, encoding="utf-8") as f:
            f.write(content)

        action = "追加" if mode == "a" else "写入"
        return f"✅ 成功{action}文件: {target.name}"

    except Exception as e:
        logger.error("写入文件出错: %s", e)
        return f"写入文件出错: {e}"


# ================== Agent 构建 ==================


def build_agent() -> Any:
    """构建并返回 LangChain Agent 实例"""
    llm = ChatOpenAI(
        model=Config.MODEL_NAME,
        base_url=Config.BASE_URL,
        api_key=Config.DEEPSEEK_KEY,
        temperature=Config.TEMPERATURE,
        request_timeout=Config.REQUEST_TIMEOUT,
        extra_body={
            "thinking": {"type": "enabled"},
            "reasoning_effort": Config.REASONING_EFFORT,
        },
    )

    tools = [calculator, search, list_files, read_file, write_file]

    system_prompt = (
        "你是一个专业的研究助手，可以使用博查搜索引擎获取2026最新中英文信息。"
        "当用户提出复杂研究课题时，你必须遵循以下流程：\n"
        "1. 规划：提炼 3~5 组中英文关键词/查询语句，覆盖课题不同角度。\n"
        "2. 搜索：分批使用搜索工具，用这些关键词进行搜索"
        "（务必同时使用英文关键词获取国际视角）。"
        "每次搜索后仔细分析返回内容，并核对信息的发布日期，优先采用近三个月内的信息。\n"
        "3. 分析：综合所有搜索结果，进行对比、归纳、提炼，形成结构化的分析报告。\n"
        "4. 引用：报告中必须为每个重要观点或数据附上来源链接"
        "（使用 [来源](URL) 格式），并在文末列出完整参考资料。\n"
        "5. 语言：始终用中文回复。"
        "其他工具按需使用。"
    )

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )


# ================== 终端渲染（Rich） ==================

console = Console()


def simple_markdown_to_rich(text: str) -> str:
    """将 Markdown 转为 Rich markup，确保样式能正确显示"""
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"[bold italic]\1[/bold italic]", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"[italic]\1[/italic]", text)
    text = re.sub(r"`([^`]+?)`", r"[yellow]\1[/yellow]", text)
    text = re.sub(r"~~(.+?)~~", r"[strike]\1[/strike]", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[link=\2]\1[/link]", text)
    return text


def render_markdown(text: str) -> None:
    """尝试 Rich Markdown 渲染，降级到简单转换"""
    try:
        console.print(Markdown(text))
    except Exception:
        console.print(simple_markdown_to_rich(text))


# ================== 聊天记录保存 ==================


def save_chat_history(user_input: str, agent_response: str) -> None:
    """
    保存聊天记录到文件

    参数:
        user_input: 用户输入
        agent_response: Agent 回复
    """
    try:
        history_file = Config.CHAT_HISTORY_FILE
        history_file.parent.mkdir(parents=True, exist_ok=True)

        with open(history_file, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"## {timestamp}\n\n")
            f.write(f"**你：** {user_input}\n\n")
            f.write(f"**Agent：** {agent_response}\n\n")
            f.write("---\n\n")
    except Exception as e:
        logger.warning("聊天记录保存失败: %s", e)
        print(f"⚠️ 聊天记录保存失败: {e}")


# ================== 命令处理 ==================


def handle_special_command(user_input: str) -> Optional[str]:
    """
    处理特殊命令，返回 None 表示不是特殊命令

    支持命令:
        /help  - 显示帮助
        /clear - 清空屏幕
        /exit  - 退出（同 exit）
        /history - 显示聊天记录文件路径
        /tools - 列出可用工具
    """
    cmd = user_input.strip().lower()

    if cmd in ("/help", "/h", "help"):
        return (
            "📖 **可用命令**\n\n"
            "- `/help` 或 `/h` - 显示此帮助信息\n"
            "- `/clear` 或 `/cls` - 清空终端屏幕\n"
            "- `/tools` - 列出所有可用工具\n"
            "- `/history` - 显示聊天记录保存路径\n"
            "- `/exit` 或 `exit` - 退出程序\n\n"
            "直接输入问题即可与 AI 对话。"
        )

    if cmd in ("/clear", "/cls", "clear"):
        os.system("cls" if os.name == "nt" else "clear")
        return "屏幕已清空。"

    if cmd == "/tools":
        return (
            "🔧 **可用工具**\n\n"
            "1. **calculator** - 安全数学计算（支持 +-*/、幂、math 函数）\n"
            "2. **search** - 博查网页搜索（中英文双语）\n"
            "3. **list_files** - 列出工作区文件\n"
            "4. **read_file** - 读取文本文件\n"
            "5. **write_file** - 写入/追加文件（受限类型）"
        )

    if cmd == "/history":
        return f"📝 聊天记录保存在: `{Config.CHAT_HISTORY_FILE}`"

    return None


# ================== 主程序 ==================


def main() -> None:
    """主程序入口"""
    # 配置校验
    missing = Config.validate()
    if missing:
        logger.error("缺少必要的环境变量: %s", ", ".join(missing))
        print("❌ 启动失败：缺少必要的 API 密钥配置")
        print(f"   请设置环境变量: {', '.join(missing)}")
        print("   或在脚本同目录创建 .env 文件，内容如下：")
        for key in missing:
            print(f"   {key}=your_key_here")
        return

    # 确保目录存在
    Config.ensure_directories()

    # 构建 Agent
    try:
        agent = build_agent()
    except Exception as e:
        logger.error("Agent 构建失败: %s", e)
        print(f"❌ Agent 初始化失败: {e}")
        return

    # 启动信息
    print("=" * 60)
    print("🤖 DeepSeek AI Agent (博查搜索·思考模式) 已启动！")
    print(f"   模型: {Config.MODEL_NAME} | 推理强度: {Config.REASONING_EFFORT}")
    print(f"   工作区: {Config.WORKSPACE}")
    print("   输入 /help 查看命令，输入 exit 退出")
    print("=" * 60)

    # 主循环
    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 收到退出信号，再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "/exit", "quit", "/quit"):
            print("👋 再见！")
            break

        # 处理特殊命令
        special_result = handle_special_command(user_input)
        if special_result is not None:
            render_markdown(special_result)
            continue

        # 调用 Agent
        try:
            print("⏳ 思考中...")
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]}
            )
            final_message = result["messages"][-1].content

            # 清除"思考中"提示行（简单实现）
            print("\r", end="")

            render_markdown(final_message)

            # 保存聊天记录
            save_chat_history(user_input, final_message)

        except KeyError as e:
            logger.error("返回结果格式异常: %s", e)
            print(f"❌ 返回结果格式异常: {e}")
        except Exception as e:
            logger.error("Agent 调用失败: %s", e, exc_info=True)
            print(f"❌ 处理出错: {e}")
            print("   请检查网络连接和 API 密钥配置，或稍后重试。")


if __name__ == "__main__":
    main()
