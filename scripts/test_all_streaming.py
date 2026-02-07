"""
全面测试所有流式传输功能
"""
import asyncio
import sys
from pathlib import Path

root_path = Path(__file__).parent.parent.absolute()
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from src.aimodel.decision.decide import should_i_reply
from src.aimodel.reply.personality import PersonalityManager
from src.aimodel.reply.chat import get_chat_reply
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

personality_manager = PersonalityManager()


async def test_decision_engine():
    """测试决策引擎的流式传输"""
    print("\n" + "="*60)
    print("测试 1: 决策引擎流式传输")
    print("="*60)
    
    try:
        # 使用测试群组
        test_group_id = 123456
        test_user = "测试用户"
        test_message = "你好呀"
        
        print(f"输入: 用户={test_user}, 消息={test_message}")
        print("调用决策引擎...")
        
        result = await should_i_reply(
            group_id=test_group_id,
            user_name=test_user,
            current_msg=test_message,
            is_at_me=True,
            user_id=999
        )
        
        print(f"\n✅ 决策引擎流式传输成功！")
        print(f"📊 结果:")
        print(f"  - 是否回复: {result.get('should_reply')}")
        print(f"  - 回复对象: {result.get('reply_to_user')}")
        print(f"  - 兴趣评分: {result.get('interest_score')}")
        print(f"  - 心情影响: {result.get('mood_impact')}")
        print(f"  - 是否回复bot: {result.get('is_replying_to_bot')}")
        
        return True
    except Exception as e:
        print(f"\n❌ 决策引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_personality_thoughts():
    """测试内心独白生成的流式传输"""
    print("\n" + "="*60)
    print("测试 2: 内心独白生成流式传输")
    print("="*60)
    
    try:
        test_group_id = 123456
        test_user = "测试用户"
        test_message = "今天天气真好"
        history = [
            f"{test_user}: 今天天气真好",
            "self: 是啊，很适合出门",
        ]
        mood_value = 70
        
        print(f"输入: 用户={test_user}, 消息={test_message}, 心情={mood_value}")
        print("生成内心独白...")
        
        thoughts = await personality_manager.generate_thoughts(
            group_id=test_group_id,
            user_name=test_user,
            current_msg=test_message,
            history=history,
            mood_value=mood_value
        )
        
        print(f"\n✅ 内心独白流式传输成功！")
        print(f"💭 生成的独白: {thoughts}")
        
        return True
    except Exception as e:
        print(f"\n❌ 内心独白测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_personality_vibe():
    """测试群氛围更新的流式传输"""
    print("\n" + "="*60)
    print("测试 3: 群氛围更新流式传输")
    print("="*60)
    
    try:
        test_group_id = 123456
        
        # 创建一些模拟历史记录
        history = [
            "用户A: 大家好啊",
            "用户B: 哈哈，笑死我了",
            "用户C: 捏，今天的天气真好捏",
            "用户D: 这也太赢了吧",
            "用户A: 确实确实",
        ]
        
        # 先保存历史记录
        for msg in history:
            await db_manager.add_chat_log(test_group_id, msg)
        
        print(f"群组: {test_group_id}")
        print("分析群氛围...")
        
        await personality_manager.update_group_vibe(test_group_id)
        
        # 获取更新后的状态
        state = await db_manager.get_personality_state(test_group_id)
        vibe_data = state.get("style_vibe", "{}")
        
        import json
        if isinstance(vibe_data, str):
            try:
                vibe_data = json.loads(vibe_data)
            except:
                vibe_data = {"vibe": "解析失败"}
        
        print(f"\n✅ 群氛围更新流式传输成功！")
        print(f"🎭 群氛围: {vibe_data.get('vibe', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"\n❌ 群氛围更新测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_style_capture():
    """测试风格捕捉的流式传输"""
    print("\n" + "="*60)
    print("测试 4: 风格捕捉流式传输")
    print("="*60)
    
    try:
        test_group_id = 123456
        
        history = [
            "用户A: 被夸奖了",
            "用户B: 哎呀，你这么说人家都不好意思了~",
            "用户C: 哈哈，太可爱了",
            "用户A: 讨论二次元",
            "用户B: 这部番真的是绝绝子，太好看了吧！",
            "用户C: 确实确实，我也很喜欢",
        ]
        
        print(f"群组: {test_group_id}")
        print("捕捉风格模式...")
        
        await personality_manager.capture_style_patterns(test_group_id, history)
        
        print(f"\n✅ 风格捕捉流式传输成功！")
        print("📝 已识别并存储风格模式")
        
        return True
    except Exception as e:
        print(f"\n❌ 风格捕捉测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_slang_mining():
    """测试黑话挖掘的流式传输"""
    print("\n" + "="*60)
    print("测试 5: 黑话挖掘流式传输")
    print("="*60)
    
    try:
        test_group_id = 123456
        
        history = [
            "用户A: 这游戏真的依托构思",
            "用户B: 哈哈，确实是一坨狗屎",
            "用户C: 那个DRG你玩过吗",
            "用户A: DRG？深岩银河啊，当然玩过",
            "用户B: 这游戏真的爆金币",
            "用户C: 确实确实，爆金币爆爆爆",
        ]
        
        print(f"群组: {test_group_id}")
        print("挖掘黑话...")
        
        await personality_manager.mine_slang(test_group_id, history)
        
        print(f"\n✅ 黑话挖掘流式传输成功！")
        print("🔤 已识别并存储黑话候选")
        
        return True
    except Exception as e:
        print(f"\n❌ 黑话挖掘测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_chat_reply():
    """测试聊天回复的流式传输"""
    print("\n" + "="*60)
    print("测试 6: 聊天回复生成流式传输")
    print("="*60)
    
    try:
        test_group_id = 123456
        test_user = "测试用户"
        test_message = "你好，能聊聊天吗？"
        
        # 添加一些历史记录
        await db_manager.add_chat_log(test_group_id, f"{test_user}: {test_message}")
        
        print(f"输入: 用户={test_user}, 消息={test_message}")
        print("生成回复...")
        
        import time
        start_time = time.time()
        
        result = await get_chat_reply(
            group_id=test_group_id,
            user_name=test_user,
            current_msg=test_message,
            user_id=999
        )
        
        elapsed = time.time() - start_time
        
        reply_text = result.get("text", "")
        sticker = result.get("sticker")
        
        print(f"\n✅ 聊天回复流式传输成功！")
        print(f"⏱️  耗时: {elapsed:.2f} 秒")
        print(f"💬 回复内容: {reply_text[:100]}{'...' if len(reply_text) > 100 else ''}")
        if sticker:
            print(f"🖼️  表情包: {sticker[:50]}...")
        
        if elapsed > 30:
            print("⚠️  耗时超过30秒，旧非流式API会超时")
        
        return True
    except Exception as e:
        print(f"\n❌ 聊天回复测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_long_generation():
    """测试长文本生成的超时抵抗"""
    print("\n" + "="*60)
    print("测试 7: 长文本生成超时抵抗")
    print("="*60)
    
    try:
        test_group_id = 123456
        test_user = "测试用户"
        test_message = "请详细介绍Python异步编程的特点、优势、使用场景和最佳实践，包括asyncio库的使用方法、协程的概念、事件循环机制等"
        
        await db_manager.add_chat_log(test_group_id, f"{test_user}: {test_message}")
        
        print(f"输入: 用户={test_user}")
        print(f"消息: {test_message[:50]}...")
        print("生成长回复...")
        
        import time
        start_time = time.time()
        
        result = await get_chat_reply(
            group_id=test_group_id,
            user_name=test_user,
            current_msg=test_message,
            user_id=999
        )
        
        elapsed = time.time() - start_time
        
        reply_text = result.get("text", "")
        
        print(f"\n✅ 长文本生成流式传输成功！")
        print(f"⏱️  总耗时: {elapsed:.2f} 秒")
        print(f"📝 回复长度: {len(reply_text)} 字符")
        print(f"📄 内容预览: {reply_text[:150]}...")
        
        if elapsed > 30:
            print("⚠️  耗时超过30秒，旧非流式API会超时")
        
        return True
    except Exception as e:
        print(f"\n❌ 长文本生成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("🚀 开始全面测试所有流式传输功能")
    print("="*60)
    
    results = []
    
    # 依次运行所有测试
    results.append(("决策引擎", await test_decision_engine()))
    results.append(("内心独白", await test_personality_thoughts()))
    results.append(("群氛围更新", await test_personality_vibe()))
    results.append(("风格捕捉", await test_style_capture()))
    results.append(("黑话挖掘", await test_slang_mining()))
    results.append(("聊天回复", await test_chat_reply()))
    results.append(("长文本生成", await test_long_generation()))
    
    # 输出测试结果汇总
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    print("\n" + "="*60)
    print(f"总计: {passed}/{total} 测试通过")
    print("="*60)
    
    if passed == total:
        print("\n🎉 所有测试通过！所有流式传输功能正常！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
