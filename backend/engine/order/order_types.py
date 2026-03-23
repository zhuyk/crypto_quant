"""
订单类型定义
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from decimal import Decimal
import uuid


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"           # 市价单
    LIMIT = "limit"             # 限价单
    STOP_LOSS = "stop_loss"     # 止损单
    STOP_LIMIT = "stop_limit"   # 止损限价单
    TAKE_PROFIT = "take_profit" # 止盈单


class TimeInForce(Enum):
    """订单有效期"""
    GTC = "GTC"  # Good Till Cancel - 直到取消
    IOC = "IOC"  # Immediate Or Cancel - 立即成交或取消
    FOK = "FOK"  # Fill Or Kill - 全部成交或取消
    GTD = "GTD"  # Good Till Date - 直到指定日期


class OrderState(Enum):
    """订单状态"""
    PENDING = "pending"       # 待提交
    SUBMITTED = "submitted"   # 已提交
    PARTIALLY_FILLED = "partially_filled"  # 部分成交
    FILLED = "filled"         # 完全成交
    CANCELLED = "cancelled"   # 已取消
    REJECTED = "rejected"     # 被拒绝
    EXPIRED = "expired"       # 已过期
    FAILED = "failed"         # 失败


@dataclass
class Order:
    """
    订单数据结构
    
    Attributes:
        order_id: 订单 ID
        client_order_id: 客户端订单 ID
        symbol: 交易对
        side: 买卖方向
        type: 订单类型
        quantity: 数量
        price: 价格（限价单）
        stop_price: 触发价格（止损/止盈单）
        time_in_force: 有效期
        state: 订单状态
        filled_quantity: 已成交数量
        avg_fill_price: 平均成交价格
        created_at: 创建时间
        updated_at: 更新时间
        strategy_id: 策略 ID
        retry_count: 重试次数
        error_message: 错误信息
    """
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: Decimal
    client_order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: Optional[str] = None
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    state: OrderState = OrderState.PENDING
    filled_quantity: Decimal = Decimal('0')
    avg_fill_price: Decimal = Decimal('0')
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    strategy_id: Optional[str] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    
    @property
    def is_active(self) -> bool:
        """订单是否活跃（可成交）"""
        return self.state in [
            OrderState.PENDING,
            OrderState.SUBMITTED,
            OrderState.PARTIALLY_FILLED
        ]
    
    @property
    def is_terminal(self) -> bool:
        """订单是否终态（不可再成交）"""
        return self.state in [
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.EXPIRED,
            OrderState.FAILED
        ]
    
    @property
    def fill_ratio(self) -> float:
        """成交比例"""
        if self.quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.quantity)
    
    @property
    def remaining_quantity(self) -> Decimal:
        """剩余数量"""
        return self.quantity - self.filled_quantity
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.type.value,
            "quantity": str(self.quantity),
            "price": str(self.price) if self.price else None,
            "stop_price": str(self.stop_price) if self.stop_price else None,
            "time_in_force": self.time_in_force.value,
            "state": self.state.value,
            "filled_quantity": str(self.filled_quantity),
            "avg_fill_price": str(self.avg_fill_price),
            "fill_ratio": self.fill_ratio,
            "remaining_quantity": str(self.remaining_quantity),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "strategy_id": self.strategy_id,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
        }


@dataclass
class OrderFill:
    """
    订单成交记录
    
    Attributes:
        fill_id: 成交 ID
        order_id: 订单 ID
        symbol: 交易对
        side: 买卖方向
        price: 成交价格
        quantity: 成交数量
        commission: 手续费
        commission_asset: 手续费币种
        trade_id: 交易 ID
        fill_time: 成交时间
    """
    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    commission: Decimal = Decimal('0')
    commission_asset: str = "USDT"
    trade_id: Optional[str] = None
    fill_time: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "price": str(self.price),
            "quantity": str(self.quantity),
            "commission": str(self.commission),
            "commission_asset": self.commission_asset,
            "trade_id": self.trade_id,
            "fill_time": self.fill_time.isoformat(),
        }


@dataclass
class OrderResult:
    """
    订单执行结果
    
    Attributes:
        success: 是否成功
        order: 订单对象
        message: 消息
        fills: 成交记录列表
    """
    success: bool
    order: Optional[Order] = None
    message: str = ""
    fills: list[OrderFill] = field(default_factory=list)
