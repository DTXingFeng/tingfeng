import yaml
from pathlib import Path


class Config:
    _instance = None
    _loaded = False
    _data: dict = {}
    
    @classmethod
    def load(cls, config_path: str = "ai_config.yaml"):
        if cls._loaded:
            return cls._instance or cls()
        
        path = Path(config_path)
        if not path.exists():
            # 如果配置文件不存在，创建一个空文件
            path.touch()
            # 写入默认配置
        
        with open(path, 'r', encoding='utf-8') as f:
            cls._data = yaml.safe_load(f) or {}
        
        cls._loaded = True
        cls._instance = cls()
        return cls._instance
    
    @classmethod
    def get(cls, key: str, default=None):
        if not cls._loaded:
            cls.load()
        
        keys = key.split('.')
        value = cls._data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value

    @classmethod
    # 获取模型的基础配置信息（不包含平台特定配置）
    def get_body_info(cls, model_name: str) -> dict:
        if not cls._loaded:
            cls.load()

        model_info = cls._data.get("models", {}).get(model_name, {})
        
        exclude_keys = {'platform_alias', 'description', 'max_context_tokens'}
        return {k: v for k, v in model_info.items() if k not in exclude_keys}
        
    @classmethod
    # 获取模型在不同平台的配置信息
    def get_platforms_info(cls,model_name: str) -> dict:
        if not cls._loaded:
            cls.load()
        
        model_info = cls._data.get("models", {}).get(model_name, {})
        platform_alias = model_info.get("platform_alias")
        
        if not platform_alias:
            return {}
        
        platform_config = cls._data.get("platforms", {}).get(platform_alias, {})
        
        exclude_keys = {'description'}
        return {k: v for k, v in platform_config.items() if k not in exclude_keys}
        