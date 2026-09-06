"""
Synloquer - 轻量级终端 LLM 对话助手

主入口文件，负责终端交互和主循环。
核心逻辑拆分到各模块：
- synloquer_config   配置管理
- synloquer_provider 多模型 API 适配
- synloquer_memory   长期记忆（检索/遗忘/压缩）
- synloquer_tools    工具调用系统
- synloquer_storage  对话总结与记录保存
- synloquer_logger   日志系统
- synloquer_retry    重试机制
"""

import json

import synloquer_logger as logger
from synloquer_config import config
import synloquer_provider as provider
import synloquer_memory as memory
import synloquer_tools as tools
import synloquer_storage as storage


# ================== 启动信息 ==================

def print_header():
    print("=" * 56)
    print("  Synloquer - 终端 AI 对话助手")
    print(f"  服务商: {config.provider} | 模型: {config.model_chat}")
    print(f"  总结模型: {config.model_summary}")
    if config.env_loaded:
        print(f"  密钥文件: {config.env_path}")
    else:
        print("  [警告] 未找到 .env 密钥文件，请检查 config.json 中的 env_file_path")
    print(f"  搜索: {config.search_provider} | 工具: 搜索/文件读取/文件列表/计算器/图片")
    print(f"  对话前缀: 用户=\"{config.user_prefix}\" AI=\"{config.ai_prefix}\"")
    if not provider.supports_tools():
        print(f"  [提示] 当前服务商 {config.provider} 暂不支持工具调用")
    memory_count = len(memory._load_from_file().get("memories", []))
    if memory_count:
        print(f"  长期记忆: 已加载 ({memory_count} 条，检索 top-{config.memory_retrieval_top_k})")
    else:
        print("  长期记忆: 暂无")
    print("  输入消息开始对话，输入 exit 或 quit 结束并总结")
    print("=" * 56)
    print()


# ================== 核心聊天（流式 + 工具调用循环） ==================

def chat_stream(user_input: str, messages: list) -> str:
    """
    发送消息，支持工具调用循环，流式输出最终回复。
    messages 是对话历史列表，会被原地修改。
    """
    # 每次对话前检索相关记忆，动态构建系统提示词
    system_prompt = memory.build_system_prompt(user_input)
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] = system_prompt
    else:
        messages.insert(0, {"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": user_input})

    full_reply = ""
    max_tool_rounds = 8
    tool_round = 0

    while tool_round < max_tool_rounds:
        tool_round += 1
        print(config.ai_prefix, end="", flush=True)

        try:
            use_tools = tools.TOOLS if provider.supports_tools() else None
            resp = provider.chat_stream_request(
                model=config.model_chat, messages=messages, tools=use_tools,
            )

            if resp.status_code != 200:
                print(f"\n[错误] API 返回 {resp.status_code}: {resp.text[:200]}")
                messages.pop()
                return ""

            # 收集流式响应
            assistant_content = ""
            tool_calls = []

            for line in resp.iter_lines(decode_unicode=True):
                parsed = provider.parse_stream_line(line)
                if parsed is None:
                    continue
                content, delta_tool_calls = parsed
                if content == "__done__":
                    break

                if content:
                    assistant_content += content
                    print(content, end="", flush=True)

                # 工具调用（仅 OpenAI 兼容格式）
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
                # 保存助手消息（含工具调用）
                assistant_msg = {"role": "assistant", "content": assistant_content or None}
                assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                # 执行每个工具
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
                        print(f"  [正在列出目录: {tool_args.get('directory', 'workspace')}]")
                    elif tool_name == "show_image":
                        print(f"  [正在展示图片: {tool_args.get('source', '')}]")
                    elif tool_name == "calculator":
                        print(f"  [正在计算: {tool_args.get('expression', '')}]")
                    else:
                        print(f"  [正在调用工具: {tool_name}]")

                    tool_result = tools.execute_tool(tool_name, tool_args)
                    print(f"  [工具完成]")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result,
                    })

                # 继续下一轮 LLM 调用（工具结果传回模型）
                continue
            else:
                # 没有工具调用，保存最终回复
                if assistant_content:
                    messages.append({"role": "assistant", "content": assistant_content})
                full_reply = assistant_content
                break

        except Exception as e:
            logger.error(f"对话出错: {e}")
            print(f"\n[错误] {e}")
            if messages and messages[-1]["role"] == "user":
                messages.pop()
            return ""

    if tool_round >= max_tool_rounds:
        print("[提示] 已达到最大工具调用轮数，结束本次回复")
        if assistant_content:
            messages.append({"role": "assistant", "content": assistant_content})
            full_reply = assistant_content

    return full_reply


# ================== 主函数 ==================

def main():
    # 初始化记忆（加载 + 遗忘检查）
    memory.init_memory()

    # 初始化对话历史（系统提示词会在每次对话时动态更新）
    messages = [{"role": "system", "content": config.system_prompt}]

    print_header()

    while True:
        try:
            user_input = input(config.user_prefix).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "退出"):
            break

        print()
        chat_stream(user_input, messages)
        print()

    # 对话结束：总结 + 保存记录 + 更新记忆
    if any(m["role"] == "user" for m in messages):
        conversation_lines = []
        for msg in messages:
            if msg["role"] == "user":
                conversation_lines.append(f"{config.user_prefix}{msg['content']}")
            elif msg["role"] == "assistant" and msg.get("content"):
                conversation_lines.append(f"{config.ai_prefix}{msg['content']}")
        conversation_text = "\n".join(conversation_lines)

        summary = storage.summarize_conversation(messages)
        print()
        print(summary)
        storage.save_summary(summary, messages)
        storage.save_chat_log(messages)
        memory.update_memory(conversation_text)
    else:
        print("\n（未进行对话，跳过总结）")

    print("\n再见！")


if __name__ == "__main__":
    main()
