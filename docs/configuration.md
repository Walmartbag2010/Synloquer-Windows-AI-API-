# 配置系统

## 概述

项目使用两个配置文件：
- `config.json` — 程序配置（服务商、模型、前缀、窗口大小等）
- `.env` — 密钥配置（API Key、Base URL 等）

两个文件分离的原因：密钥敏感，不应与程序配置混在一起；`.env` 放在桌面，`config.json` 放在项目目录。

## config.json

### 文件位置

项目根目录下的 `config.json`。首次运行时自动从 `config.example.json` 复制创建。

### 配置项详解

```json
{
  "env_file_path": "D:\\HuaweiMoveData\\Users\\HUAWEI\\Desktop\\.env",
  "models": {
    "chat": "deepseek-v4-pro",
    "summary": "deepseek-v4-flash"
  },
  "provider": "deepseek",
  "system_prompt": "不要使用Markdown格式。",
  "chat_prefix": {
    "user": "我：",
    "assistant": "AI："
  },
  "image_window": {
    "width_ratio": 0.55,
    "height_ratio": 0.65,
    "max_width": 1100,
    "max_height": 800
  },
  "available_providers": { ... },
  "search": { ... }
}
```

### 基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `env_file_path` | string | 桌面 `.env` | `.env` 密钥文件的完整路径 |
| `provider` | string | `deepseek` | AI 服务商，决定 API 调用方式 |
| `models.chat` | string | `deepseek-v4-pro` | 对话模型名称 |
| `models.summary` | string | `deepseek-v4-flash` | 总结/记忆模型名称 |
| `system_prompt` | string | `不要使用Markdown格式。` | 系统提示词 |

### 对话前缀配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `chat_prefix.user` | string | `我：` | 用户输入前缀 |
| `chat_prefix.assistant` | string | `AI：` | AI 回复前缀 |

前缀可自定义为任意字符串，如 `User: `、`>>> `、`主人：` 等。

### 图片窗口配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `image_window.width_ratio` | float | `0.55` | 窗口宽度占屏幕比例 |
| `image_window.height_ratio` | float | `0.65` | 窗口高度占屏幕比例 |
| `image_window.max_width` | int | `1100` | 窗口最大宽度（像素） |
| `image_window.max_height` | int | `800` | 窗口最大高度（像素） |

窗口大小计算公式：
```
width = min(screen_width * width_ratio, max_width)
height = min(screen_height * height_ratio, max_height)
```

### 服务商配置

`available_providers` 预配置了 8 家主流服务商：

```json
"deepseek": {
  "base_url": "https://api.deepseek.com",
  "env_key": "DEEPSEEK_API_KEY",
  "models": ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"]
}
```

每个服务商包含：
- `base_url` — API 基础 URL
- `env_key` — 对应的环境变量名（从 `.env` 读取）
- `models` — 可用模型列表（参考用，实际调用以 `models.chat` 为准）

### 搜索配置

```json
"search": {
  "provider": "bocha",
  "bocha": {
    "base_url": "https://api.bocha.cn/v1/web-search",
    "env_key": "BOCHA_API_KEY"
  },
  "tavily": {
    "base_url": "https://api.tavily.com/search",
    "env_key": "TAVILY_API_KEY"
  }
}
```

> 注：当前仅实现了博查搜索，Tavily 为预留配置。

## .env 文件

### 文件位置

由 `config.json` 中的 `env_file_path` 指定，默认放在桌面。

### 格式

标准的 `KEY=VALUE` 格式，支持注释（`#` 开头）：

```env
# DeepSeek
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 博查搜索
BOCHA_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 预配置的密钥变量

`.env.example` 预格式化了以下密钥位置：

| 服务商 | API Key 变量 | Base URL 变量 |
|--------|-------------|---------------|
| DeepSeek | `DEEPSEEK_API_KEY` | `DEEPSEEK_BASE_URL` |
| OpenAI | `OPENAI_API_KEY` | `OPENAI_BASE_URL` |
| Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` |
| 智谱 | `ZHIPU_API_KEY` | `ZHIPU_BASE_URL` |
| 通义千问 | `DASHSCOPE_API_KEY` | `DASHSCOPE_BASE_URL` |
| Moonshot | `MOONSHOT_API_KEY` | `MOONSHOT_BASE_URL` |
| MiniMax | `MINIMAX_API_KEY` | `MINIMAX_BASE_URL` |
| 百度文心 | `BAIDU_API_KEY` + `BAIDU_SECRET_KEY` | `BAIDU_BASE_URL` |
| 博查搜索 | `BOCHA_API_KEY` | `BOCHA_BASE_URL` |
| Tavily 搜索 | `TAVILY_API_KEY` | `TAVILY_BASE_URL` |

## 配置加载流程

```
程序启动
  │
  ├─▶ 检查 config.json 是否存在
  │     ├─▶ 不存在：从 config.example.json 复制创建
  │     └─▶ 存在：直接读取
  │
  ├─▶ 解析 config.json，获取 env_file_path
  │
  ├─▶ 加载 .env 文件
  │     ├─▶ 读取 env_file_path 指定的文件
  │     ├─▶ 解析 KEY=VALUE，注入环境变量
  │     └─▶ 如果失败，尝试桌面默认路径兜底
  │
  ├─▶ 根据 provider 获取对应配置
  │     ├─▶ base_url
  │     └─▶ env_key（对应的 API Key 环境变量名）
  │
  ├─▶ 从环境变量读取 API_KEY
  │
  └─▶ 所有配置就绪，开始对话
```

## 配置验证

启动时显示当前配置，便于验证：

```
========================================================
  AI 终端聊天室（工具增强版）
  服务商: deepseek | 模型: deepseek-v4-pro
  总结模型: deepseek-v4-flash
  密钥文件: D:\...\Desktop\.env
  搜索: bocha | 工具: 搜索/文件读取/文件列表/计算器/图片
  对话前缀: 用户="我：" AI="AI："
  长期记忆: 已加载 (2414 字符)
========================================================
```

如果 `.env` 文件未找到，显示警告：
```
  [警告] 未找到 .env 密钥文件，请检查 config.json 中的 env_file_path
```

## 安全考虑

1. **`.gitignore` 排除**：`config.json` 和 `.env` 都已加入 `.gitignore`，不会上传到 GitHub
2. **模板上传**：`config.example.json` 和 `.env.example` 上传到 GitHub，作为参考模板
3. **密钥不硬编码**：所有 API Key 都从 `.env` 读取，代码中无硬编码密钥
4. **桌面隔离**：`.env` 放在桌面而非项目目录，减少意外提交风险

## 常见问题

### Q: 修改 config.json 后需要重启吗？
A: 是的，配置在启动时加载，修改后需要重启程序生效。

### Q: 可以把 .env 放在其他位置吗？
A: 可以，修改 `config.json` 中的 `env_file_path` 为任意完整路径即可。

### Q: 切换服务商需要修改哪些配置？
A: 修改 `provider` 字段，以及对应的 `models.chat` 和 `models.summary`。确保 `.env` 中有对应服务商的 API Key。

### Q: 百度文心为什么需要两个密钥？
A: 百度文心使用 API Key + Secret Key 换取 access_token 的认证方式，两个都需要配置。
