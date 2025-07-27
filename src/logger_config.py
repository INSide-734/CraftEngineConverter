import logging
from colorama import Fore, Style, init
from typing import Optional

# 初始化 colorama，autoreset 确保每次输出后颜色重置
init(autoreset=True)


class ModernConsoleFormatter(logging.Formatter):
    """
    自定义日志格式器。
    非 DEBUG 模式下，INFO 级别仅显示消息，不带时间戳和级别。
    """

    FORMATS = {
        logging.DEBUG: f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} {Fore.BLACK} %(filename)s:%(lineno)d {Style.RESET_ALL} %(message)s",
        logging.INFO: "%(message)s",  # 非 DEBUG 模式下，INFO 级别只输出消息
        logging.WARNING: f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} %(message)s",
        logging.ERROR: f"{Fore.RED}[ERROR]{Style.RESET_ALL} %(message)s",
        logging.CRITICAL: f"{Fore.MAGENTA}{Style.BRIGHT}[CRITICAL]{Style.RESET_ALL} %(message)s"
    }

    def __init__(self, debug_mode: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug_mode = debug_mode

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.FORMATS[logging.INFO])
        # 对于非 DEBUG 模式下的 INFO 级别，不使用时间戳
        if record.levelno == logging.INFO and not getattr(self, 'debug_mode', False):
            formatter = logging.Formatter(log_fmt)
        else:
            formatter = logging.Formatter(f"{Fore.CYAN}[%(asctime)s]{Style.RESET_ALL} " + log_fmt, datefmt='%H:%M:%S')

        # 针对 INFO 级别，特殊处理颜色，使其更自然
        if record.levelno == logging.INFO:
            return f"{Fore.GREEN}{formatter.format(record)}{Style.RESET_ALL}"

        return formatter.format(record)


def setup_logging(debug_mode: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """
    配置日志系统。
    Args:
        debug_mode (bool): 如果为 True，则日志级别设置为 DEBUG。
        log_file (str, optional): 日志文件路径，如指定则写入文件。
    """
    logger = logging.getLogger('YAMLConverter')
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    logger.propagate = False  # 避免重复输出

    # 移除已存在的处理器，避免重复添加
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    # 控制台处理器
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if debug_mode else logging.INFO)  # 控制台输出的最低级别
    ch.setFormatter(ModernConsoleFormatter(debug_mode=debug_mode))
    logger.addHandler(ch)

    # 文件处理器（可选）
    if log_file:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        file_fmt = '[%(asctime)s] %(levelname)s %(filename)s:%(lineno)d %(message)s'
        fh.setFormatter(logging.Formatter(file_fmt, datefmt='%Y-%m-%d %H:%M:%S'))
        logger.addHandler(fh)

    return logger

