from loguru import logger
import sys
from pathlib import Path

class LoggerConfig:
    """日志配置管理器"""
    
    @staticmethod
    def setup(log_dir: str = "logs", rotation: str = "10 MB", retention: str = "30 days"):
        """
        配置 loguru 日志系统
        
        Args:
            log_dir: 日志文件目录
            rotation: 日志文件轮转大小
            retention: 日志保留时间
        """
        try:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            
            logger.remove()
            
            logger.add(
                sys.stdout,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                level="INFO",
                colorize=True
            )
            
            logger.add(
                log_path / "info_{time:YYYY-MM-DD}.log",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level="INFO",
                rotation=rotation,
                retention=retention,
                encoding="utf-8"
            )
            
            logger.add(
                log_path / "error_{time:YYYY-MM-DD}.log",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level="ERROR",
                rotation=rotation,
                retention=retention,
                encoding="utf-8"
            )
            
            logger.add(
                log_path / "debug_{time:YYYY-MM-DD}.log",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level="DEBUG",
                rotation=rotation,
                retention="7 days",
                encoding="utf-8"
            )
        except PermissionError:
            print(f"\n❌ ERROR: 无法写入日志目录 '{log_dir}'。请检查权限！")
            print(f"提示: 请尝试运行 'sudo chown -R $USER:$USER {Path.cwd()}'\n")
            # 在这种情况下，我们至少保留标准输出日志
            logger.remove()
            logger.add(sys.stdout, level="INFO", colorize=True)
        except Exception as e:
            print(f"\n❌ ERROR: 初始化日志系统失败: {e}\n")

LoggerConfig.setup()

def get_logger(name: str = None):
    """
    获取 logger 实例
    
    Args:
        name: logger 名称，默认使用调用模块名
    
    Returns:
        logger 实例
    """
    if name:
        return logger.bind(name=name)
    return logger
