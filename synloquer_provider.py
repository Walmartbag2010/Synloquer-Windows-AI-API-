"""
Synloquer Provider 适配层

统一适配三种 API 模式：
1. OpenAI 兼容格式（deepseek/openai/zhipu/qwen/moonshot/minimax）
2. Anthropic Messages API
3. 百度文心（需先换 access_token）

所有 API 调用内置指数退避重试。
"""

import json
import time

import requests

import synloquer_logger as logger
from synloquer_config import config
from synloquer_retry import retry_request

_OPENAI_COMPATIBLE = {"deepseek", "openai", "zhipu", "qwen", "moonshot", "minimax"}

_baidu_token = None
_baidu_token_expire = 0


def _get_baidu_access_token() -> str:
    """百度文心需要先用 API Key + Secret Key 换取 access_token（带缓存）"""
    global _baidu_token, _baidu_token_expire
    if _baidu_token and time.time() < _baidu_token_expire:
        return _baidu_token

    api_key = config.api_key if config.env_key_name == "BAIDU_API_KEY" else __import__("os").environ.get("BAIDU_API_KEY", "")
    secret_key = __import__("os").environ.get("BAIDU_SECRET_KEY", "")
    if not api_key or not secret_key:
        raise Exception("百度文心需要 BAIDU_API_KEY 和 BAIDU_SECRET_KEY")

    token_url = (
        f"https://aip.baidubce.com/oauth/2.0/token"
        f"?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    )
    resp = requests.post(token_url, timeout=30)
    data = resp.json()
    _baidu_token = data.get("access_token", "")
    _baidu_token_expire = time.time() + data.get("expires_in", 2592000) - 300
    return _baidu_token


def get_headers() -> dict:
    """根据 provider 返回请求头"""
    if config.provider == "anthropic":
        return {"x-api-key": config.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    elif config.provider == "baidu":
        return {"Content-Type": "application/json"}
    else:
        return {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}


def get_endpoint() -> str:
    """根据 provider 返回 API 端点"""
    if config.provider == "anthropic":
        return f"{config.base_url}/v1/messages"
    elif config.provider == "baidu":
        token = _get_baidu_access_token()
        return f"{config.base_url}/chat/completions?access_token={token}"
    else:
        return f"{config.base_url}/chat/completions"


def build_request(model: str, messages: list, stream: bool = False,
                  tools: list = None, tool_choice: str = None,
                  temperature: float = 0.7, max_tokens: int = 4096,
                  thinking_disabled: bool = False) -> dict:
    """根据 provider 构建请求体"""
    if config.provider == "anthropic":
        system_content = ""
        chat_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
            elif m.get("role") in ("user", "assistant"):
                chat_messages.append({"role": m["role"], "content": m.get("content", "")})
        body = {
            "model": model, "messages": chat_messages,
            "max_tokens": max_tokens, "stream": stream, "temperature": temperature,
        }
        if system_content:
            body["system"] = system_content
        return body
    else:
        body = {
            "model": model, "messages": messages, "stream": stream,
            "temperature": temperature, "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"
        if thinking_disabled:
            body["thinking"] = {"type": "disabled"}
        return body


def parse_stream_line(line: str):
    """
    解析流式响应的一行。
    返回 (content_chunk, tool_calls_delta) 或 None；content 为 "__done__" 表示流结束。
    """
    if not line:
        return None

    if config.provider == "anthropic":
        if line.startswith("event: "):
            return ("", None)
        if line.startswith("data: "):
            data = line[6:]
            try:
                obj = json.loads(data)
                obj_type = obj.get("type", "")
                if obj_type == "content_block_delta":
                    delta = obj.get("delta", {})
                    text = delta.get("text", "")
                    return (text, None)
                elif obj_type == "message_stop":
                    return ("__done__", None)
            except json.JSONDecodeError:
                pass
        return None

    # OpenAI 兼容格式
    if not line.startswith("data: "):
        return None
    data = line[6:]
    if data.strip() == "[DONE]":
        return ("__done__", None)
    try:
        obj = json.loads(data)
        choices = obj.get("choices", [])
        if not choices:
            return None
        delta = choices[0].get("delta", {})
        content = delta.get("content", "")
        tool_calls_delta = delta.get("tool_calls", None)
        return (content, tool_calls_delta)
    except json.JSONDecodeError:
        return None


def parse_non_stream_response(resp) -> str:
    """解析非流式响应，返回文本内容"""
    data = resp.json()
    if config.provider == "anthropic":
        content_parts = data.get("content", [])
        return "\n".join(p.get("text", "") for p in content_parts if p.get("type") == "text")
    else:
        choices = data.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            return msg.get("content", "") or ""
        return ""


def supports_tools() -> bool:
    """当前 provider 是否支持工具调用"""
    return config.provider in _OPENAI_COMPATIBLE or config.provider == "baidu"


def chat_stream_request(model: str, messages: list, tools: list = None,
                        temperature: float = 0.7, max_tokens: int = 4096):
    """
    发送流式聊天请求（带重试），返回 requests.Response（stream=True）。
    调用方需自行迭代 resp.iter_lines()。
    """
    body = build_request(model, messages, stream=True, tools=tools,
                         tool_choice="auto" if tools else None,
                         temperature=temperature, max_tokens=max_tokens)
    return retry_request(
        requests.post,
        get_endpoint(), headers=get_headers(), json=body,
        stream=True, timeout=120, max_attempts=3, base_delay=2.0,
    )


def chat_non_stream_request(model: str, messages: list, temperature: float = 0.3,
                             max_tokens: int = 4096, thinking_disabled: bool = False) -> str:
    """发送非流式聊天请求（带重试），返回文本内容"""
    body = build_request(model, messages, stream=False, temperature=temperature,
                         max_tokens=max_tokens, thinking_disabled=thinking_disabled)
    resp = retry_request(
        requests.post,
        get_endpoint(), headers=get_headers(), json=body,
        timeout=60, max_attempts=3, base_delay=2.0,
    )
    return parse_non_stream_response(resp)
