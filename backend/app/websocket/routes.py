"""
WebSocket 路由
"""
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from typing import Optional

from app.websocket.manager import manager, get_manager, ConnectionManager
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: Optional[str] = Query(None, description="用户 ID"),
    room: Optional[str] = Query(None, description="房间名"),
    token: Optional[str] = Query(None, description="认证令牌"),
):
    """
    WebSocket 主端点
    
    支持的功能:
    - 实时价格推送
    - 订单状态更新
    - 策略信号推送
    - 系统通知
    
    连接示例:
    ws://localhost:8000/ws?user_id=user123&room=btc_traders
    """
    # 简单的认证 (生产环境应该验证 token)
    if token and not settings.DEBUG:
        # TODO: 实现真实的 token 验证
        pass
    
    # 连接
    await manager.connect(
        websocket,
        user_id=user_id,
        room=room,
        metadata={"token": token},
    )
    
    # 发送欢迎消息
    await manager.send_personal(
        {
            "type": "welcome",
            "message": "欢迎连接到 CryptoQuant WebSocket",
            "user_id": user_id,
            "room": room,
        },
        websocket,
    )
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            
            try:
                message = parse_client_message(data)
                await handle_client_message(message, websocket, user_id)
            except Exception as e:
                logger.error(f"处理客户端消息失败：{e}")
                await manager.send_personal(
                    {
                        "type": "error",
                        "message": f"消息处理失败：{str(e)}",
                    },
                    websocket,
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"客户端断开连接 - user: {user_id}")
    
    except Exception as e:
        logger.error(f"WebSocket 错误：{e}", exc_info=True)
        manager.disconnect(websocket)


def parse_client_message(data: str) -> dict:
    """
    解析客户端消息
    
    支持的消息类型:
    - subscribe: 订阅主题
    - unsubscribe: 取消订阅
    - ping: 心跳
    - trade: 交易指令
    """
    import json
    
    try:
        message = json.loads(data)
        msg_type = message.get("type")
        
        if msg_type not in ["subscribe", "unsubscribe", "ping", "trade"]:
            raise ValueError(f"未知消息类型：{msg_type}")
        
        return message
    except json.JSONDecodeError:
        raise ValueError("无效的 JSON 格式")


async def handle_client_message(
    message: dict,
    websocket: WebSocket,
    user_id: Optional[str],
) -> None:
    """
    处理客户端消息
    
    Args:
        message: 解析后的消息
        websocket: WebSocket 连接
        user_id: 用户 ID
    """
    msg_type = message.get("type")
    
    if msg_type == "ping":
        # 心跳响应
        await manager.send_personal(
            {
                "type": "pong",
                "timestamp": message.get("timestamp"),
            },
            websocket,
        )
    
    elif msg_type == "subscribe":
        # 订阅主题
        topic = message.get("topic")
        if topic:
            logger.info(f"用户 {user_id} 订阅主题：{topic}")
            await manager.send_personal(
                {
                    "type": "subscribed",
                    "topic": topic,
                },
                websocket,
            )
    
    elif msg_type == "unsubscribe":
        # 取消订阅
        topic = message.get("topic")
        if topic:
            logger.info(f"用户 {user_id} 取消订阅：{topic}")
            await manager.send_personal(
                {
                    "type": "unsubscribed",
                    "topic": topic,
                },
                websocket,
            )
    
    elif msg_type == "trade":
        # 交易指令 (需要认证)
        if not user_id:
            await manager.send_personal(
                {
                    "type": "error",
                    "message": "未认证用户不能发送交易指令",
                },
                websocket,
            )
            return
        
        # TODO: 处理交易指令
        logger.info(f"收到交易指令：{message}")


@router.get("/stats")
async def get_websocket_stats():
    """获取 WebSocket 连接统计"""
    return manager.get_stats()


# ==================== 辅助函数 ====================

async def broadcast_price_update(
    symbol: str,
    price: float,
    change_pct: float,
) -> None:
    """
    广播价格更新
    
    Args:
        symbol: 交易对
        price: 当前价格
        change_pct: 变化百分比
    """
    await manager.send_price_update(symbol, price, change_pct)


async def broadcast_trade_update(
    action: str,
    symbol: str,
    data: dict,
    user_id: Optional[str] = None,
) -> None:
    """
    广播交易更新
    
    Args:
        action: 动作 (order_created, order_filled, position_closed)
        symbol: 交易对
        data: 详细数据
        user_id: 用户 ID (可选，为 None 时广播给所有人)
    """
    await manager.send_trade_update(action, symbol, data, user_id)


async def broadcast_strategy_signal(
    strategy: str,
    symbol: str,
    signal: str,
    strength: float,
    data: Optional[dict] = None,
) -> None:
    """
    广播策略信号
    
    Args:
        strategy: 策略名
        symbol: 交易对
        signal: 信号 (buy/sell/hold)
        strength: 信号强度
        data: 详细数据
    """
    await manager.send_strategy_signal(strategy, symbol, signal, strength, data)
