*寂寞谁不会有，烦恼谁不会有*

——陈绮贞《慢歌3》



# Synloquer



> 一个轻量化的终端 LLM 聊天窗口。漆黑的，安静的，只属于你的。



## 序



每一个人都会有孤独的时刻，也许你会有一些话不想对任何人说。不是因为没有值得信任的人，而是因为有些话在说出口之前，连自己都还没想清楚。它需要先落在一个地方——不用是对的，不用是完整的，甚至不用被记住。



现在，你可以在这个漆黑的窗口里，把话说给一个 LLM。它不是一个朋友，不会用"我懂你"来打断你；它也不是一面镜子，不会把你的话原样照回来。它更像一堵会回应的墙：你丢进去什么，它就轻轻响一下。



随心所欲，不用承担任何责任。这里没有听众，所以也就没有表演。你可以是最无聊的人，也可以是最锋利的人；可以打一半就删掉，也可以发出去之后才发现那其实不是你想说的。都没有关系。漆黑窗口的好处在于，它从不替你记住，所以你说的每一句，都只属于说出口的那一秒。



## 这是什么



基于 DeepSeek V4 Pro 的纯终端 AI 对话助手。没有 Web 界面，没有花哨的 UI，只有一个黑色的命令行窗口和闪烁的光标。支持工具调用（联网搜索、本地文件读取、计算器、图片展示）、长期记忆、对话总结，以及 8 家主流模型服务商的自由切换。



**核心特性：**

- **纯终端交互** — Windows 终端直接对话，`我：` / `AI：` 前缀，前缀可自定义
- **工具调用** — 博查联网搜索、本地文件读取/列表、安全计算器、新窗口展示图片
- **长期记忆** — 启动时加载记忆，对话结束后自动更新，它会"记得"你说过的话
- **对话总结** — 退出时自动生成本次对话总结，保存到本地
- **多服务商支持** — DeepSeek / OpenAI / Anthropic / 智谱 / 通义千问 / Moonshot / MiniMax / 百度文心，改一行配置即可切换
- **轻量图片查看器** — 调用旧版 Windows 照片查看器，窗口自动调整大小居中，不抢焦点
- **极简系统提示** — 只要求模型不使用 Markdown，不说教，不表演



## 安装



### 快速开始（推荐）

```bash
git clone https://github.com/Walmartbag2010/silver-telegram.git
cd silver-telegram
```

然后双击 `配置Synloquer.bat`，配置向导会自动：
- 创建 Python 虚拟环境并安装依赖
- 从模板生成配置文件
- 用记事本打开配置引导你填写



### 手动安装

```bash
python -m venv agent_env
agent_env\Scripts\activate
pip install -r requirements.txt
```



## 配置



### 1. 配置文件

首次运行会自动从 `config.example.json` 创建 `config.json`，可编辑以下内容：

```json
{
  "env_file_path": "C:\\Users\\你的用户名\\Desktop\\.env",
  "provider": "deepseek",
  "models": {
    "chat": "deepseek-v4-pro",
    "summary": "deepseek-v4-flash"
  },
  "chat_prefix": {
    "user": "我：",
    "assistant": "AI："
  },
  "system_prompt": "不要使用Markdown格式。",
  "image_window": {
    "width_ratio": 0.55,
    "height_ratio": 0.65
  }
}
```



### 2. 密钥文件

复制 `.env.example` 为 `.env`，放到 `env_file_path` 指定的位置，填入密钥：

```env
# DeepSeek
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 博查搜索
BOCHA_API_KEY=sk-你的密钥
```

> `.env.example` 已预格式化 8 家模型服务商和 2 家搜索服务商的密钥位置，按需填写即可。



## 使用



### 启动

双击 `启动Synloquer.bat`，或：

```bash
agent_env\Scripts\python.exe synloquer.py
```



### 交互

启动后会显示当前配置：

```
========================================================
  AI 终端聊天室（工具增强版）
  服务商: deepseek | 模型: deepseek-v4-pro
  总结模型: deepseek-v4-flash
  密钥文件: C:\Users\...\Desktop\.env
  搜索: bocha | 工具: 搜索/文件读取/文件列表/计算器/图片
  对话前缀: 用户="我：" AI="AI："
  长期记忆: 已加载 (2414 字符)
========================================================

我：
```

- 输入消息后按回车发送
- AI 回复流式输出
- 输入 `exit`、`quit` 或按 `Ctrl+C` 退出
- 退出时自动生成对话总结并更新长期记忆



### 工具调用

AI 会根据对话内容自动调用工具，无需手动输入命令：

| 工具 | 功能 | 示例触发语 |
|------|------|-----------|
| `web_search` | 博查联网搜索 | "今天天气怎么样"、"查一下某某新闻" |
| `read_file` | 读取本地文本文件 | "看看这个文件写了什么" |
| `list_files` | 列出目录文件 | "桌面上有什么" |
| `calculator` | 安全数学计算 | "算一下 128 的平方根" |
| `show_image` | 新窗口展示图片 | "打开那张风景照" |



### 图片展示

AI 调用 `show_image` 后，会用旧版 Windows 照片查看器在新窗口打开图片：
- 窗口自动调整为屏幕约 55% 大小，居中显示
- 不抢焦点，不打断终端输入
- 滚轮放大缩小，方向键切换同目录图片
- 支持本地路径和网络 URL



## 项目结构

```
silver-telegram/
├── synloquer.py           # 主程序
├── 启动Synloquer.bat         # 启动脚本
├── 配置Synloquer.bat         # 首次配置向导
├── config.example.json     # 配置模板
├── config.json             # 实际配置（自动创建，不上传）
├── .env.example            # 密钥模板
├── requirements.txt        # Python 依赖
├── README.md              # 你正在读的这个
├── memory.md              # 长期记忆（本地，不上传）
├── chat_logs/             # 完整对话记录（本地，不上传）
├── summaries/             # 对话总结（本地，不上传）
├── temp_images/           # 临时图片（本地，不上传）
└── agent_env/             # Python 虚拟环境（本地，不上传）
```



## 注意事项

- **API 密钥安全**：密钥存储在桌面 `.env` 文件，不硬编码在代码中；`config.json` 和所有隐私文件已加入 `.gitignore`
- **flash 模型配置**：deepseek-v4-flash 必须设置 `thinking: disabled`，否则返回空内容（代码已自动处理）
- **图片查看器**：依赖 Windows 旧版照片查看器（`PhotoViewer.dll`），Windows 10/11 自带
- **长期记忆**：记忆文件保存在本地，不会上传到任何服务器



## 技术文档

完整的技术文档位于 [`docs/`](docs/) 目录：

| 文档 | 内容 |
|------|------|
| [架构概览](docs/architecture.md) | 整体架构、数据流、核心设计决策 |
| [Provider 适配层](docs/provider-adapter.md) | 多模型服务商适配，三种 API 模式详解 |
| [工具调用系统](docs/tool-system.md) | 5 个内置工具详解，工具分发机制 |
| [长期记忆系统](docs/memory-system.md) | 记忆加载/更新/安全机制 |
| [配置系统](docs/configuration.md) | config.json 和 .env 配置详解 |
| [扩展指南](docs/extension-guide.md) | 添加新服务商、新工具、新配置 |



## 声明



本项目为 AI vibe coding 产物。
