# Provider 适配层详解

## 设计目标

不同 LLM 服务商的 API 格式存在差异，适配层的目标是**用统一的接口屏蔽差异**，让上层业务逻辑（对话、总结、记忆）不需要关心底层是哪家服务商。

## 三种 API 模式

### 1. OpenAI 兼容模式

**适用服务商**：DeepSeek、OpenAI、智谱（Zhipu）、通义千问（Qwen）、Moonshot、MiniMax

**特征**：
- 端点：`{base_url}/chat/completions`
- 认证：`Authorization: Bearer {api_key}`
- 请求体：标准 OpenAI 格式
- 流式响应：SSE，`data: {"choices": [{"delta": {"content": "..."}}]}`

**请求体示例**：
```json
{
  "model": "deepseek-v4-pro",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "你好"}
  ],
  "tools": [...],
  "tool_choice": "auto",
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 4096
}
```

**流式响应示例**：
```
data: {"choices":[{"delta":{"content":"你"}}]}

data: {"choices":[{"delta":{"content":"好"}}]}

data: [DONE]
```

---

### 2. Anthropic 模式

**适用服务商**：Anthropic（Claude）

**特征**：
- 端点：`{base_url}/v1/messages`
- 认证：`x-api-key: {api_key}` + `anthropic-version: 2023-06-01`
- 请求体：`system` 是独立参数，不是 message role
- `max_tokens` 必填
- 流式响应：`event: content_block_delta` + `data: {"delta": {"text": "..."}}`
- 暂不支持 OpenAI 格式的工具调用

**请求体示例**：
```json
{
  "model": "claude-3-5-sonnet-20241022",
  "system": "系统提示词",
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "max_tokens": 4096,
  "stream": true,
  "temperature": 0.7
}
```

**流式响应示例**：
```
event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"你"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"好"}}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}
```

---

### 3. 百度文心模式

**适用服务商**：百度文心（Ernie）

**特征**：
- 需要先用 API Key + Secret Key 换取 `access_token`
- 端点：`{base_url}/chat/completions?access_token={token}`
- access_token 有效期 30 天，带缓存自动刷新
- 请求体和响应格式兼容 OpenAI

**access_token 获取流程**：
```
POST https://aip.baidubce.com/oauth/2.0/token
  ?grant_type=client_credentials
  &client_id={API_KEY}
  &client_secret={SECRET_KEY}

响应：
{
  "access_token": "24.xxxxxx",
  "expires_in": 2592000
}
```

## 适配函数详解

### `_get_provider_headers() -> dict`

根据当前 provider 返回请求头。

```python
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
```

### `_get_provider_endpoint() -> str`

根据当前 provider 返回 API 端点。百度文心会自动附加 access_token。

```python
if PROVIDER == "anthropic":
    return f"{BASE_URL}/v1/messages"
elif PROVIDER == "baidu":
    token = _get_baidu_access_token()
    return f"{BASE_URL}/chat/completions?access_token={token}"
else:
    return f"{BASE_URL}/chat/completions"
```

### `_build_chat_request(...) -> dict`

根据 provider 构建请求体。关键差异：
- Anthropic：提取 system 消息为独立参数，过滤掉 tool_calls 字段，不发送 tools
- OpenAI 兼容：标准格式，支持 tools 和 thinking 参数

```python
if PROVIDER == "anthropic":
    system_content = ""
    chat_messages = []
    for m in messages:
        if m.get("role") == "system":
            system_content = m.get("content", "")
        elif m.get("role") in ("user", "assistant"):
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
    return body
```

### `_parse_stream_line(line) -> tuple | None`

解析流式响应的一行，返回 `(content_chunk, tool_calls_delta)` 或 `None`。

- OpenAI 兼容：解析 `data: ` 前缀，`[DONE]` 返回 `("__done__", None)`
- Anthropic：解析 `event: ` 和 `data: `，只处理 `content_block_delta` 类型

### `_parse_non_stream_response(resp) -> str`

解析非流式响应，返回文本内容。

- OpenAI 兼容：`resp.json()["choices"][0]["message"]["content"]`
- Anthropic：遍历 `content` 数组，拼接所有 `type == "text"` 的块

### `provider_supports_tools() -> bool`

判断当前 provider 是否支持工具调用。

```python
_OPENAI_COMPATIBLE_PROVIDERS = {"deepseek", "openai", "zhipu", "qwen", "moonshot", "minimax"}
return PROVIDER in _OPENAI_COMPATIBLE_PROVIDERS or PROVIDER == "baidu"
```

## 调用点迁移

所有 LLM 调用都已迁移到适配层：

| 调用点 | 函数 | 流式 | 工具 |
|--------|------|------|------|
| 主对话 | `chat_stream()` | 是 | 是（如支持） |
| 对话总结 | `summarize_conversation()` | 否 | 否 |
| 记忆更新 | `update_memory()` | 否 | 否 |

## DeepSeek 特殊处理

### flash 模型思考模式

DeepSeek V4 Flash 默认进入思考模式，导致 `content` 字段为空、`finish_reason: length`。

**解决方案**：在 flash 模型的请求中添加：
```json
"thinking": {"type": "disabled"}
```

适配层通过 `thinking_disabled=True` 参数控制，总结和记忆调用都设置为 `True`。

### 工具调用

DeepSeek V4 Pro 原生支持 OpenAI Function Calling 格式，无需转换。

## 扩展新 Provider

添加新服务商需要：

1. 在 `config.example.json` 的 `available_providers` 中添加配置
2. 判断属于哪种 API 模式：
   - OpenAI 兼容：无需修改代码，配置即可用
   - Anthropic 格式：无需修改代码（已适配）
   - 百度文心格式：无需修改代码（已适配）
   - 全新格式：需要在适配函数中添加分支
3. 在 `.env.example` 中添加对应的密钥变量

详见 [扩展指南](extension-guide.md)。
