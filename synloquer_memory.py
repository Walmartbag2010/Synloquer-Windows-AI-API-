"""
Synloquer 长期记忆系统

实现三大核心机制：
1. 检索记忆 - 基于关键词相关性检索，只返回 top_k 条，而非全量塞入
2. 遗忘机制 - 长期未访问的低重要性记忆自动删除
3. 压缩记忆 - 记忆超过阈值时，用模型合并去重、精简过时信息

记忆存储格式（JSON）：
{
  "version": 2,
  "memories": [
    {"id": "...", "content": "...", "created_at": "...", "last_accessed": "...",
     "access_count": 0, "importance": "normal", "tags": []}
  ]
}

向后兼容旧版 memory.md（纯文本格式），首次加载时自动迁移。
"""

import json
import os
import re
import uuid
from datetime import datetime, timedelta

import synloquer_logger as logger
from synloquer_config import config
import synloquer_provider as provider


# ================== 数据结构 ==================

def _new_memory(content: str, importance: str = "normal") -> dict:
    now = datetime.now().isoformat()
    return {
        "id": str(uuid.uuid4())[:8],
        "content": content.strip(),
        "created_at": now,
        "last_accessed": now,
        "access_count": 1,
        "importance": importance,
        "tags": [],
    }


def _load_from_file() -> dict:
    """加载记忆文件，处理旧格式迁移"""
    # 优先加载新格式 JSON
    if os.path.exists(config.memory_file):
        try:
            with open(config.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") == 2 and "memories" in data:
                return data
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"memory.json 解析失败: {e}，尝试从旧格式恢复")

    # 从旧格式 memory.md 迁移
    if os.path.exists(config.memory_file_legacy):
        try:
            with open(config.memory_file_legacy, "r", encoding="utf-8") as f:
                text = f.read().strip()
            memories = []
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    memories.append(_new_memory(line[2:], "normal"))
                elif line and not line.startswith("#"):
                    memories.append(_new_memory(line, "normal"))
            if memories:
                logger.info(f"从 memory.md 迁移了 {len(memories)} 条记忆到 memory.json")
                data = {"version": 2, "memories": memories}
                _save_to_file(data)
                # 备份旧文件
                os.rename(config.memory_file_legacy, config.memory_file_legacy + ".legacy")
                return data
        except Exception as e:
            logger.error(f"从 memory.md 迁移失败: {e}")

    return {"version": 2, "memories": []}


def _save_to_file(data: dict):
    """保存记忆到文件，写入前备份"""
    if os.path.exists(config.memory_file):
        try:
            with open(config.memory_file, "r", encoding="utf-8") as f:
                old = f.read()
            with open(config.memory_file + ".bak", "w", encoding="utf-8") as f:
                f.write(old)
        except Exception:
            pass
    with open(config.memory_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ================== 检索记忆 ==================

def _score_memory(query: str, memory: dict) -> float:
    """
    计算记忆与查询的相关性得分。
    基于：关键词匹配数量 + 访问频率 + 重要性权重
    """
    content = memory["content"].lower()
    query_lower = query.lower()

    # 提取查询中的关键词（按空格和标点分割）
    keywords = re.findall(r'[\w\u4e00-\u9fff]+', query_lower)
    if not keywords:
        return 0.0

    # 关键词匹配得分
    match_score = 0.0
    for kw in keywords:
        if len(kw) >= 2 and kw in content:
            match_score += 1.0

    # 访问频率加成（对数缩放，避免高频记忆垄断）
    import math
    freq_bonus = math.log1p(memory.get("access_count", 1)) * 0.3

    # 重要性权重
    importance_weight = {"high": 1.5, "normal": 1.0, "low": 0.5}.get(memory.get("importance", "normal"), 1.0)

    return (match_score + freq_bonus) * importance_weight


def retrieve_memory(query: str, top_k: int = None) -> list:
    """
    基于关键词检索相关记忆，返回 top_k 条。
    同时更新被检索到记忆的 last_accessed 和 access_count。
    """
    if top_k is None:
        top_k = config.memory_retrieval_top_k

    data = _load_from_file()
    memories = data.get("memories", [])
    if not memories:
        return []

    # 计算得分并排序
    scored = [(m, _score_memory(query, m)) for m in memories]
    scored.sort(key=lambda x: x[1], reverse=True)

    # 只取得分 > 0 的（有相关性），最多 top_k 条
    relevant = [(m, s) for m, s in scored if s > 0][:top_k]

    # 更新访问时间
    now = datetime.now().isoformat()
    for m, _ in relevant:
        m["last_accessed"] = now
        m["access_count"] = m.get("access_count", 0) + 1

    if relevant:
        _save_to_file(data)
        logger.debug(f"检索到 {len(relevant)} 条相关记忆")

    return [m for m, _ in relevant]


def get_all_memory_text() -> str:
    """获取所有记忆的纯文本（用于更新记忆时传给模型）"""
    data = _load_from_file()
    lines = []
    for m in data.get("memories", []):
        imp = m.get("importance", "normal")
        prefix = "[重要] " if imp == "high" else ("[低] " if imp == "low" else "")
        lines.append(f"- {prefix}{m['content']}")
    return "\n".join(lines)


def build_system_prompt(query: str = "") -> str:
    """
    构建系统提示词，包含检索到的相关记忆。
    如果 query 为空，则返回所有记忆（用于首次启动）。
    """
    if query:
        relevant = retrieve_memory(query)
    else:
        data = _load_from_file()
        relevant = data.get("memories", [])[:config.memory_retrieval_top_k]

    if not relevant:
        return config.system_prompt

    memory_lines = []
    for m in relevant:
        imp = m.get("importance", "normal")
        prefix = "[重要] " if imp == "high" else ""
        memory_lines.append(f"- {prefix}{m['content']}")

    memory_text = "\n".join(memory_lines)
    return (
        f"{config.system_prompt}\n\n"
        f"以下是你在之前对话中积累的相关记忆，请在回答时参考：\n{memory_text}"
    )


# ================== 遗忘机制 ==================

def forget_memory() -> int:
    """
    遗忘长期未访问的低重要性记忆。
    - importance=low 且超过 forget_days_low 天未访问 → 删除
    - importance=normal 且超过 forget_days_normal 天未访问 → 降级为 low
    - importance=high → 永不自动删除

    返回被删除的记忆数量。
    """
    data = _load_from_file()
    memories = data.get("memories", [])
    if not memories:
        return 0

    now = datetime.now()
    removed = 0
    kept = []

    for m in memories:
        try:
            last_access = datetime.fromisoformat(m.get("last_accessed", now.isoformat()))
        except (ValueError, TypeError):
            last_access = now

        days_since_access = (now - last_access).days
        importance = m.get("importance", "normal")

        if importance == "low" and days_since_access > config.memory_forget_days_low:
            removed += 1
            logger.debug(f"遗忘记忆（{days_since_access}天未访问）: {m['content'][:50]}")
            continue

        if importance == "normal" and days_since_access > config.memory_forget_days_normal:
            m["importance"] = "low"
            logger.debug(f"记忆降级为low（{days_since_access}天未访问）: {m['content'][:50]}")

        kept.append(m)

    if removed > 0 or len(kept) != len(memories):
        data["memories"] = kept
        _save_to_file(data)
        logger.info(f"遗忘机制：删除 {removed} 条，当前共 {len(kept)} 条记忆")

    return removed


# ================== 压缩记忆 ==================

def compress_memory() -> bool:
    """
    当记忆数量超过阈值时，用 flash 模型压缩记忆。
    压缩策略：合并相似记忆、删除过时信息、精简冗余表述。
    压缩前自动备份，压缩后保留 high 重要性记忆。

    返回是否执行了压缩。
    """
    data = _load_from_file()
    memories = data.get("memories", [])

    if len(memories) < config.memory_compress_threshold:
        return False

    logger.info(f"记忆数量 {len(memories)} 超过阈值 {config.memory_compress_threshold}，开始压缩...")

    # 分离 high 重要性记忆（不参与压缩，直接保留）
    high_memories = [m for m in memories if m.get("importance") == "high"]
    normal_memories = [m for m in memories if m.get("importance") != "high"]

    if not normal_memories:
        logger.info("只有 high 重要性记忆，无需压缩")
        return False

    # 构建压缩 prompt
    memory_text = "\n".join(f"- {m['content']}" for m in normal_memories)
    prompt = (
        "以下是一组长期记忆，数量过多需要压缩。请执行以下操作：\n"
        "1. 合并内容相似或重复的记忆\n"
        "2. 删除已经过时或不再有价值的信息\n"
        "3. 精简冗长的表述，保留核心信息\n"
        "4. 对特别重要的记忆，在前面标注 [重要]\n\n"
        f"原始记忆（共{len(normal_memories)}条）：\n{memory_text}\n\n"
        "输出压缩后的记忆清单，每条一行，以 - 开头。只输出记忆内容本身。"
    )

    try:
        compressed_text = provider.chat_non_stream_request(
            model=config.model_summary,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=4096, thinking_disabled=True,
        )
    except Exception as e:
        logger.error(f"记忆压缩失败: {e}，保持原记忆不变")
        return False

    # 解析压缩结果
    new_memories = list(high_memories)  # high 记忆直接保留
    for line in compressed_text.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            content = line[2:].strip()
            importance = "high" if content.startswith("[重要]") else "normal"
            if importance == "high":
                content = content[4:].strip()
            if content:
                new_memories.append(_new_memory(content, importance))

    # 安全校验：压缩后记忆不应少于原始的 30%
    if len(new_memories) < len(memories) * 0.3:
        logger.warning(
            f"压缩后记忆({len(new_memories)}条)少于原始({len(memories)}条)的30%，"
            f"可能丢失信息，取消压缩"
        )
        return False

    data["memories"] = new_memories
    _save_to_file(data)
    logger.info(f"记忆压缩完成：{len(memories)} → {len(new_memories)} 条")
    return True


# ================== 更新记忆 ==================

def update_memory(conversation_text: str):
    """
    对话结束后，用 flash 模型从对话中提取新记忆，追加到记忆库。
    追加后自动触发遗忘和压缩检查。
    """
    existing_text = get_all_memory_text()

    if existing_text:
        prompt = (
            "以下是已有的长期记忆（必须全部保留，除非新对话明确否定了某条信息）：\n"
            f"{existing_text}\n\n"
            "以下是本次对话的内容：\n"
            f"{conversation_text}\n\n"
            "请更新长期记忆，严格遵守以下规则：\n"
            "1. 必须保留已有记忆中的所有信息点，一条都不能删除\n"
            "2. 从本次对话中提取新的值得长期记住的信息点（如用户偏好、事实、计划、问题、情绪状态等），添加到记忆中\n"
            "3. 只有当本次对话明确否定或纠正了某条已有记忆时，才更新或删除那条记忆\n"
            "4. 对特别重要的记忆（如用户身份、核心目标、关键偏好），在前面标注 [重要]\n"
            "5. 输出格式：每条记忆一行，以 - 开头\n"
            "6. 只输出记忆内容本身，不要输出解释、标题或多余文字"
        )
    else:
        prompt = (
            "以下是本次对话的内容：\n"
            f"{conversation_text}\n\n"
            "请提取其中值得长期记住的关键信息点（如用户偏好、事实、计划、问题、情绪状态等），整理成记忆清单。\n"
            "对特别重要的记忆（如用户身份、核心目标、关键偏好），在前面标注 [重要]。\n"
            "每条一行，以 - 开头。只输出记忆内容本身。"
        )

    logger.info("正在更新长期记忆...")

    try:
        new_memory_text = provider.chat_non_stream_request(
            model=config.model_summary,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=4096, thinking_disabled=True,
        ).strip()
    except Exception as e:
        logger.error(f"记忆更新失败: {e}，已有记忆保持不变")
        return

    # 解析新记忆
    data = _load_from_file()
    existing_contents = {m["content"].lower() for m in data["memories"]}
    added = 0

    for line in new_memory_text.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            content = line[2:].strip()
            importance = "high" if content.startswith("[重要]") else "normal"
            if importance == "high":
                content = content[4:].strip()
            if content and content.lower() not in existing_contents:
                data["memories"].append(_new_memory(content, importance))
                existing_contents.add(content.lower())
                added += 1

    _save_to_file(data)
    logger.info(f"长期记忆已更新：新增 {added} 条，当前共 {len(data['memories'])} 条")

    # 自动触发遗忘和压缩
    forget_memory()
    compress_memory()

    return data["memories"]


# ================== 启动时初始化 ==================

def init_memory() -> dict:
    """启动时加载记忆，执行一次遗忘检查"""
    data = _load_from_file()
    forget_memory()
    if data["memories"]:
        logger.info(f"长期记忆已加载：{len(data['memories'])} 条")
    return data
