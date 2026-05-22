"""
WebSocket 路由

提供:
- /ws 主连接端点（心跳/订阅/交易指令）
- /stats 连接统计
- 广播辅助函数（供其他模块调用）
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.websocket.manager import manager
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# 支持的客户端消息类型
_VALID_MSG_TYPES = frozenset({"subscribe", "unsubscribe", "ping", "trade"})


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: Optional[str] = Query(None, description="用户 ID"),
    room: Optional[str] = Query(None, description="房间名"),
    token: Optional[str] = Query(None, description="认证令牌"),
) -> None:
    """
    WebSocket 主端点

    连接示例: ws://localhost:8000/api/v1/ws/ws?user_id=user123&room=btc_traders
    """
    # 简单认证 (生产环境应验证 token)
    if token and not settings.DEBUG:
        # TODO: 实现 JWT token 验证
        pass

    # 建立连接
    await manager.connect(websocket, user_id=user_id, room=room)

    # 欢迎消息
    await manager.send_personal(
        {"type": "welcome", "message": "欢迎连接到 CryptoQuant WebSocket", "user_id": user_id, "room": room},
        websocket,
    )

    try:
        while True:
            raw_data: str = await websocket.receive_text()

            try:
                message = _parse_client_message(raw_data)
                await _handle_client_message(message, websocket, user_id)
            except ValueError as e:
                await manager.send_personal(
                    {"type": "error", "message": str(e)},
                    websocket,
                )
            except Exception as e:
                logger.error(f"处理 WS 消息异常: {e}", exc_info=True)
                await manager.send_personal(
                    {"type": "error", "message": "内部处理错误"},
                    websocket,
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 连接异常: {e}", exc_info=True)
        manager.disconnect(websocket)


@router.get("/stats")
async def get_websocket_stats() -> Dict[str, Any]:
    """获取 WebSocket 连接统计"""
    return manager.get_stats()


# ==================== 内部消息处理 ====================


def _parse_client_message(data: str) -> Dict[str, Any]:
    """
    解析客户端 JSON 消息

    Raises:
        ValueError: 格式无效或类型未知
    """
    try:
        message: Dict[str, Any] = json.loads(data)
    except json.JSONDecodeError:
        raise ValueError("无效的 JSON 格式")

    msg_type = message.get("type")
    if msg_type not in _VALID_MSG_TYPES:
        raise ValueError(f"未知消息类型: {msg_type}，支持: {sorted(_VALID_MSG_TYPES)}")

    return message


async def _handle_client_message(
    message: Dict[str, Any],
    websocket: WebSocket,
    user_id: Optional[str],
) -> None:
    """分发处理客户端消息"""
    msg_type: str = message["type"]

    if msg_type == "ping":
        await manager.send_personal(
            {"type": "pong", "client_ts": message.get("timestamp")},
            websocket,
        )

    elif msg_type == "subscribe":
        topic: Optional[str] = message.get("topic")
        if topic:
            logger.debug(f"用户 {user_id} 订阅: {topic}")
            await manager.send_personal({"type": "subscribed", "topic": topic}, websocket)

    elif msg_type == "unsubscribe":
        topic = message.get("topic")
        if topic:
            logger.debug(f"用户 {user_id} 取消订阅: {topic}")
            await manager.send_personal({"type": "unsubscribed", "topic": topic}, websocket)

    elif msg_type == "trade":
        if not user_id:
            await manager.send_personal(
                {"type": "error", "message": "未认证用户不能发送交易指令"},
                websocket,
            )
            return
        # TODO: 转发到交易执行引擎
        logger.info(f"收到交易指令 from user={user_id}: {message.get('data', {})}")
        await manager.send_personal(
            {"type": "trade_ack", "message": "交易指令已接收"},
            websocket,
        )


# ==================== 广播辅助函数（供外部模块调用）====================


async def broadcast_price_update(
    symbol: str, price: float, change_pct: float
) -> None:
    """广播价格更新"""
    await manager.send_price_update(symbol, price, change_pct)


async def broadcast_trade_update(
    action: str,
    symbol: str,
    data: Dict[str, Any],
    user_id: Optional[str] = None,
) -> None:
    """广播交易更新"""
    await manager.send_trade_update(action, symbol, data, user_id)


async def broadcast_strategy_signal(
    strategy: str,
    symbol: str,
    signal: str,
    strength: float,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """广播策略信号"""
    await manager.send_strategy_signal(strategy, symbol, signal, strength, data)
