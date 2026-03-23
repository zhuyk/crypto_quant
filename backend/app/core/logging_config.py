"""
结构化日志配置 - 生产环境
"""

import logging
import sys
from datetime import datetime
from typing import Optional
import json


class JSONFormatter(logging.Formatter):
    """JSON 格式日志"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加额外字段
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'symbol'):
            log_data['symbol'] = record.symbol
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class TradingFormatter(logging.Formatter):
    """交易日志格式"""
    
    def format(self, record: logging.LogRecord) -> str:
        # 交易相关日志特殊格式
        if hasattr(record, 'trade_type'):
            trade_log = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "type": "TRADE",
                "trade_type": record.trade_type,
                "symbol": getattr(record, 'symbol', ''),
                "side": getattr(record, 'side', ''),
                "price": getattr(record, 'price', 0),
                "amount": getattr(record, 'amount', 0),
                "pnl": getattr(record, 'pnl', 0),
                "message": record.getMessage(),
            }
            return json.dumps(trade_log, ensure_ascii=False)
        
        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: str = "json",
    service_name: str = "cryptoquant"
):
    """
    配置日志系统
    
    Args:
        log_level: 日志级别
        log_file: 日志文件路径
        log_format: 日志格式 (json/text)
        service_name: 服务名称
    """
    # 根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    if log_format == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(TradingFormatter(
            f'%(asctime)s [{service_name}] %(levelname)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
    
    # 设置第三方库日志级别
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('celery').setLevel(logging.INFO)
    
    # 创建服务日志
    logger = logging.getLogger(service_name)
    logger.info(f"{service_name} logging initialized", extra={'service': service_name})
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger(name)
