"""
Synloquer 存储模块

负责对话结束后的总结生成和记录保存：
1. summarize_conversation - 用 flash 模型生成对话总结
2. save_summary - 保存总结到 summaries/ 目录
3. save_chat_log - 保存完整对话记录到 chat_logs/ 目录
"""

import json
import os
from datetime import datetime

import synloquer_logger as logger
from synloquer_config import config
import synloquer_provider as provider


def summarize_conversation(messages: list) -> str:
    """用 flash 模型生成对话总结"""
    conversation_lines = []
    for msg in messages:
        if msg["role"] == "user":
            conversation_lines.append(f"{config.user_prefix}{msg['content']}")
        elif msg["role"] == "assistant" and msg.get("content"):
            conversation_lines.append(f"{config.ai_prefix}{msg['content']}")

    conversation_text = "\n".join(conversation_lines)
    if not conversation_text.strip():
        return "（无对话内容）"

    summary_prompt = (
        "请阅读以下对话，完成两件事：\n"
        "1. 用简洁的语言总结对话的主要内容和话题走向\n"
        "2. 列出值得记住的关键信息点\n\n"
        f"对话内容：\n{conversation_text}"
    )

    logger.info("正在生成对话总结...")

    try:
        return provider.chat_non_stream_request(
            model=config.model_summary,
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.3, max_tokens=2048, thinking_disabled=True,
        )
    except Exception as e:
        logger.error(f"总结失败: {e}")
        return f"总结失败: {e}"


def _get_conversation_meta(messages: list) -> tuple:
    """提取对话元信息：第一条用户消息、消息轮次"""
    first_user_msg = next(
        (m["content"][:30] for m in messages if m["role"] == "user"),
        "未命名对话"
    )
    msg_count = sum(1 for m in messages if m["role"] in ("user", "assistant") and m.get("content"))
    return first_user_msg, msg_count


def save_summary(summary: str, messages: list) -> str:
    """保存对话总结到 summaries/ 目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_summary_{timestamp}.md"
    filepath = os.path.join(config.summary_dir, filename)

    first_user_msg, msg_count = _get_conversation_meta(messages)

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
    logger.info(f"总结已保存到: {filepath}")
    return filepath


def save_chat_log(messages: list) -> str:
    """保存完整的原始对话记录（逐字）到 chat_logs 目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_{timestamp}.md"
    filepath = os.path.join(config.chat_log_dir, filename)

    first_user_msg, msg_count = _get_conversation_meta(messages)

    lines = [
        "# 对话记录", "",
        f"- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **对话主题**: {first_user_msg}",
        f"- **消息轮次**: {msg_count}",
        "", "---", "",
    ]

    for msg in messages:
        role = msg["role"]
        content = msg.get("content")

        if role == "system":
            continue
        elif role == "user":
            lines.extend([f"## 我", "", content, ""])
        elif role == "assistant":
            lines.extend([f"## AI", ""])
            if content:
                lines.extend([content, ""])
            for tc in msg.get("tool_calls", []):
                tool_name = tc["function"]["name"]
                try:
                    tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                except json.JSONDecodeError:
                    tool_args = {}
                args_str = ", ".join(f"{k}={v}" for k, v in tool_args.items())
                lines.extend([f"> 调用工具: `{tool_name}`({args_str})", ""])
        elif role == "tool":
            lines.extend([f"### 工具返回", "", f"```\n{content}\n```", ""])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"完整对话记录已保存到: {filepath}")
    return filepath
