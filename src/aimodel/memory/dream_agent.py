import asyncio
import json
from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.context_manager import context_manager
from src.utils.db_manager import db_manager
from src.utils.openai_compat import openai_compat
from src.utils.thinking_mode import thinking_handler
from nonebot import logger


async def dream_and_optimize(group_id: int):
    """
    梦境代理 (Dream Agent)：后台自主演化与优化记忆。
    """
    logger.info(f"群 {group_id} 的梦境代理启动，正在复盘记忆...")

    triplets = await db_manager.get_knowledge_triplets(group_id, limit=100)
    patterns = await db_manager.get_style_patterns(group_id, limit=50)

    if not triplets and not patterns:
        logger.debug(f"群 {group_id} 没有需要优化的记忆，跳过梦境处理")
        return

    model_alias = ai_config.dream_agent_model or ai_config.reply_model
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        logger.warning(f"无法获取梦境代理模型凭据，跳过群 {group_id} 的梦境处理")
        return
    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=60.0)

    triplet_str = "\n".join([f"- {t['subject']} --({t['predicate']})--> {t['object']}" for t in triplets])
    pattern_str = "\n".join(
        [f"- 情境: {p['context']} | 风格: {p['style_desc']} (权重: {p['weight']})" for p in patterns]
    )

    dream_prompt = f"""
你现在是 {bot_config.bot_name} 的"梦境代理"。你的任务是在后台复盘并优化已有的记忆结构。

### 现有知识图谱 (三元组)：
{triplet_str}

### 现有风格模式：
{pattern_str}

### 任务要求：
1. **合并与去重**：发现表达同一事实但描述略有不同的三元组，建议合并。
2. **精炼风格**：检查风格模式，如果多个模式相似，建议合并并保留核心特征。
3. **清理噪声**：识别出毫无意义或时效性已过的错误记忆，建议删除。

### 输出格式 (JSON)：
{{
  "merges": [
    {{"type": "style_pattern", "old": [{{"context": "A", "style_desc": "B"}}, {{"context": "C", "style_desc": "D"}}], "new": {{"context": "合并后情境", "style_desc": "合并后描述"}}}}
  ],
  "deletes": [
    {{"type": "triplet", "subject": "主体", "predicate": "关系", "object": "客体"}},
    {{"type": "style_pattern", "context": "情境", "style_desc": "描述"}}
  ]
}}

注意：
- merges 只支持 style_pattern 类型的合并
- deletes 支持 triplet 和 style_pattern 两种类型
- 如果没有需要优化的内容，输出空 JSON: {{"merges": [], "deletes": []}}
"""
    try:
        optimized_prompt, prompt_tokens = context_manager.truncate_text(
            text=dream_prompt, model_alias=model_alias, max_output_tokens=1000
        )

        # 使用兼容性工具自动处理 response_format
        response = await openai_compat.create_with_auto_fallback(
            client=client,
            model=creds["model"],
            messages=[{"role": "system", "content": optimized_prompt}],
            base_url=creds["base_url"],
            use_response_format=True,
            stream=False,
            max_tokens=1000,
            temperature=0.4,
        )

        # 使用思考模式处理器处理响应
        response_result = thinking_handler.process_non_streaming_response(response)
        result_text = response_result["content"]

        if response_result["has_thinking"]:
            logger.info(f"梦境代理使用思考模式: 推理长度={len(response_result['thinking'])}")

        try:
            optimization_result = json.loads(result_text)
        except json.JSONDecodeError:
            logger.warning(f"群 {group_id} 梦境代理返回了无效的 JSON，跳过执行")
            return

        merges = optimization_result.get("merges", [])
        deletes = optimization_result.get("deletes", [])

        merge_count = 0
        delete_count = 0

        for merge_item in merges:
            if merge_item.get("type") == "style_pattern":
                old_patterns = merge_item.get("old", [])
                new_pattern = merge_item.get("new", {})
                if old_patterns and new_pattern:
                    success = await db_manager.merge_style_patterns(
                        group_id=group_id,
                        old_patterns=old_patterns,
                        new_context=new_pattern.get("context", ""),
                        new_style_desc=new_pattern.get("style_desc", ""),
                    )
                    if success:
                        merge_count += 1

        for delete_item in deletes:
            if delete_item.get("type") == "triplet":
                deleted = await db_manager.delete_knowledge_triplet(
                    group_id=group_id,
                    subject=delete_item.get("subject"),
                    predicate=delete_item.get("predicate"),
                    obj=delete_item.get("object"),
                )
                delete_count += deleted
            elif delete_item.get("type") == "style_pattern":
                deleted = await db_manager.delete_style_pattern(
                    group_id=group_id, context=delete_item.get("context"), style_desc=delete_item.get("style_desc")
                )
                delete_count += deleted

        logger.info(f"群 {group_id} 梦境复盘完成: 合并 {merge_count} 项，删除 {delete_count} 项")

    except Exception as e:
        logger.opt(exception=True).error("梦境代理运行失败 (群 {}): {}", group_id, e)


async def start_dream_cycle():
    """
    定期启动梦境周期。
    """
    while True:
        await asyncio.sleep(3600 * 6)  # 每 6 小时梦境一次
        groups = await db_manager.get_all_groups()
        for group_id in groups:
            await dream_and_optimize(group_id)
