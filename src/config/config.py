import yaml
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional, List

class BotConfig(BaseModel):
    bot_name: str = "听风"
    bot_qq: str = "391459725"
    creator_id: Optional[int] = None # 创造者的 QQ 号
    creator_name: str = "刑风" # 创造者的名字
    identity: str = "你是一个性格温和、有些害羞的二次元少女，名字叫听风。你喜欢和大家聊天，但说话比较委婉。"
    prompt: str = "请以听风的身份进行回复。保持角色设定，不要提及你是AI。"
    reply_rate: float = 0.0  # 默认 0.0，强制艾特才回复
    enable_mood: bool = True # 是否启用心情系统
    decision_interval: int = 60 # 决策间隔时间（秒）
    allowed_groups: List[int] = Field(default_factory=list) # 白名单
    blocked_groups: List[int] = Field(default_factory=list) # 黑名单

    class Config:
        arbitrary_types_allowed = True

class ConfigManager:
    _instance = None
    _config: Optional[BotConfig] = None
    _config_path = Path("config.yaml")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def load_config(cls) -> BotConfig:
        if not cls._config_path.exists():
            # Create default config if not exists
            default_config = BotConfig()
            cls.save_config(default_config)
            cls._config = default_config
        else:
            try:
                with open(cls._config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    cls._config = BotConfig(**data)
            except Exception as e:
                print(f"Error loading config: {e}")
                cls._config = BotConfig()
        return cls._config

    @classmethod
    def save_config(cls, config: BotConfig):
        with open(cls._config_path, "w", encoding="utf-8") as f:
            yaml.dump(config.model_dump(), f, allow_unicode=True, sort_keys=False)

    @property
    def config(self) -> BotConfig:
        if self._config is None:
            self.load_config()
        return self._config

# Global instance
config_manager = ConfigManager()
bot_config = config_manager.config
