*寂寞谁不会有，烦恼谁不会有*

——陈绮贞《慢歌3》



# Synloquer



> 一个轻量化的终端 LLM 聊天窗口。漆黑的，安静的，只属于你的。



## 序



每一个人都会有孤独的时刻，也许你会有一些话不想对任何人说。不是因为没有值得信任的人，而是因为有些话在说出口之前，连自己都还没想清楚。它需要先落在一个地方——不用是对的，不用是完整的，甚至不用被记住。



现在，你可以在这个漆黑的窗口里，把话说给一个 LLM。它不是一个朋友，不会用"我懂你"来打断你；它也不是一面镜子，不会把你的话原样照回来。它更像一堵会回应的墙：你丢进去什么，它就轻轻响一下。



随心所欲，不用承担任何责任。这里没有听众，所以也就没有表演。你可以是最无聊的人，也可以是最锋利的人；可以打一半就删掉，也可以发出去之后才发现那其实不是你想说的。都没有关系。漆黑窗口的好处在于，它从不替你记住，所以你说的每一句，都只属于说出口的那一秒。

（Synloquer 这个词不会读？没关系，翻到结尾处有发音。）



## 这是什么

**Synloquer · 终端双向对话助手**　—　Two‑way AI chat in your terminal.



基于 DeepSeek V4 Pro 的纯终端 AI 对话助手。没有 Web 界面，没有花哨的 UI，只有一个黑色的命令行窗口和闪烁的光标。支持 10 个工具调用、长期记忆（检索/遗忘/压缩三大机制）、对话总结、对话时间统计，以及 8 家主流模型服务商的自由切换。采用模块化架构，主程序仅 230 行，核心逻辑拆分到 9 个独立模块。



**核心特性：**

- **纯终端交互** — Windows 终端直接对话，`我：` / `AI：` 前缀，前缀可自定义
- **10 个工具调用** — 联网搜索、文件读取/列表、计算器、图片展示、词汇统计、词云图、对话时间统计、历史对话检索、数据整理
- **长期记忆系统** — 检索（动态相关度匹配）、遗忘（过期自动清理）、压缩（超量自动合并）三大机制，记忆会"记得"你说过的话
- **对话总结** — 退出时自动生成本次对话总结，保存到本地
- **多服务商支持** — DeepSeek / OpenAI / Anthropic / 智谱 / 通义千问 / Moonshot / MiniMax / 百度文心，改一行配置即可切换
- **轻量图片查看器** — 调用旧版 Windows 照片查看器，窗口自动调整大小居中，不抢焦点
- **词汇分析** — 中英文混合分词（jieba）、词频统计、词云图生成
- **对话数据分析** — 时间分布统计、历史记录检索排序、flash 模型代理数据整理
- **模块化架构** — 9 个独立模块，配置/Provider/记忆/工具/存储/日志/重试分离
- **稳定性保障** — 所有 API 调用内置 3 次指数退避重试，分级日志系统
- **极简系统提示** — 只要求模型不使用 Markdown，不说教，不表演



## 安装



### 快速开始（推荐）

```bash
git clone https://github.com/Walmartbag2010/Synloquer-Windows-AI-API-.git
cd Synloquer-Windows-AI-API-
```

然后双击 `启动Synloquer.bat`，首次运行会自动调用 Python 配置向导 `setup.py`：
- 检测/创建 Python 虚拟环境并安装依赖
- 交互式选择服务商（8家，带中文标签）
- 引导填写模型、env路径、对话前缀
- 引导填写 API 密钥（根据当前服务商动态显示）
- 配置完成后可选择立即启动



### 手动安装

```bash
python -m venv agent_env
agent_env\Scripts\activate
pip install -r requirements.txt
python setup.py
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
  },
  "memory": {
    "max_items": 100,
    "retrieval_top_k": 15,
    "forget_days_low": 30,
    "forget_days_normal": 60,
    "compress_threshold": 80
  }
}
```

**记忆系统配置说明：**
- `max_items`：记忆最大条数，超过后触发压缩
- `retrieval_top_k`：每次对话检索返回的相关记忆条数
- `forget_days_low`：低重要性记忆超过多少天未访问自动删除
- `forget_days_normal`：普通记忆超过多少天未访问降级为低重要性
- `compress_threshold`：记忆超过多少条时自动触发压缩



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
  Synloquer - 终端 AI 对话助手
  服务商: deepseek | 模型: deepseek-v4-pro
  总结模型: deepseek-v4-flash
  密钥文件: C:\Users\...\Desktop\.env
  搜索: bocha | 工具: 搜索/文件读取/文件列表/计算器/图片
  对话前缀: 用户="我：" AI="AI："
  长期记忆: 已加载 (53 条，检索 top-15)
  输入消息开始对话，输入 exit 或 quit 结束并总结
========================================================

我：
```

- 输入消息后按回车发送
- AI 回复流式输出
- 输入 `exit`、`quit` 或按 `Ctrl+C` 退出
- 退出时自动生成对话总结、保存完整记录、更新长期记忆



### 工具调用

AI 会根据对话内容自动调用工具，无需手动输入命令：

| # | 工具 | 功能 | 示例触发语 |
|---|------|------|-----------|
| 1 | `web_search` | 博查联网搜索 | "今天天气怎么样"、"查一下某某新闻" |
| 2 | `read_file` | 读取本地文本文件 | "看看这个文件写了什么" |
| 3 | `list_files` | 列出目录文件 | "桌面上有什么" |
| 4 | `calculator` | 安全数学计算 | "算一下 128 的平方根" |
| 5 | `show_image` | 新窗口展示图片 | "打开那张风景照" |
| 6 | `word_frequency` | 词汇统计分析 | "统计这段文字的词频" |
| 7 | `generate_wordcloud` | 词云图生成 | "给这段文字生成词云" |
| 8 | `chat_time_stats` | 对话时间统计 | "看看我最近的对话时间分布" |
| 9 | `search_chat_history` | 历史对话检索 | "找一下之前聊过人工智能的对话" |
| 10 | `summarize_data` | 数据整理（flash代理） | "帮我整理这些数据，提取关键点" |



### 图片展示

AI 调用 `show_image` 后，会用旧版 Windows 照片查看器在新窗口打开图片：
- 窗口自动调整为屏幕约 55% 大小，居中显示
- 不抢焦点，不打断终端输入
- 滚轮放大缩小，方向键切换同目录图片
- 支持本地路径和网络 URL



### 长期记忆

Synloquer 的记忆系统采用三大机制：

**1. 检索记忆**
- 每次对话前，基于用户输入动态检索相关记忆
- 评分算法：关键词匹配 + 访问频率 + 重要性加权
- 只返回 top_k 条（默认15条），不全量塞入，节省 token
- 被检索到的记忆自动更新访问时间

**2. 遗忘机制**
- 低重要性记忆超过 30 天未访问 → 自动删除
- 普通记忆超过 60 天未访问 → 降级为低重要性
- 高重要性记忆永不自动删除
- 启动时自动执行一次遗忘检查

**3. 压缩记忆**
- 记忆总数超过 80 条时自动触发
- 用 flash 模型合并相似记忆、删除过时信息
- 高重要性记忆不参与压缩，直接保留
- 安全机制：压缩前备份，压缩后不少于原始 30%

记忆存储格式为结构化 JSON，含 id、创建时间、最后访问时间、访问次数、重要性、标签等元数据。首次运行自动从旧版 `memory.md` 迁移。



## 项目结构

```
Synloquer/
├── synloquer.py              # 主入口（230行），仅保留主循环和终端UI
├── synloquer_config.py       # 配置管理（config.json + .env 加载）
├── synloquer_provider.py     # 多模型API适配（OpenAI兼容/Anthropic/百度文心）
├── synloquer_memory.py       # 长期记忆系统（检索/遗忘/压缩）
├── synloquer_tools.py        # 工具调用系统（10个工具）
├── synloquer_storage.py      # 对话总结与完整记录保存
├── synloquer_logger.py       # 分级日志系统
├── synloquer_retry.py        # 指数退避重试机制
├── setup.py                  # Python交互式配置向导
├── 启动Synloquer.bat            # 启动脚本（首次运行自动配置）
├── config.example.json       # 配置模板
├── config.json               # 实际配置（自动创建，不上传）
├── .env.example              # 密钥模板
├── requirements.txt          # Python依赖
├── README.md                 # 你正在读的这个
├── docs/                     # 技术文档
├── memory.json               # 长期记忆（本地，不上传）
├── chat_logs/                # 完整对话记录（本地，不上传）
├── summaries/                # 对话总结（本地，不上传）
├── temp_images/              # 临时图片（本地，不上传）
├── logs/                     # 运行日志（本地，不上传）
└── agent_env/                # Python 虚拟环境（本地，不上传）
```



## 注意事项

- **API 密钥安全**：密钥存储在桌面 `.env` 文件，不硬编码在代码中；`config.json` 和所有隐私文件已加入 `.gitignore`
- **flash 模型配置**：deepseek-v4-flash 必须设置 `thinking: disabled`，否则返回空内容（代码已自动处理）
- **图片查看器**：依赖 Windows 旧版照片查看器（`PhotoViewer.dll`），Windows 10/11 自带
- **长期记忆**：记忆文件保存在本地，不会上传到任何服务器
- **仅支持 Windows**：图片展示、旧版照片查看器、启动脚本均为 Windows 专属
- **数据整理工具**：`summarize_data` 调用 flash 模型处理大量数据，会产生额外 API 调用费用



## 技术文档

完整的技术文档位于 [`docs/`](docs/) 目录：

| 文档 | 内容 |
|------|------|
| [架构概览](docs/architecture.md) | 整体架构、数据流、核心设计决策 |
| [Provider 适配层](docs/provider-adapter.md) | 多模型服务商适配，三种 API 模式详解 |
| [工具调用系统](docs/tool-system.md) | 10 个内置工具详解，工具分发机制 |
| [长期记忆系统](docs/memory-system.md) | 记忆检索/遗忘/压缩三大机制详解 |
| [配置系统](docs/configuration.md) | config.json 和 .env 配置详解 |
| [扩展指南](docs/extension-guide.md) | 添加新服务商、新工具、新配置 |



## 声明



本项目为 AI vibe coding 产物。



## 附录：关于 Synloquer

### 发音

- **国际音标**：英 /sɪnˈləʊkə(r)/　美 /sɪnˈloʊkər/
- **音节划分**：Syn‑lo‑quer（3 个音节）
- **重音位置**：第二个音节 `lo`
- **上口谐音**：辛‑洛‑克儿

### 词源

> **Etymology**
> `syn‑` (Greek prefix: mutual, joint, two‑way)
> + `loqu‑` (Latin root: to speak, converse)
> + `‑er` (agent suffix, means a tool or performer)
>
> Synloquer — A two‑way conversation tool, an AI chat client built for Windows Terminal.

Synloquer 取自词根组合：syn‑双向同步 + loqu‑交谈 + ‑er工具执行者。寓意一款运行于 Windows 终端、实现人与大模型双向对话的 AI 聊天室程序。

### 标语

**Synloquer · 终端双向对话助手**　—　Two‑way AI chat in your terminal.
