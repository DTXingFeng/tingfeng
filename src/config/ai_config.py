from pydantic import BaseModel
from typing import Dict, Optional, List
import yaml
from pathlib import Path

class PlatformConfig(BaseModel):
    base_url: str
    api_key: str
    description: Optional[str] = ""

class ModelConfig(BaseModel):
    platform_alias: str
    model_name: str
    description: Optional[str] = ""

class AIConfig(BaseModel):
    platforms: Dict[str, PlatformConfig] = {}
    models: Dict[str, ModelConfig] = {}
    
    # 功能绑定配置
    reply_model: str = ""         # 回复功能使用的模型别名
    decision_model: str = ""      # 决策功能使用的模型别名
    memory_model: str = ""        # 嵌入模型使用的别名
    consolidation_model: str = "" # 记忆固化/总结使用的模型别名
    image_model: str = ""         # 图像识别使用的模型别名

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
                        base_url="https://api.siliconflow.cn/v1",
                        api_key="sk-xxxxxx",
                        description="SiliconFlow API"
                    )
                },
                models={
                    "qwen_7b": ModelConfig(
                        platform_alias="siliconflow",
                        model_name="Qwen/Qwen2.5-7B-Instruct",
                        description="Qwen 7B Instruct"
                    ),
                    "qwen_72b": ModelConfig(
                        platform_alias="siliconflow",
                        model_name="Qwen/Qwen2.5-72B-Instruct",
                        description="Qwen 72B Instruct"
                    ),
                    "qwen_vl": ModelConfig(
                        platform_alias="siliconflow",
                        model_name="Qwen/Qwen2-VL-72B-Instruct",
                        description="Qwen2-VL 72B"
                    ),
                    "bge_m3": ModelConfig(
                        platform_alias="siliconflow",
                        model_name="BAAI/bge-m3",
                        description="BGE-M3 Embedding"
                    )
                },
                reply_model="qwen_72b",
                decision_model="qwen_7b",
                memory_model="bge_m3",
                consolidation_model="qwen_7b",
                image_model="qwen_vl"
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

    def get_model_credentials(self, model_alias: str) -> Optional[Dict[str, str]]:
        """
        根据模型别名获取完整的调用凭证 (base_url, api_key, model_name)
        """
        config = self.config
        if model_alias not in config.models:
            return None
        
        model_cfg = config.models[model_alias]
        if model_cfg.platform_alias not in config.platforms:
            return None
            
        platform_cfg = config.platforms[model_cfg.platform_alias]
        
        return {
            "base_url": platform_cfg.base_url,
            "api_key": platform_cfg.api_key,
            "model": model_cfg.model_name
        }

# Global instance
ai_config_manager = AIConfigManager()
ai_config = ai_config_manager.config
