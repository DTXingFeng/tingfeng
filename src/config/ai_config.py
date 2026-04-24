from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Optional, List, Any
import yaml
from pathlib import Path


class PlatformConfig(BaseModel):
    base_url: str
    api_key: str
    description: Optional[str] = ""


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    platform_alias: str
    model: str
    description: Optional[str] = ""
    max_context_tokens: int = 4096
    enable_thinking: Optional[bool] = None


class AIConfig(BaseModel):
    platforms: Dict[str, PlatformConfig] = {}
    models: Dict[str, ModelConfig] = {}

    # 功能绑定配置
    reply_model: str = ""  # 回复功能使用的模型别名
    decision_model: str = ""  # 决策功能使用的模型别名
    memory_model: str = ""  # 嵌入模型使用的别名
    consolidation_model: str = ""  # 记忆固化/总结使用的模型别名
    image_model: str = ""  # 图像识别使用的模型别名

    # 人格相关功能绑定
    inner_voice_model: str = ""  # 内心独白模型
    style_mimic_model: str = ""  # 风格模仿模型
    slang_mining_model: str = ""  # 黑话挖掘模型
    personality_refine_model: str = ""  # 人格精炼模型
    mute_reflection_model: str = ""  # 禁言反思模型

    # 记忆相关功能绑定
    dream_agent_model: str = ""  # 梦境代理模型
    memory_search_model: str = ""  # 记忆搜索嵌入模型

    # 对话相关功能绑定
    context_summary_model: str = ""  # 上下文总结模型


class AIConfigManager:
    _instance = None
    _config: Optional[AIConfig] = None
    _config_path = Path("ai_config.yaml")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIConfigManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def load_config(cls) -> AIConfig:
        if not cls._config_path.exists():
            # Create default config if not exists
            default_config = AIConfig(
                platforms={
                    "siliconflow": PlatformConfig(
                        base_url="https://api.siliconflow.cn/v1", api_key="sk-xxxxxx", description="SiliconFlow API"
                    )
                },
                models={
                    "qwen_7b": ModelConfig(
                        platform_alias="siliconflow",
                        model="Qwen/Qwen2.5-7B-Instruct",
                        description="Qwen 7B Instruct",
                    ),
                    "qwen_72b": ModelConfig(
                        platform_alias="siliconflow",
                        model="Qwen/Qwen2.5-72B-Instruct",
                        description="Qwen 72B Instruct",
                    ),
                    "qwen_vl": ModelConfig(
                        platform_alias="siliconflow",
                        model="Qwen/Qwen2-VL-72B-Instruct",
                        description="Qwen2-VL 72B",
                    ),
                    "bge_m3": ModelConfig(
                        platform_alias="siliconflow", model="BAAI/bge-m3", description="BGE-M3 Embedding"
                    ),
                },
                reply_model="qwen_72b",
                decision_model="qwen_7b",
                memory_model="bge_m3",
                consolidation_model="qwen_7b",
                image_model="qwen_vl",
                # 人格相关功能绑定
                inner_voice_model="qwen_7b",
                style_mimic_model="qwen_7b",
                slang_mining_model="qwen_7b",
                personality_refine_model="qwen_7b",
                # 记忆相关功能绑定
                dream_agent_model="qwen_7b",
                memory_search_model="bge_m3",
                # 对话相关功能绑定
                context_summary_model="qwen_7b",
            )
            cls.save_config(default_config)
            cls._config = default_config
        else:
            try:
                with open(cls._config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    cls._config = AIConfig(**data)
            except Exception as e:
                print(f"Error loading AI config: {e}")
                cls._config = AIConfig()
        return cls._config

    @classmethod
    def save_config(cls, config: AIConfig):
        with open(cls._config_path, "w", encoding="utf-8") as f:
            yaml.dump(config.model_dump(), f, allow_unicode=True, sort_keys=False)

    @property
    def config(self) -> AIConfig:
        if self._config is None:
            self.load_config()
        return self._config

    def get_model_credentials(self, model_alias: str) -> Optional[Dict[str, any]]:
        """
        根据模型别名获取完整的调用凭证 (base_url, api_key, model, enable_thinking)
        额外字段（如 thinking）也会被包含在返回值中，供 API 调用使用
        """
        config = self.config
        if model_alias not in config.models:
            return None

        model_cfg = config.models[model_alias]
        if model_cfg.platform_alias not in config.platforms:
            return None

        platform_cfg = config.platforms[model_cfg.platform_alias]

        # 获取模型配置的所有字段
        model_dict = model_cfg.model_dump()
        
        # 提取已知字段构建凭证
        credentials = {
            "base_url": platform_cfg.base_url,
            "api_key": platform_cfg.api_key,
            "model": model_dict.get("model"),
        }
        
        # 保留额外字段（如 thinking），这些会被传递到 API 请求中
        extra_fields = ["platform_alias", "description", "max_context_tokens", "enable_thinking"]
        for key, value in model_dict.items():
            if key not in extra_fields and value is not None:
                credentials[key] = value
        
        return credentials


# Global instance
ai_config_manager = AIConfigManager()
ai_config = ai_config_manager.config
