import yaml
from pathlib import Path


class Config:
    _instance = None
    _loaded = False
    _data: dict = {}
    
    @classmethod
    def load(cls, config_path: str = "config.yaml"):
        if cls._loaded:
            return cls._instance or cls()
        
        path = Path(config_path)
        if not path.exists():
            # 如果配置文件不存在，创建一个空文件
            path.touch()
            
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
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
