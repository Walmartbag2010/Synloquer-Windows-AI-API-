# 长期记忆系统

## 概述

长期记忆系统让 AI 能够在多次对话之间保留用户的关键信息，实现"每次对话前复习之前的对话"的效果。记忆以 Markdown 文件形式持久化到本地，启动时加载注入系统提示，对话结束后自动更新。

## 核心机制

### 记忆文件

- **路径**：`memory.md`（项目根目录）
- **格式**：纯文本 Markdown，每行一条记忆，以 `-` 开头
- **编码**：UTF-8
- **备份**：更新前自动备份为 `memory.md.bak`

### 记忆生命周期

```
启动时
  │
  ├─▶ 读取 memory.md
  ├─▶ 注入到系统提示词（SYSTEM_PROMPT + 记忆内容）
  └─▶ 显示记忆加载状态（字符数）

对话中
  │
  └─▶ 每次对话都携带记忆（通过系统提示词）

退出时
  │
  ├─▶ 用 flash 模型生成新记忆
  ├─▶ 安全校验（长度突变检测）
  ├─▶ 备份旧记忆
  └─▶ 写入 memory.md
```

## 启动加载

### 加载逻辑

```python
def load_memory() -> str:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""
```

### 注入系统提示

记忆内容被追加到系统提示词中，让模型在每次对话前"复习"之前的记忆：

```python
system_prompt_with_memory = SYSTEM_PROMPT + "\n\n【长期记忆】\n" + memory
```

### 启动界面显示

```
  长期记忆: 已加载 (2414 字符)
```

## 对话更新

### 更新触发

用户输入 `exit` / `quit` 或按 `Ctrl+C` 退出时触发记忆更新。

### 更新 Prompt

```
你是一个记忆整理助手。以下是已有的长期记忆和本次对话内容。

请更新长期记忆：
1. 必须保留已有记忆中的所有信息点，一条都不能删除
2. 从本次对话中提取值得长期记住的新信息
3. 合并重复信息，保持简洁
4. 每条记忆一行，以 - 开头
5. 只输出记忆内容本身，不要输出解释

已有记忆：
{existing_memory}

本次对话：
{conversation_text}
```

**关键约束**：`必须保留已有记忆中的所有信息点，一条都不能删除`——防止模型总结时丢失重要信息。

### 使用的模型

- **模型**：`MODEL_SUMMARY`（默认 `deepseek-v4-flash`）
- **流式**：否（非流式，等待完整结果）
- **temperature**：0.3（低随机性，保证稳定性）
- **max_tokens**：4096
- **thinking**：`disabled`（必须禁用思考模式，否则 content 为空）

## 安全机制

### 1. 长度突变检测

```python
if existing_memory and len(new_memory) < len(existing_memory) * 0.5:
    print("[警告] 新记忆明显短于旧记忆，可能丢失信息")
    print("[警告] 为安全起见，保留旧记忆，新记忆追加到末尾")
    new_memory = existing_memory + "\n" + new_memory
```

如果新记忆长度不到旧记忆的 50%，判定为可能丢失信息，自动改为追加模式（旧记忆 + 新记忆），而非覆盖。

### 2. 自动备份

```python
if existing_memory and os.path.exists(MEMORY_FILE):
    backup_path = MEMORY_FILE + ".bak"
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(existing_memory)
```

更新前自动将旧记忆备份为 `memory.md.bak`，如更新出错可手动恢复。

### 3. 异常处理

```python
try:
    # 调用 API 生成新记忆
    # 安全校验
    # 备份
    # 写入
except Exception as e:
    print(f"[记忆更新失败] {e}，已有记忆保持不变")
    return
```

任何异常都不会导致记忆丢失，旧记忆保持不变。

## 记忆恢复

### 从对话总结恢复

如果记忆文件丢失或损坏，可以从 `summaries/` 目录下的历史对话总结中恢复：

1. 读取所有历史总结文件
2. 提取关键信息点
3. 用 flash 模型整理为记忆格式
4. 写入 `memory.md`

### 从备份恢复

`memory.md.bak` 保存了上一次更新前的记忆，直接复制回 `memory.md` 即可恢复。

## 记忆内容示例

```markdown
- 用户是长春高中生，目标2029年高考，意向中国药科大学药学专业
- 四岁开始学英语，中考700.5分（差9分满分）
- 与ZPY是镜面式关系的朋友
- 喜欢陈绮贞的音乐，尤其是《慢歌3》
- 正在开发基于DeepSeek的终端聊天室AI Agent项目
- 偏好直接获取可执行完整代码，拒绝引导式提问
- 使用华为D16笔记本，16GB内存
- 对Windows桌面应用UI/UX有严格规范，偏好极简风格
```

## 设计决策

### 为什么用文件而非数据库

- 记忆数据量小（通常几千字符），文件足够
- 人类可读，可手动编辑
- 无需数据库依赖，部署简单
- 版本管理友好（可纳入 Git）

### 为什么用 flash 模型而非 pro 模型

- 记忆整理是简单任务，flash 模型足够
- flash 模型更快、更便宜
- 低 temperature 保证稳定性

### 为什么追加保留式而非覆盖式

- 覆盖式可能丢失重要信息（模型总结时容易遗漏）
- 追加保留式确保信息不丢失，代价是记忆可能逐渐变长
- 长度突变检测作为兜底，极端情况下自动切换为追加

## 隐私保护

- `memory.md` 已加入 `.gitignore`，不会上传到 GitHub
- 记忆文件只保存在本地，不发送到任何第三方服务器（除了调用 LLM API 时作为 prompt 的一部分）
- 用户可随时手动编辑或删除记忆文件
