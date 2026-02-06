import asyncio
from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.context_manager import context_manager
from src.utils.db_manager import db_manager
from nonebot import logger


async def dream_and_optimize(group_id: int):
    """
    梦境代理 (Dream Agent)：后台自主演化与优化记忆。
    """
    logger.info(f"群 {group_id} 的梦境代理启动，正在复盘记忆...")

    # 1. 获取需要优化的数据 (三元组和风格模式)
    triplets = await db_manager.get_knowledge_triplets(group_id, limit=100)
    patterns = await db_manager.get_style_patterns(group_id, limit=50)

    if not triplets and not patterns:
        return

    model_alias = ai_config.dream_agent_model or ai_config.reply_model
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return
    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=60.0)

    # 构造复盘数据摘要
    triplet_str = "\n".join([f"- {t['subject']} --({t['predicate']})--> {t['object']}" for t in triplets])
    pattern_str = "\n".join(
        [f"- 情境: {p['context']} | 风格: {p['style_desc']} (权重: {p['weight']})" for p in patterns]
    )

    dream_prompt = f"""
你现在是 {bot_config.bot_name} 的“梦境代理”。你的任务是在后台复盘并优化已有的记忆结构。

### 现有知识图谱 (三元组)：
{triplet_str}

### 现有风格模式：
{pattern_str}

### 任务要求：
1. **合并与去重**：发现表达同一事实但描述略有不同的三元组，建议合并。
2. **精炼风格**：检查风格模式，如果多个模式相似，建议合并并保留核心特征。
3. **清理噪声**：识别出毫无意义或时效性已过的错误记忆，建议删除。

请输出 JSON 格式的操作指令：
{{
  "merges": [ {{"type": "triplet", "old": ["A", "B"], "new": "C"}}, ... ],
  "deletes": [ {{"type": "pattern", "content": "..."}}, ... ]
}}
"""
    try:
        optimized_prompt, prompt_tokens = context_manager.truncate_text(
            text=dream_prompt, model_alias=model_alias, max_output_tokens=1000
        )

        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "system", "content": optimized_prompt}],
            max_tokens=1000,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        # 注意：这里仅实现逻辑框架，实际的数据库批量删除/更新操作需要根据 JSON 结果执行
        # 为保持 Demo 简洁，这里先记录日志
        logger.info(f"群 {group_id} 梦境复盘完成，已生成优化建议。")

    except Exception as e:
        logger.error(f"梦境代理运行失败: {e}")


async def start_dream_cycle():
    """
    定期启动梦境周期。
    """
    while True:
        await asyncio.sleep(3600 * 6)  # 每 6 小时梦境一次
        groups = await db_manager.get_all_groups()
        for group_id in groups:
            await dream_and_optimize(group_id)
