import logging
import inspect
from datetime import datetime

LOG_LEVEL = 'info'

LEVELS = {
    'debug': 0,
    'info': 1,
    'success': 1,
    'warning': 2,
    'error': 3
}


def set_log_level(level: str):
    global LOG_LEVEL
    LOG_LEVEL = level.lower()
    print(f"\033[90m[logger] 日志等级已设置为: {level.upper()}\033[0m")


def setup_logger(name: str = 'app', level: int = logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s │ %(levelname)-8s │ [%(name)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def log_message(message: str, level: str = 'info', source: str = None, logger: logging.Logger = None):
    if LEVELS.get(level.lower(), 1) < LEVELS.get(LOG_LEVEL, 1):
        return
    
    if source is None:
        source = _get_caller_module()
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    symbol = '✓' if level == 'success' else '→'
    
    colors = {
        'success': '\033[92m',
        'info': '\033[96m',
        'warning': '\033[93m',
        'error': '\033[91m',
        'debug': '\033[90m'
    }
    color = colors.get(level, '\033[96m')
    
    formatted = f"{color}{timestamp}\033[0m │ {color}{level.upper():<8}\033[0m │ {color}[{source}]\033[0m {symbol} {message}"
    print(formatted)
    
    if logger:
        log_func = getattr(logger, level, logger.info)
        log_func(message)


def _get_caller_module() -> str:
    try:
        frame = inspect.currentframe()
        caller_frame = frame.f_back.f_back
        module = inspect.getmodule(caller_frame)
        if module:
            filename = module.__file__
            name = filename.split('\\')[-1].replace('.py', '') if '\\' in filename else filename.split('/')[-1].replace('.py', '')
            return name
        return 'unknown'
    except:
        return 'unknown'
