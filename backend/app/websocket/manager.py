"""
WebSocket 连接管理器
支持广播、单播、房间管理
"""
import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # 所有连接
        self.active_connections: Set[WebSocket] = set()
        
        # 按用户 ID 分组的连接
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        
        # 按房间分组的连接
        self.rooms: Dict[str, Set[WebSocket]] = {}
        
        # 连接元数据
        self.connection_metadata: Dict[WebSocket, Dict] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        room: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        接受 WebSocket 连接
        
        Args:
            websocket: WebSocket 连接
            user_id: 用户 ID (可选)
            room: 房间名 (可选)
            metadata: 连接元数据 (可选)
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # 记录元数据
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "room": room,
            "connected_at": datetime.now().isoformat(),
            **(metadata or {}),
        }
        
        # 添加到用户连接
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
        
        # 添加到房间
        if room:
            if room not in self.rooms:
                self.rooms[room] = set()
            self.rooms[room].add(websocket)
        
        logger.info(f"✅ WebSocket 连接建立 - user: {user_id}, room: {room}")
    
    def disconnect(self, websocket: WebSocket) -> None:
        """
        断开 WebSocket 连接
        
        Args:
            websocket: WebSocket 连接
        """
        if websocket not in self.active_connections:
            return
        
        self.active_connections.remove(websocket)
        
        # 清理元数据
        metadata = self.connection_metadata.pop(websocket, {})
        user_id = metadata.get("user_id")
        room = metadata.get("room")
        
        # 从用户连接中移除
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # 从房间中移除
        if room and room in self.rooms:
            self.rooms[room].discard(websocket)
            if not self.rooms[room]:
                del self.rooms[room]
        
        logger.info(f"👋 WebSocket 连接断开 - user: {user_id}, room: {room}")
    
    async def send_personal(self, message: Any, websocket: WebSocket) -> None:
        """
        发送个人消息
        
        Args:
            message: 消息内容 (会自动 JSON 序列化)
            websocket: 目标 WebSocket 连接
        """
        try:
            if isinstance(message, dict):
                message["timestamp"] = datetime.now().isoformat()
                await websocket.send_json(message)
            elif isinstance(message, str):
                await websocket.send_text(message)
            else:
                await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送个人消息失败：{e}")
    
    async def broadcast(self, message: Any, exclude: Optional[WebSocket] = None) -> None:
        """
        广播消息给所有连接
        
        Args:
            message: 消息内容
            exclude: 排除的连接 (可选)
        """
        if isinstance(message, dict):
            message["timestamp"] = datetime.now().isoformat()
        
        disconnected = set()
        
        for connection in self.active_connections:
            if connection == exclude:
                continue
            
            try:
                if isinstance(message, dict):
                    await connection.send_json(message)
                elif isinstance(message, str):
                    await connection.send_text(message)
                else:
                    await connection.send_json(message)
            except Exception as e:
                logger.error(f"广播消息失败：{e}")
                disconnected.add(connection)
        
        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_to_user(self, user_id: str, message: Any) -> None:
        """
        广播消息给指定用户的所有连接
        
        Args:
            user_id: 用户 ID
            message: 消息内容
        """
        if user_id not in self.user_connections:
            return
        
        message_dict = message if isinstance(message, dict) else {"data": message}
        message_dict["user_id"] = user_id
        message_dict["timestamp"] = datetime.now().isoformat()
        
        disconnected = set()
        
        for connection in self.user_connections[user_id]:
            try:
                await connection.send_json(message_dict)
            except Exception as e:
                logger.error(f"发送用户消息失败：{e}")
                disconnected.add(connection)
        
        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_to_room(self, room: str, message: Any) -> None:
        """
        广播消息到指定房间
        
        Args:
            room: 房间名
            message: 消息内容
        """
        if room not in self.rooms:
            return
        
        message_dict = message if isinstance(message, dict) else {"data": message}
        message_dict["room"] = room
        message_dict["timestamp"] = datetime.now().isoformat()
        
        disconnected = set()
        
        for connection in self.rooms[room]:
            try:
                await connection.send_json(message_dict)
            except Exception as e:
                logger.error(f"发送房间消息失败：{e}")
                disconnected.add(connection)
        
        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)
    
    async def send_trade_update(
        self,
        action: str,
        symbol: str,
        data: Dict,
        user_id: Optional[str] = None,
    ) -> None:
        """
        发送交易更新
        
        Args:
            action: 动作 (order_created, order_filled, position_closed, etc.)
            symbol: 交易对
            data: 详细数据
            user_id: 用户 ID (可选)
        """
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
    
    async def send_price_update(self, symbol: str, price: float, change_pct: float) -> None:
        """
        发送价格更新
        
        Args:
            symbol: 交易对
            price: 当前价格
            change_pct: 变化百分比
        """
        message = {
            "type": "price_update",
            "symbol": symbol,
            "price": price,
            "change_pct": change_pct,
        }
        await self.broadcast(message)
    
    async def send_strategy_signal(
        self,
        strategy: str,
        symbol: str,
        signal: str,
        strength: float,
        data: Optional[Dict] = None,
    ) -> None:
        """
        发送策略信号
        
        Args:
            strategy: 策略名
            symbol: 交易对
            signal: 信号 (buy/sell/hold)
            strength: 信号强度 (0-1)
            data: 详细数据
        """
        message = {
            "type": "strategy_signal",
            "strategy": strategy,
            "symbol": symbol,
            "signal": signal,
            "strength": strength,
            "data": data or {},
        }
        await self.broadcast(message)
    
    def get_stats(self) -> Dict:
        """获取连接统计"""
        return {
            "total_connections": len(self.active_connections),
            "users": len(self.user_connections),
            "rooms": len(self.rooms),
            "room_details": {
                room: len(connections) for room, connections in self.rooms.items()
            },
        }


# 全局管理器实例
manager = ConnectionManager()


def get_manager() -> ConnectionManager:
    """获取 WebSocket 管理器"""
    return manager
