"""
统一日志配置 - 基于 loguru

将 stdlib logging 和 loguru 统一：
- 所有模块可使用 `from loguru import logger` 或 `logging.getLogger(__name__)`
- stdlib logging 的输出会被自动拦截并路由到 loguru
- 统一的格式化和文件输出
"""

import logging
import sys
import os
from typing import Optional
from loguru import logger


class InterceptHandler(logging.Handler):
    """
    将 stdlib logging 拦截并转发到 loguru
    
    这确保了无论模块使用 loguru 还是 stdlib logging，
    日志都通过统一的 loguru pipeline 输出。
    """
    
    def emit(self, record: logging.LogRecord):
        # 获取对应的 loguru 级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        
        # 找到调用者的帧（跳过 logging 和本拦截器的帧）
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: str = "text",
    service_name: str = "cryptoquant",
):
    """
    配置统一日志系统
    
    - loguru 作为唯一的日志后端
    - stdlib logging 通过 InterceptHandler 桥接到 loguru
    - 支持 JSON / Text 格式切换
    - 支持文件输出和日志轮转
    
    Args:
        log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径（None 则不写文件）
        log_format: "json" 使用结构化 JSON，"text" 使用可读文本
        service_name: 服务名称标识
    """
    # 1. 移除 loguru 默认 handler
    logger.remove()
    
    # 2. 配置 loguru 控制台输出
    if log_format == "json":
        # JSON 结构化日志（适合生产环境 + ELK/Loki 等）
        logger.add(
            sys.stdout,
            level=log_level.upper(),
            format="{message}",
            serialize=True,  # loguru 内置 JSON 序列化
            colorize=False,
        )
    else:
        # 可读文本格式（适合开发环境）
        logger.add(
            sys.stdout,
            level=log_level.upper(),
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                f"<cyan>{service_name}</cyan> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            colorize=True,
        )
    
    # 3. 配置文件输出（带日志轮转）
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        logger.add(
            log_file,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="50 MB",       # 单文件最大 50MB
            retention="7 days",     # 保留 7 天
            compression="gz",       # 旧文件压缩
            encoding="utf-8",
            serialize=(log_format == "json"),
        )
    
    # 4. 拦截 stdlib logging -> loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # 5. 抑制第三方库过于啰嗦的日志
    for noisy_logger in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy.engine",
        "celery",
        "websockets",
        "httpx",
        "httpcore",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    
    logger.info(f"日志系统初始化完成 | service={service_name} level={log_level} format={log_format}")


def get_logger(name: str):
    """
    获取日志记录器
    
    兼容接口：返回 loguru logger 的绑定实例。
    使用方式: logger = get_logger(__name__)
    """
    return logger.bind(module=name)
