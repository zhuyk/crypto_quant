"""数据持久化模块"""
from .kline_storage import KlineStorage, get_kline_storage

__all__ = ["KlineStorage", "get_kline_storage"]
