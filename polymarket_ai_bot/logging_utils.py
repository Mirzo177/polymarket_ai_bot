import sys
from pathlib import Path
from loguru import logger
from datetime import datetime


def setup_logging(log_level: str = "INFO"):
    logger.remove()
    
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d")
    
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    logger.add(
        log_dir / f"system_{timestamp}.log",
        level="INFO",
        rotation="00:00",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True
    )
    
    logger.add(
        log_dir / f"trades_{timestamp}.log",
        level="INFO",
        rotation="00:00",
        retention="90 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | TRADE | {message}",
        enqueue=True,
        filter=lambda record: "trade" in record["extra"] or "order" in record["message"].lower()
    )
    
    logger.add(
        log_dir / f"errors_{timestamp}.log",
        level="ERROR",
        rotation="00:00",
        retention="90 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True
    )
    
    return logger


def get_logger(name=None):
    if name:
        return logger.bind(name=name)
    return logger


class LoggingContext:
    def __init__(self, logger_instance, **context):
        self.logger = logger_instance
        self.context = context
    
    def __enter__(self):
        for key, value in self.context.items():
            self.logger = self.logger.bind(**{key: value})
        return self.logger
    
    def __exit__(self, *args):
        pass