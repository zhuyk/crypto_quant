"""
WebSocket 连接管理器

支持:
- 广播 / 单播 / 房间广播
- 用户级连接管理
- 自动清理断开的连接
- 连接统计
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket 连接管理器

    管理所有活跃的 WebSocket 连接，支持按用户/房间分组推送。
    """

    def __init__(self) -> None:
        # 所有活跃连接
        self._active_connections: Set[WebSocket] = set()
        # 按用户 ID 分组
        self._user_connections: Dict[str, Set[WebSocket]] = {}
        # 按房间分组
        self._rooms: Dict[str, Set[WebSocket]] = {}
        # 连接元数据
        self._metadata: Dict[int, Dict[str, Any]] = {}  # id(ws) -> metadata

    # ==================== 连接生命周期 ====================

    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        room: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """接受并注册 WebSocket 连接"""
        await websocket.accept()
        self._active_connections.add(websocket)

        # 存储元数据（使用 id(ws) 作为 key 避免 hash 问题）
        ws_id = id(websocket)
        self._metadata[ws_id] = {
            "user_id": user_id,
            "room": room,
            "connected_at": datetime.now().isoformat(),
            **(metadata or {}),
        }

        # 注册到用户组
        if user_id:
            self._user_connections.setdefault(user_id, set()).add(websocket)

        # 注册到房间
        if room:
            self._rooms.setdefault(room, set()).add(websocket)

        logger.info(
            f"✅ WebSocket 连接建立 - user={user_id}, room={room}, "
            f"total={len(self._active_connections)}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """断开并清理 WebSocket 连接"""
        if websocket not in self._active_connections:
            return

        self._active_connections.discard(websocket)

        # 取出元数据
        ws_id = id(websocket)
        meta = self._metadata.pop(ws_id, {})
        user_id: Optional[str] = meta.get("user_id")
        room: Optional[str] = meta.get("room")

        # 清理用户组
        if user_id and user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        # 清理房间
        if room and room in self._rooms:
            self._rooms[room].discard(websocket)
            if not self._rooms[room]:
                del self._rooms[room]

        logger.info(
            f"👋 WebSocket 断开 - user={user_id}, room={room}, "
            f"remaining={len(self._active_connections)}"
        )

    # ==================== 消息发送 ====================

    async def send_personal(self, message: Any, websocket: WebSocket) -> bool:
        """
        发送个人消息

        Returns:
            bool: 发送是否成功
        """
        try:
            payload = self._prepare_message(message)
            await websocket.send_json(payload)
            return True
        except Exception as e:
            logger.warning(f"发送个人消息失败: {e}")
            self.disconnect(websocket)
            return False

    async def broadcast(
        self,
        message: Any,
        exclude: Optional[WebSocket] = None,
    ) -> int:
        """
        广播消息给所有连接

        Returns:
            int: 成功发送的连接数
        """
        payload = self._prepare_message(message)
        return await self._send_to_group(self._active_connections, payload, exclude)

    async def broadcast_to_user(self, user_id: str, message: Any) -> int:
        """
        广播消息给指定用户的所有连接

        Returns:
            int: 成功发送的连接数
        """
        connections = self._user_connections.get(user_id)
        if not connections:
            return 0

        payload = self._prepare_message(message)
        payload["user_id"] = user_id
        return await self._send_to_group(connections, payload)

    async def broadcast_to_room(self, room: str, message: Any) -> int:
        """
        广播消息到指定房间

        Returns:
            int: 成功发送的连接数
        """
        connections = self._rooms.get(room)
        if not connections:
            return 0

        payload = self._prepare_message(message)
        payload["room"] = room
        return await self._send_to_group(connections, payload)

    # ==================== 业务消息快捷方法 ====================

    async def send_price_update(
        self, symbol: str, price: float, change_pct: float
    ) -> None:
        """发送价格更新"""
        await self.broadcast({
            "type": "price_update",
            "symbol": symbol,
            "price": price,
            "change_pct": change_pct,
        })

    async def send_trade_update(
        self,
        action: str,
        symbol: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> None:
        """发送交易更新（指定用户或广播）"""
        message = {
            "type": "trade_update",
            "action": action,
            "symbol": symbol,
            "data": data,
        }
        if user_id:
            await self.broadcast_to_user(user_id, message)
        else:
            await self.broadcast(message)

    async def send_strategy_signal(
        self,
        strategy: str,
        symbol: str,
        signal: str,
        strength: float,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """发送策略信号"""
        await self.broadcast({
            "type": "strategy_signal",
            "strategy": strategy,
            "symbol": symbol,
            "signal": signal,
            "strength": strength,
            "data": data or {},
        })

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取连接统计"""
        return {
            "total_connections": len(self._active_connections),
            "users": len(self._user_connections),
            "rooms": len(self._rooms),
            "room_details": {
                room: len(conns) for room, conns in self._rooms.items()
            },
        }

    @property
    def connection_count(self) -> int:
        """当前连接数"""
        return len(self._active_connections)

    # ==================== 内部方法 ====================

    def _prepare_message(self, message: Any) -> Dict[str, Any]:
        """标准化消息为字典格式，附加时间戳"""
        if isinstance(message, dict):
            payload = dict(message)
        elif isinstance(message, str):
            payload = {"data": message}
        else:
            payload = {"data": message}

        payload.setdefault("timestamp", datetime.now().isoformat())
        return payload

    async def _send_to_group(
        self,
        connections: Set[WebSocket],
        payload: Dict[str, Any],
        exclude: Optional[WebSocket] = None,
    ) -> int:
        """向一组连接发送消息，自动清理失败连接"""
        disconnected: Set[WebSocket] = set()
        sent_count: int = 0

        for ws in connections.copy():  # copy() 避免迭代中修改
            if ws is exclude:
                continue
            try:
                await ws.send_json(payload)
                sent_count += 1
            except Exception:
                disconnected.add(ws)

        # 清理断开的连接
        for ws in disconnected:
            self.disconnect(ws)

        return sent_count


# 全局管理器单例
manager: ConnectionManager = ConnectionManager()


def get_manager() -> ConnectionManager:
    """获取 WebSocket 管理器单例"""
    return manager
