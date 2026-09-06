# DeepSeek 终端聊天室 AI Agent

基于 DeepSeek V4 Pro 模型的纯终端 AI 对话助手，支持工具调用（博查搜索、本地文件读取、计算器、图片展示）、长期记忆和多轮对话。

## 功能特性

- **纯终端交互**：Windows 终端中直接对话，"我："/"AI："前缀，无需 Web 界面
- **DeepSeek V4 Pro**：对话使用 deepseek-v4-pro，总结/记忆使用 deepseek-v4-flash
- **工具调用**：
  - `web_search` — 博查搜索（Bocha），联网检索
  - `read_file` — 读取本地文本文件
  - `list_files` — 列出目录文件，按类型分组（图片/文档/视频/音频/代码）
  - `calculator` — 安全数学计算器
  - `show_image` — 在新窗口展示本地/网络图片（旧版 Windows 照片查看器，自动调整窗口大小居中）
- **长期记忆**：启动时加载 `memory.md` 注入系统提示，对话结束后用 flash 模型更新记忆
- **对话总结**：退出时自动生成对话总结，保存到 `summaries/` 目录
- **完整记录**：所有对话保存到 `chat_logs/` 目录
- **在线状态**：启动时检测 API 连通性，显示在线/离线状态
- **极简系统提示**：仅要求模型不使用 Markdown 格式

## 安装

### 环境要求

- Windows 10/11
- Python 3.10+

### 步骤

1. 克隆仓库：
```bash
git clone <your-repo-url>
cd My_Agent
```

2. 创建虚拟环境并安装依赖：
```bash
python -m venv agent_env
agent_env\Scripts\activate
pip install -r requirements.txt
```

3. 配置 API 密钥：

在桌面创建 `.env` 文件（路径：`%USERPROFILE%\Desktop\.env`），内容如下：
```
DEEPSEEK_API_KEY=sk-你的deepseek密钥
BOCHA_API_KEY=sk-你的博查密钥
```

> 密钥文件放在桌面而非项目目录，避免意外提交到 Git。

## 使用方法

### 启动

双击 `启动终端聊天.bat`，或在命令行中：
```bash
agent_env\Scripts\python.exe terminal_chat.py
```

### 交互

- 启动后显示在线状态和长期记忆加载情况
- 输入消息后按回车发送
- AI 回复以 `AI：` 前缀显示，流式输出
- 输入 `exit`、`quit` 或按 `Ctrl+C` 退出
- 退出时自动生成对话总结并更新长期记忆

### 示例对话

```
我：帮我搜索一下今天的天气
AI：[调用 web_search 工具] 已为你搜索...
我：打开桌面上的风景照片
AI：[调用 show_image 工具] 已在新窗口中展示图片（窗口 844×624，居中）
我：计算一下 128 的平方根
AI：[调用 calculator 工具] 128 的平方根约为 11.31
```

## 工具说明

### show_image 图片展示

- 支持本地路径和网络 URL
- 优先使用旧版 Windows 照片查看器（轻量、纯查看、支持放大缩小）
- 窗口自动调整为屏幕约 55% 大小，居中显示
- 网络图片自动下载到 `temp_images/` 临时目录
- 支持格式：jpg, jpeg, png, gif, bmp, webp, tiff, svg

### list_files 文件列表

- 按类型分组显示（图片/文档/视频/音频/代码/压缩包/其他）
- 图片类型完整列出，其他类型超过 10 个提示用 `file_type` 筛选
- 支持 `file_type` 参数筛选特定类型

## 项目结构

```
My_Agent/
├── terminal_chat.py        # 主程序
├── 启动终端聊天.bat          # 启动脚本
├── requirements.txt        # Python 依赖
├── .gitignore             # Git 忽略规则
├── README.md              # 本文件
├── memory.md              # 长期记忆（本地，不上传）
├── chat_logs/             # 完整对话记录（本地，不上传）
├── summaries/             # 对话总结（本地，不上传）
├── temp_images/           # 临时图片（本地，不上传）
├── workspace/             # Agent 工作区（本地，不上传）
└── agent_env/             # Python 虚拟环境（本地，不上传）
```

## 注意事项

- **API 密钥安全**：密钥存储在桌面 `.env` 文件，项目目录的 `.gitignore` 已排除所有 `.env` 文件
- **隐私保护**：对话记录、长期记忆等含个人信息的文件均已加入 `.gitignore`，不会上传到 GitHub
- **flash 模型配置**：deepseek-v4-flash 必须设置 `"thinking": {"type": "disabled"}`，否则 `content` 字段为空
- **图片查看器**：依赖 Windows 旧版照片查看器（`PhotoViewer.dll`），Windows 10/11 自带
- **博查搜索**：需在 [博查开放平台](https://bocha.cn) 注册获取 API Key

## License

MIT
