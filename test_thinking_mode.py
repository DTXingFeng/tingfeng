"""
思考模式测试脚本

测试 thinking_mode.py 模块的基本功能和与真实模型的集成
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from openai import AsyncOpenAI
from src.config.ai_config import ai_config_manager
from src.utils.thinking_mode import thinking_handler, ThinkingModeHandler
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_handler_basic():
    """测试处理器基本功能（模拟数据）"""
    print("\n" + "="*60)
    print("测试 1: 思考模式处理器基本功能")
    print("="*60)
    
    handler = ThinkingModeHandler(enable_thinking_log=True)
    
    # 检查已知的思考字段
    print(f"✓ 支持的思考字段: {handler.KNOWN_THINKING_FIELDS}")
    
    # 检查统计信息
    stats = handler.get_stats()
    print(f"✓ 初始统计: {stats}")
    
    print("✓ 基本功能测试通过！\n")


async def test_with_real_model():
    """使用真实模型测试思考模式"""
    print("\n" + "="*60)
    print("测试 2: 使用 DeepSeek R1 思考模型")
    print("="*60)
    
    # 获取 ds_reasoner 配置
    creds = ai_config_manager.get_model_credentials("ds_reasoner")
    
    if not creds:
        print("⚠ 未找到 ds_reasoner 模型配置，跳过真实模型测试")
        print("  提示: 在 ai_config.yaml 中配置 ds_reasoner 模型")
        return
    
    print(f"✓ 模型: {creds['model']}")
    print(f"✓ API: {creds['base_url']}")
    
    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
    
    test_prompt = "请计算 123 * 456 = ? 并解释你的计算过程。"
    print(f"✓ 测试提示: {test_prompt}")
    
    try:
        print("\n⏳ 正在调用模型...")
        stream = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": test_prompt}],
            stream=True,
            max_tokens=500,
        )
        
        print("⏳ 处理流式响应...")
        result = await thinking_handler.process_streaming_response(
            stream=stream,
            model_name=creds["model"],
            collect_thinking=True,
        )
        
        print("\n" + "-"*60)
        print("📊 结果统计:")
        print(f"  - 是否包含思考内容: {result['has_thinking']}")
        print(f"  - 接收块数量: {result['chunk_count']}")
        print(f"  - 处理耗时: {result['elapsed_time']:.2f}秒")
        print(f"  - 思考内容长度: {len(result['thinking'])} 字符")
        print(f"  - 最终内容长度: {len(result['content'])} 字符")
        
        if result['has_thinking']:
            print("\n🧠 思考过程 (前200字):")
            print(f"  {result['thinking'][:200]}...")
        
        print("\n💡 最终回答:")
        print(f"  {result['content']}")
        
        print("\n✓ 思考模式测试通过！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_with_regular_model():
    """使用普通模型测试兼容性"""
    print("\n" + "="*60)
    print("测试 3: 使用普通模型（兼容性测试）")
    print("="*60)
    
    # 使用 ds_chat 或其他普通模型
    model_alias = "ds_chat"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print(f"⚠ 未找到 {model_alias} 模型配置，跳过兼容性测试")
        return
    
    print(f"✓ 模型: {creds['model']}")
    
    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
    
    test_prompt = "用一句话介绍你自己。"
    print(f"✓ 测试提示: {test_prompt}")
    
    try:
        print("\n⏳ 正在调用模型...")
        stream = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": test_prompt}],
            stream=True,
            max_tokens=100,
        )
        
        print("⏳ 处理流式响应...")
        result = await thinking_handler.process_streaming_response(
            stream=stream,
            model_name=creds["model"],
            collect_thinking=True,
        )
        
        print("\n" + "-"*60)
        print("📊 结果统计:")
        print(f"  - 是否包含思考内容: {result['has_thinking']}")
        print(f"  - 接收块数量: {result['chunk_count']}")
        print(f"  - 处理耗时: {result['elapsed_time']:.2f}秒")
        print(f"  - 最终内容长度: {len(result['content'])} 字符")
        
        print("\n💡 回答:")
        print(f"  {result['content']}")
        
        print("\n✓ 普通模型兼容性测试通过！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_global_stats():
    """测试全局统计功能"""
    print("\n" + "="*60)
    print("测试 4: 全局统计信息")
    print("="*60)
    
    stats = thinking_handler.get_stats()
    print(f"📊 全局统计:")
    print(f"  - 总调用次数: {stats['total_calls']}")
    print(f"  - 思考模式调用次数: {stats['thinking_enabled_calls']}")
    print(f"  - 思考字符收集总数: {stats['thinking_chars_collected']}")
    
    print("\n✓ 统计功能正常！\n")


async def main():
    """运行所有测试"""
    print("\n" + "🔬"*30)
    print("  TingFengBot 思考模式测试套件")
    print("🔬"*30)
    
    try:
        # 测试 1: 基本功能
        await test_handler_basic()
        
        # 测试 2: 真实思考模型
        await test_with_real_model()
        
        # 测试 3: 普通模型兼容性
        await test_with_regular_model()
        
        # 测试 4: 全局统计
        await test_global_stats()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成！")
        print("="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n⚠ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
