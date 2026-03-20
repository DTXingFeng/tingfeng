import yaml
from pathlib import Path

config_path = Path("ai_config.yaml")

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

print('✅ YAML 语法正确')
print(f'平台数量: {len(config["platforms"])}')
print(f'模型数量: {len(config["models"])}')
print(f'LM Studio 平台: {"lm_studio_local" in config["platforms"]}')
print(f'GLM Heretic 模型: {"glm-4.7-heretic-neo-code" in config["models"]}')

if "glm-4.7-heretic-neo-code" in config["models"]:
    model_cfg = config["models"]["glm-4.7-heretic-neo-code"]
    print(f'\n模型配置:')
    print(f'  - 平台: {model_cfg["platform_alias"]}')
    print(f'  - 模型名: {model_cfg["model_name"]}')
    print(f'  - 描述: {model_cfg["description"]}')
    print(f'  - 最大上下文: {model_cfg["max_context_tokens"]}')
    print(f'  - 思考模式: {model_cfg.get("enable_thinking", "未配置")}')

print('\n配置验证完成！')
