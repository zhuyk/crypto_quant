"""
交易连接状态管理

持久化交易所连接状态到 JSON 文件，
支持多进程/重启后恢复状态。
"""
from __future__ import annotations

import json
import time
import logging
from pathlib import Path
from typing import TypedDict, Optional

logger = logging.getLogger(__name__)

# 状态文件路径
_STATE_FILE: Path = Path(__file__).parent / ".trading_state.json"


class TradingState(TypedDict):
    """交易状态结构"""
    connected: bool
    exchange: str
    testnet: bool
    timestamp: float


def _default_state() -> TradingState:
    """默认状态"""
    return TradingState(
        connected=False,
        exchange="binance",
        testnet=True,
        timestamp=0.0,
    )


def load_trading_state() -> TradingState:
    """
    加载交易状态

    Returns:
        TradingState: 当前状态字典
    """
    if not _STATE_FILE.exists():
        return _default_state()

    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 验证必要字段
        return TradingState(
            connected=bool(data.get("connected", False)),
            exchange=str(data.get("exchange", "binance")),
            testnet=bool(data.get("testnet", True)),
            timestamp=float(data.get("timestamp", 0.0)),
        )
    except (json.JSONDecodeError, OSError, TypeError) as e:
        logger.warning(f"加载交易状态失败，使用默认值: {e}")
        return _default_state()


def save_trading_state(
    connected: bool,
    exchange: str = "binance",
    testnet: bool = True,
) -> None:
    """
    保存交易状态

    Args:
        connected: 是否已连接
        exchange: 交易所 ID
        testnet: 是否测试网
    """
    state: TradingState = TradingState(
        connected=connected,
        exchange=exchange,
        testnet=testnet,
        timestamp=time.time(),
    )

    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        logger.error(f"保存交易状态失败: {e}")


def set_connected(exchange: str = "binance", testnet: bool = True) -> None:
    """设置为已连接状态"""
    save_trading_state(connected=True, exchange=exchange, testnet=testnet)


def set_disconnected() -> None:
    """设置为已断开状态"""
    save_trading_state(connected=False)


def is_connected() -> bool:
    """检查是否已连接"""
    state = load_trading_state()
    return state["connected"]


def get_connection_info() -> Optional[TradingState]:
    """
    获取完整连接信息

    Returns:
        TradingState if connected, None otherwise
    """
    state = load_trading_state()
    if state["connected"]:
        return state
    return None
