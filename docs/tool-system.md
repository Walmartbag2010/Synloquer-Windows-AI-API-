# 工具调用系统

## 概述

工具调用（Tool Calling / Function Calling）允许 LLM 在对话过程中调用外部函数，获取实时信息或执行操作。本项目实现了 5 个内置工具，遵循 OpenAI Function Calling 格式。

## 工具列表

| 工具名 | 功能 | 触发场景 |
|--------|------|----------|
| `web_search` | 博查联网搜索 | 查询实时信息、新闻、事实查证 |
| `read_file` | 读取本地文本文件 | 用户要求查看某个文件内容 |
| `list_files` | 列出目录文件 | 用户要求查看某个目录下有什么 |
| `calculator` | 安全数学计算 | 用户要求计算数学表达式 |
| `show_image` | 新窗口展示图片 | 用户要求打开/展示某张图片 |

## 工具定义格式

每个工具在 `TOOLS` 列表中定义，遵循 OpenAI Function Calling 格式：

```json
{
  "type": "function",
  "function": {
    "name": "web_search",
    "description": "使用博查搜索引擎搜索网页信息...",
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
}
```

## 工具分发机制

### 工具函数注册表

```python
TOOL_FUNCTIONS = {
    "web_search": tool_web_search,
    "read_file": tool_read_file,
    "list_files": tool_list_files,
    "calculator": tool_calculator,
    "show_image": tool_show_image,
}
```

### 调用流程

```
LLM 返回 tool_calls
  │
  ▼
保存 assistant 消息（含 tool_calls）
  │
  ▼
遍历每个 tool_call
  │
  ├─▶ 解析 function.name 和 function.arguments
  ├─▶ 从 TOOL_FUNCTIONS 查找对应函数
  ├─▶ 调用函数，传入参数
  ├─▶ 获取返回结果（字符串）
  └─▶ 保存 tool 结果消息
  │
  ▼
将 tool 结果消息加入 messages
  │
  ▼
进入下一轮 LLM 调用（LLM 根据工具结果生成回复）
```

### 消息格式

**Assistant 消息（含工具调用）**：
```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "web_search",
        "arguments": "{\"query\": \"今天天气\"}"
      }
    }
  ]
}
```

**Tool 结果消息**：
```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "搜索结果..."
}
```

## 各工具详解

### 1. web_search（博查搜索）

**API 端点**：`https://api.bocha.cn/v1/web-search`

**请求头**：`Authorization: Bearer {BOCHA_API_KEY}`

**请求体**：
```json
{
  "query": "搜索关键词",
  "count": 5,
  "summary": true
}
```

**响应解析**：从 `data.webPages.value` 提取搜索结果，格式化为标题+摘要+URL的列表。

**安全措施**：
- 结果数量限制 1-20
- 超时 30 秒
- 异常时返回错误信息而非崩溃

### 2. read_file（读取文件）

**路径解析**：`_resolve_path(path)` 函数处理相对路径，基于 `WORKSPACE_DIR` 解析。

**安全限制**：
- 只允许读取特定后缀：`.txt`, `.md`, `.log`, `.py`, `.json`, `.csv`, `.xml`, `.html`, `.css`, `.js`, `.yaml`, `.yml`, `.ini`, `.cfg`, `.bat`, `.ps1`
- 最大读取 50000 字符（`MAX_FILE_READ_SIZE`）
- 不允许读取目录
- 不允许读取二进制文件

**返回格式**：文件内容纯文本，或错误信息。

### 3. list_files（列出目录）

**按类型分组**：
- 文件夹单独列出
- 文件按类型分组：图片、文档、视频、音频、代码、压缩包、其他
- 图片类型完整列出（最常用）
- 其他类型超过 10 个时只显示前 10 个，提示用 `file_type` 筛选

**支持的 file_type 参数**：`all` / `image` / `document` / `video` / `audio` / `code` / `archive` / `other`

**设计原因**：目录文件过多时输出会被截断，按类型分组确保关键信息（如图片文件名）完整可见。

### 4. calculator（计算器）

**安全命名空间**：只允许数学函数和常量，禁止执行任意代码。

```python
safe_namespace = {
    "abs": abs, "round": round, "min": min, "max": max,
    "sqrt": math.sqrt, "pow": math.pow, "exp": math.exp,
    "log": math.log, "log2": math.log2, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "pi": math.pi, "e": math.e, "ceil": math.ceil, "floor": math.floor,
}
```

**实现**：使用 `eval(expression, {"__builtins__": {}}, safe_namespace)`，禁用内置函数，只允许白名单中的数学函数。

### 5. show_image（图片展示）

**支持来源**：
- 网络 URL：自动下载到 `temp_images/` 临时目录
- 本地路径：直接打开

**支持格式**：jpg, jpeg, png, gif, bmp, webp, tiff, tif, svg

**打开方式（按优先级尝试）**：

| 优先级 | 方式 | 说明 |
|--------|------|------|
| 1 | 旧版 Windows 照片查看器 | `rundll32 PhotoViewer.dll ImageView_Fullscreen`，最轻量，无需文件关联 |
| 2 | 画图 | `mspaint.exe`，系统自带 |
| 3 | `os.startfile` | 默认关联程序，可能弹"打开方式"对话框 |
| 4 | `explorer.exe` | 资源管理器打开 |
| 5 | 浏览器 | `webbrowser.open`，最后兜底 |

**窗口大小控制**：
- 启动后通过 Windows API（`EnumWindows` + `SetWindowPos`）找到窗口
- 调整为屏幕约 55% 宽、65% 高，最大 1100×800
- 居中显示
- 进程完全分离（`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`），不阻塞终端

**轮询等待**：启动后最多等待 3 秒，每 0.1 秒检查窗口是否创建。

## 工具调用循环

```python
max_tool_rounds = 8  # 最多8轮工具调用，防止死循环
tool_round = 0

while tool_round < max_tool_rounds:
    tool_round += 1
    # 调用 LLM
    # 解析响应
    # 如果有 tool_calls，执行工具，继续循环
    # 如果没有 tool_calls，返回最终回复
```

**防死循环**：最多 8 轮工具调用，超过后强制返回。

## 扩展新工具

添加新工具需要 3 步：

1. **定义工具函数**：`def tool_xxx(param1, param2="default") -> str`
2. **添加工具定义**：在 `TOOLS` 列表中添加 JSON Schema 定义
3. **注册分发**：在 `TOOL_FUNCTIONS` 字典中添加 `"xxx": tool_xxx`

详见 [扩展指南](extension-guide.md)。

## 限制与注意事项

1. **Anthropic 暂不支持工具调用**：当前 provider 为 anthropic 时，请求中不发送 tools 参数，启动时显示提示
2. **工具结果为字符串**：所有工具返回字符串，LLM 根据字符串内容生成回复
3. **无状态工具**：工具调用是无状态的，不保存上下文
4. **文件读取安全**：只允许读取白名单后缀的文本文件，防止读取敏感文件（如 .env、密钥文件）
