# 技术文档

Synloquer 项目的完整技术文档。

## 文档索引

| 文档 | 内容 |
|------|------|
| [架构概览](architecture.md) | 整体架构、数据流、核心设计决策 |
| [Provider 适配层](provider-adapter.md) | 多模型服务商适配详解，三种 API 模式 |
| [工具调用系统](tool-system.md) | 5 个内置工具详解，工具分发机制 |
| [长期记忆系统](memory-system.md) | 记忆加载/更新/安全机制 |
| [配置系统](configuration.md) | config.json 和 .env 配置详解 |
| [扩展指南](extension-guide.md) | 如何添加新服务商、新工具、新配置 |

## 快速导航

### 我想了解...

- **项目整体怎么工作的？** → [架构概览](architecture.md)
- **切换不同 AI 模型需要改什么？** → [Provider 适配层](provider-adapter.md) + [配置系统](configuration.md)
- **工具调用是怎么实现的？** → [工具调用系统](tool-system.md)
- **AI 怎么记住之前的对话？** → [长期记忆系统](memory-system.md)
- **我想添加一个新工具** → [扩展指南](extension-guide.md#添加新工具)
- **我想支持一个新的 AI 服务商** → [扩展指南](extension-guide.md#添加新的-ai-服务商)

## 技术栈

- **语言**：Python 3.10+
- **依赖**：仅 `requests`
- **运行环境**：Windows 10/11 终端
- **无框架**：不使用 Flask/FastAPI/LangChain 等框架

## 核心特性

- 纯终端交互，无 Web 界面
- 8 家主流 AI 服务商适配
- 5 个内置工具（搜索、文件读取、文件列表、计算器、图片展示）
- 长期记忆持久化
- 对话自动总结
- 轻量图片查看器（旧版 Windows 照片查看器）
- 对话前缀自定义
