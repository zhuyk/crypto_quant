"""
交易连接状态管理
"""
import os
import json
from pathlib import Path

STATE_FILE = Path(__file__).parent / ".trading_state.json"


def load_trading_state():
    """加载交易状态"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"connected": False, "exchange": "binance", "testnet": True}


def save_trading_state(connected: bool, exchange: str = "binance", testnet: bool = True):
    """保存交易状态"""
    state = {
        "connected": connected,
        "exchange": exchange,
        "testnet": testnet,
        "timestamp": __import__('time').time()
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def set_connected(exchange: str = "binance", testnet: bool = True):
    """设置已连接"""
    save_trading_state(True, exchange, testnet)


def set_disconnected():
    """设置已断开"""
    save_trading_state(False)


def is_connected() -> bool:
    """检查是否已连接"""
    state = load_trading_state()
    return state.get("connected", False)
