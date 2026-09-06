# 扩展指南

本文档介绍如何为项目添加新的 AI 服务商、新工具、新功能。

## 目录

- [添加新的 AI 服务商](#添加新的-ai-服务商)
- [添加新工具](#添加新工具)
- [添加新的配置项](#添加新的配置项)
- [修改系统提示词](#修改系统提示词)

---

## 添加新的 AI 服务商

### 步骤 1：判断 API 模式

首先判断新服务商属于哪种 API 模式：

| 模式 | 特征 | 是否需要改代码 |
|------|------|---------------|
| OpenAI 兼容 | 端点 `/chat/completions`，`Bearer` 认证，标准 SSE 流 | 否，配置即可 |
| Anthropic 格式 | 端点 `/v1/messages`，`x-api-key` 头 | 否，已适配 |
| 百度文心格式 | 需要换 access_token | 否，已适配 |
| 全新格式 | 以上都不是 | 是，需要添加适配逻辑 |

### 步骤 2：添加配置（OpenAI 兼容/Anthropic/百度格式）

在 `config.example.json` 的 `available_providers` 中添加：

```json
"new_provider": {
  "base_url": "https://api.new-provider.com/v1",
  "env_key": "NEW_PROVIDER_API_KEY",
  "models": ["model-name-1", "model-name-2"]
}
```

在 `.env.example` 中添加密钥变量：

```env
# New Provider
NEW_PROVIDER_API_KEY=sk-xxxxxxxxxxxxxxxx
NEW_PROVIDER_BASE_URL=https://api.new-provider.com/v1
```

然后在 `config.json` 中切换 `provider` 为 `new_provider`，设置对应的模型名称即可。

### 步骤 3：添加全新 API 格式的适配（如需要）

如果新服务商是全新的 API 格式，需要在适配层添加逻辑。

#### 3.1 修改 `_get_provider_headers()`

```python
elif PROVIDER == "new_provider":
    return {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
    }
```

#### 3.2 修改 `_get_provider_endpoint()`

```python
elif PROVIDER == "new_provider":
    return f"{BASE_URL}/completions"
```

#### 3.3 修改 `_build_chat_request()`

```python
elif PROVIDER == "new_provider":
    # 新服务商的请求体格式
    body = {
        "model": model,
        "prompt": messages[-1]["content"],
        "stream": stream,
    }
    return body
```

#### 3.4 修改 `_parse_stream_line()`

```python
elif PROVIDER == "new_provider":
    # 新服务商的流式响应格式
    if line.startswith("data: "):
        data = line[6:]
        try:
            obj = json.loads(data)
            text = obj.get("text", "")
            return (text, None)
        except json.JSONDecodeError:
            pass
    return None
```

#### 3.5 修改 `_parse_non_stream_response()`

```python
elif PROVIDER == "new_provider":
    data = resp.json()
    return data.get("output", "")
```

#### 3.6 更新 `provider_supports_tools()`

如果新服务商支持工具调用，将其加入支持列表：

```python
_OPENAI_COMPATIBLE_PROVIDERS = {
    "deepseek", "openai", "zhipu", "qwen", "moonshot", "minimax",
    "new_provider"  # 添加新服务商
}
```

---

## 添加新工具

### 步骤 1：定义工具函数

在 `terminal_chat.py` 的工具函数区域添加：

```python
def tool_weather(city: str, days: int = 1) -> str:
    """
    查询指定城市的天气
    参数:
        city: 城市名称
        days: 查询天数，默认1天
    返回: 天气信息字符串
    """
    try:
        # 调用天气 API
        resp = requests.get(
            f"https://api.weather.com/{city}",
            params={"days": days},
            timeout=10
        )
        data = resp.json()
        # 格式化结果
        return f"{city}天气: {data['weather']}, 温度: {data['temp']}°C"
    except Exception as e:
        return f"天气查询失败: {str(e)}"
```

**注意事项**：
- 函数参数必须有明确的类型注解
- 必须返回字符串（LLM 只能处理文本）
- 异常必须捕获，不能让程序崩溃
- 函数名建议用 `tool_` 前缀

### 步骤 2：添加工具定义

在 `TOOLS` 列表中添加 JSON Schema 定义：

```python
{
    "type": "function",
    "function": {
        "name": "weather",
        "description": "查询指定城市的天气信息，当用户询问天气时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如北京、上海、长春"
                },
                "days": {
                    "type": "integer",
                    "description": "查询天数，1-7天，默认1天",
                    "default": 1
                }
            },
            "required": ["city"]
        }
    }
},
```

**编写 description 的技巧**：
- 说明工具做什么
- 说明什么时候使用（触发场景）
- 清晰明确，让 LLM 能正确判断是否调用

### 步骤 3：注册分发

在 `TOOL_FUNCTIONS` 字典中添加：

```python
TOOL_FUNCTIONS = {
    "web_search": tool_web_search,
    "read_file": tool_read_file,
    "list_files": tool_list_files,
    "calculator": tool_calculator,
    "show_image": tool_show_image,
    "weather": tool_weather,  # 新工具
}
```

### 步骤 4：测试

1. 启动程序
2. 输入触发工具的对话（如"长春今天天气怎么样"）
3. 观察是否正确调用工具并返回结果

---

## 添加新的配置项

### 步骤 1：在 config.example.json 中添加

```json
"new_config": {
  "option1": "value1",
  "option2": 42
}
```

### 步骤 2：在 terminal_chat.py 中读取

在配置加载区域添加：

```python
NEW_CONFIG = CONFIG.get("new_config", {})
OPTION1 = NEW_CONFIG.get("option1", "default_value")
OPTION2 = NEW_CONFIG.get("option2", 0)
```

### 步骤 3：在代码中使用

```python
if OPTION1 == "value1":
    # 执行逻辑
    pass
```

### 步骤 4：更新文档

在 `docs/configuration.md` 中添加新配置项的说明。

---

## 修改系统提示词

### 方法 1：通过配置文件（推荐）

修改 `config.json` 中的 `system_prompt` 字段：

```json
"system_prompt": "你是一个 helpful 的助手，用中文回答问题。不要使用Markdown格式。"
```

### 方法 2：修改代码默认值

在 `terminal_chat.py` 中修改默认值：

```python
SYSTEM_PROMPT = CONFIG.get("system_prompt", "你的默认系统提示词")
```

### 注意事项

- 系统提示词会与长期记忆合并后发送给模型
- 过于复杂的系统提示词可能影响模型的工具调用能力
- 建议保持简洁，只包含必要的格式和行为约束

---

## 代码规范

### 文件结构

所有逻辑集中在 `terminal_chat.py` 单文件中，按区域组织：

```
# ================== 配置 ==================
# ================== Provider 适配层 ==================
# ================== 工具定义 ==================
# ================== 工具函数 ==================
# ================== 核心对话 ==================
# ================== 记忆系统 ==================
# ================== 主程序 ==================
```

### 命名规范

- 函数：`snake_case`，工具函数用 `tool_` 前缀
- 变量：`snake_case`，全局常量用 `UPPER_SNAKE_CASE`
- 配置项：`snake_case`

### 错误处理

- 所有外部调用（API、文件、网络）必须有 try-except
- 异常时返回错误信息字符串，不抛出异常
- 工具函数异常不能中断主程序

### 安全原则

- 不硬编码 API 密钥
- 文件读取限制后缀和大小
- 计算器禁用内置函数，只用白名单
- `.gitignore` 排除所有敏感文件
