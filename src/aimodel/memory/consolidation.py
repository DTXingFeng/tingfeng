from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.utils.context_manager import context_manager
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors, retry_on_failure, DatabaseError
from src.utils.performance_monitor import monitor_performance, ConcurrencyLimiter
from src.utils.thinking_mode import thinking_handler
from typing import List, Set

logger = get_logger(__name__)

active_consolidation_groups: Set[int] = set()

consolidation_limiter = ConcurrencyLimiter(max_concurrent=3)


@monitor_performance("consolidate_memories")
async def consolidate_memories(group_id: int):
    """
    将群组中未处理的聊天记录总结为长期事实并存入向量库
    """
    if group_id in active_consolidation_groups:
        return

    async with consolidation_limiter:
        try:
            active_consolidation_groups.add(group_id)

            # 1. 获取未处理的消息 (为了保证总结质量，建议攒够 50 条再处理，单次最多处理 100 条)
            raw_logs = await db_manager.get_unprocessed_logs(group_id, limit=100)
            if len(raw_logs) < 50:
                return

            msg_ids = [row[0] for row in raw_logs]
            chat_content = "\n".join([row[1] for row in raw_logs])

            # 2. 调用 LLM 进行总结提取
            model_alias = ai_config.consolidation_model
            if not model_alias:
                model_alias = ai_config.reply_model

            creds = ai_config_manager.get_model_credentials(model_alias)
            if not creds:
                return

            client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=60.0)

            prompt = (
                f"你现在是'{bot_config.bot_name}'的深度记忆固化模块。你的任务是从最近的群聊记录中提取具有长期社交价值的'记忆碎片'。\n\n"
                "### 提取准则：\n"
                "1. **记忆碎片化**：将复杂的对话拆解为独立、简洁的陈述句。每条记忆应包含'主体'和'行为/状态'。\n"
                "2. **社交价值优先**：关注用户的偏好、职业、所在地、重要经历、对特定事物的看法、以及与你的互动细节。\n"
                "3. **剔除冗余**：过滤掉无意义的打招呼、纯表情包交流、时效性极短的信息（如'我下楼买个烟'）。\n"
                "4. **客观与主观并存**：既记录客观事实（他在北京），也记录主观态度（他讨厌加班）。\n\n"
                "### 任务 1：提取记忆碎片 (Memory Shards)\n"
                "这些碎片将被存入向量数据库，用于后续的语义检索。请确保描述具有代表性，即使未来的提问词不完全一致，也能通过含义关联到。\n"
                "格式：'SHARD|内容'。例如：'SHARD|刑风最近在研究神经网络，由于模型训练失败显得很暴躁'。\n\n"
                "### 任务 2：更新用户画像 (User Profile)\n"
                "更新你对参与者的整体刻板印象。要求极度精炼，包含身份标签和性格特征。\n"
                "格式：'PROFILE|用户名|标签A,标签B,性格描述'。\n\n"
                "### 任务 3：提取用户专属往事 (User Stories)\n"
                "提取关于某个用户的特定、具体的关键事件或属性。\n"
                "格式：'STORY|用户名|事件描述'。\n\n"
                "### 任务 4：提取知识三元组 (Knowledge Triplets)\n"
                "提取具有客观价值或长期逻辑关联的结构化知识。\n"
                "格式：'TRIPLET|主体|关系|客体|置信度'。置信度范围 0.0-1.0。\n"
                "例如：'TRIPLET|刑风|喜欢|猫咪|0.95'。\n\n"
                "### 任务 5：情绪标记 (EMO)\n"
                "分析群聊氛围的情绪倾向，输出一个整数，范围 -10（极度负面）到 +10（极度正面）。\n"
                "格式：'EMO|情绪值'。例如：'EMO|3'。\n\n"
                "### 限制：\n"
                "- 只输出上述格式的内容，每行一条。\n"
                "- 如果没有提取到任何有价值的信息，只输出一个字：无。\n"
                "- 不要输出任何解释、问候或总结。"
            )

            # 合并历史消息，但截断以避免超过 token 限制
            max_chat_length = 3000
            chat_content = chat_content[-max_chat_length:]

            optimized_prompt = prompt + f"\n\n### 聊天记录：\n{chat_content}\n\n### 提取结果："

            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "user", "content": optimized_prompt}],
                temperature=0.3,
            )

            # 使用思考模式处理器处理响应
            response_result = thinking_handler.process_non_streaming_response(response)
            output = response_result["content"]

            if response_result["has_thinking"]:
                logger.info(f"记忆固化使用思考模式: 推理长度={len(response_result['thinking'])}")

            if output == "无" or not output:
                await db_manager.mark_as_processed(msg_ids)
                return

            # 3. 解析并存入
            lines = [line.strip("- ").strip() for line in output.split("\n") if line.strip()]
            shards = []
            mood_adjustment = 0
            for line in lines:
                if line.startswith("PROFILE|"):
                    parts = line.split("|")
                    if len(parts) >= 3:
                        u_name, u_profile = parts[1].strip(), parts[2].strip()
                        # 尝试获取 user_id
                        u_id = await db_manager.get_user_id_by_name(group_id, u_name)
                        if u_id:
                            await db_manager.update_user_impression(group_id, u_id, u_name, u_profile)
                elif line.startswith("STORY|"):
                    parts = line.split("|")
                    if len(parts) >= 3:
                        u_name, u_story = parts[1].strip(), parts[2].strip()
                        # 尝试获取 user_id
                        u_id = await db_manager.get_user_id_by_name(group_id, u_name)
                        if u_id:
                            await db_manager.add_user_specific_memory(group_id, u_id, u_name, u_story)
                elif line.startswith("TRIPLET|"):
                    parts = line.split("|")
                    if len(parts) >= 5:
                        sub, pred, obj = parts[1].strip(), parts[2].strip(), parts[3].strip()
                        try:
                            conf = float(parts[4].strip())
                            await db_manager.add_knowledge_triplet(group_id, sub, pred, obj, conf)
                        except:
                            await db_manager.add_knowledge_triplet(group_id, sub, pred, obj)
                elif line.startswith("EMO|"):
                    parts = line.split("|")
                    if len(parts) >= 2:
                        try:
                            mood_adjustment = int(parts[1].strip())
                        except:
                            pass
                elif line.startswith("SHARD|"):
                    content = line[6:].strip()
                    if len(content) > 5:
                        shards.append(content)
                else:
                    if "|" not in line and len(line) > 5:
                        shards.append(line)

            # 应用氛围调整
            if mood_adjustment != 0:
                await db_manager.update_mood(group_id, mood_adjustment)

            if shards:
                vectors = await get_embeddings(shards)
                for i, shard in enumerate(shards):
                    await vector_db.add_memory(
                        group_id=group_id,
                        text=f"[碎片] {shard}",
                        vector=vectors[i],
                        metadata={"type": "shard"},
                    )

                logger.info(f"群 {group_id} 记忆固化完成：提取了 {len(shards)} 条碎片")

            # 4. 标记这些原始消息为已处理
            await db_manager.mark_as_processed(msg_ids)

        except Exception as e:
            logger.opt(exception=True).error("记忆固化失败 (群 {}): {}", group_id, e)
        finally:
            active_consolidation_groups.discard(group_id)
