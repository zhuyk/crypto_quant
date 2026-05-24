#!/usr/bin/env python3
"""
实盘交易引擎核心模块
"""
import ccxt
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
from dataclasses import dataclass, field
from enum import Enum


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"

    def to_signal_side(self) -> str:
        """转换为策略层 SignalSide 值"""
        return "long" if self == OrderSide.BUY else "short"

    @classmethod
    def from_signal_side(cls, signal_side) -> "OrderSide":
        """从策略层 SignalSide 转换"""
        val = signal_side.value if hasattr(signal_side, "value") else str(signal_side)
        return cls.BUY if val == "long" else cls.SELL


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """订单数据类"""
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    amount: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: float = 0.0
    filled_price: float = 0.0
    fee: float = 0.0
    fee_currency: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.type.value,
            "amount": self.amount,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled_amount": self.filled_amount,
            "filled_price": self.filled_price,
            "fee": self.fee,
            "fee_currency": self.fee_currency,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Position:
    """持仓数据类"""
    symbol: str
    side: OrderSide
    amount: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: float = 1.0
    opened_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_price(self, price: float):
        """更新当前价格并计算盈亏"""
        self.current_price = price
        self.updated_at = datetime.now()
        
        if self.side == OrderSide.BUY:
            self.unrealized_pnl = (price - self.entry_price) * self.amount
            self.unrealized_pnl_pct = (price - self.entry_price) / self.entry_price * 100
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.amount
            self.unrealized_pnl_pct = (self.entry_price - price) / self.entry_price * 100
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "amount": self.amount,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "leverage": self.leverage,
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_strategy_position(self):
        """
        转换为策略层 Position (strategies.base.Position)
        
        用于需要在策略和交易引擎之间传递持仓数据的场景。
        """
        from strategies.base import Position as StrategyPosition, SignalSide
        side = SignalSide.LONG if self.side == OrderSide.BUY else SignalSide.SHORT
        return StrategyPosition(
            symbol=self.symbol,
            side=side,
            quantity=self.amount,
            entry_price=self.entry_price,
            current_price=self.current_price,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
        )

    @classmethod
    def from_strategy_position(cls, strategy_pos, leverage: float = 1.0) -> "Position":
        """
        从策略层 Position 创建交易层 Position
        """
        from strategies.base import SignalSide
        side = OrderSide.BUY if strategy_pos.side == SignalSide.LONG else OrderSide.SELL
        pos = cls(
            symbol=strategy_pos.symbol,
            side=side,
            amount=strategy_pos.quantity,
            entry_price=strategy_pos.entry_price,
            current_price=strategy_pos.current_price,
            stop_loss=strategy_pos.stop_loss,
            take_profit=strategy_pos.take_profit,
            leverage=leverage,
        )
        pos.update_price(strategy_pos.current_price)
        return pos


class TradingEngine:
    """实盘交易引擎"""
    
    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True,
        initial_capital: float = 100000.0,
    ):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.initial_capital = initial_capital
        self.capital = initial_capital
        
        # 初始化交易所
        self.exchange: Optional[ccxt.Exchange] = None
        self._init_exchange()
        
        # 订单和持仓管理
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}
        
        # 交易历史
        self.trade_history: List[Dict] = []
        
        logger.info(f"✅ 交易引擎初始化完成 - {exchange_id} {'(测试网)' if testnet else '(实盘)'}")
    
    def _init_exchange(self):
        """初始化交易所连接"""
        try:
            exchange_class = getattr(ccxt, self.exchange_id)
            
            config = {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",  # spot/margin/future
                }
            }
            
            # 添加代理配置 (如果需要)
            import os
            http_proxy = os.getenv("HTTP_PROXY")
            https_proxy = os.getenv("HTTPS_PROXY")
            
            if http_proxy or https_proxy:
                config["proxies"] = {
                    "http": http_proxy,
                    "https": https_proxy,
                }
                logger.info(f"🔧 使用代理配置 - HTTP: {http_proxy}, HTTPS: {https_proxy}")
            
            if self.testnet and self.exchange_id == "binance":
                config["urls"] = {
                    "api": {
                        "public": "https://testnet.binance.vision/api/v3",
                        "private": "https://testnet.binance.vision/api/v3",
                    }
                }
            
            # 配置代理（如果需要）
            import os
            proxy_url = os.getenv('PROXY_URL')
            if proxy_url:
                config['proxies'] = {
                    'http': proxy_url,
                    'https': proxy_url,
                }
                logger.info(f"🌐 使用代理：{proxy_url}")
            else:
                logger.info("🌐 未配置代理，使用直连")
            
            self.exchange = exchange_class(config)
            logger.info(f"✅ 交易所连接成功 - {self.exchange_id}")
            
        except Exception as e:
            logger.error(f"❌ 交易所连接失败：{e}")
            raise
    
    def connect(self) -> bool:
        """测试交易所连接"""
        try:
            if self.exchange:
                self.exchange.fetch_balance()
                logger.info("✅ 交易所连接测试通过")
                return True
        except Exception as e:
            logger.error(f"❌ 交易所连接测试失败：{e}")
            return False
        return False
    
    def get_balance(self) -> Dict[str, float]:
        """获取账户余额"""
        try:
            balance = self.exchange.fetch_balance()
            available = {}
            for currency, data in balance["total"].items():
                if data and data > 0:
                    available[currency] = {
                        "total": balance["total"].get(currency, 0),
                        "free": balance["free"].get(currency, 0),
                        "used": balance["used"].get(currency, 0),
                    }
            return available
        except Exception as e:
            logger.error(f"❌ 获取余额失败：{e}")
            return {}
    
    def get_ticker(self, symbol: str) -> Dict:
        """获取当前行情"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "last": ticker.get("last"),
                "high": ticker.get("high"),
                "low": ticker.get("low"),
                "volume": ticker.get("baseVolume"),
                "timestamp": ticker.get("timestamp"),
            }
        except Exception as e:
            logger.error(f"❌ 获取行情失败：{e}")
            return {}
    
    def get_klines(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> pd.DataFrame:
        """获取 K 线数据"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df
        except Exception as e:
            logger.error(f"❌ 获取 K 线失败：{e}")
            return pd.DataFrame()
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Optional[Order]:
        """创建订单"""
        try:
            # 准备订单参数
            params = {}
            if stop_loss:
                params["stopLoss"] = {"price": stop_loss}
            if take_profit:
                params["takeProfit"] = {"price": take_profit}
            
            # 提交订单
            if order_type == OrderType.MARKET:
                order_response = self.exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=side.value,
                    amount=amount,
                    params=params,
                )
            elif order_type == OrderType.LIMIT:
                if not price:
                    raise ValueError("限价单需要指定价格")
                order_response = self.exchange.create_order(
                    symbol=symbol,
                    type="limit",
                    side=side.value,
                    amount=amount,
                    price=price,
                    params=params,
                )
            else:
                raise ValueError(f"不支持的订单类型：{order_type}")
            
            # 创建订单对象
            order = Order(
                id=order_response["id"],
                symbol=symbol,
                side=side,
                type=order_type,
                amount=amount,
                price=price,
                stop_price=stop_price,
                status=OrderStatus(order_response["status"]),
                filled_amount=order_response.get("filled", 0),
                filled_price=order_response.get("average", 0),
                fee=0,
            )
            
            self.orders[order.id] = order
            logger.info(f"✅ 订单创建成功 - {order.id} {side.value} {amount} {symbol}")
            
            return order
            
        except Exception as e:
            logger.error(f"❌ 订单创建失败：{e}")
            return None
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消订单"""
        try:
            self.exchange.cancel_order(order_id, symbol)
            if order_id in self.orders:
                self.orders[order_id].status = OrderStatus.CANCELLED
            logger.info(f"✅ 订单已取消 - {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 取消订单失败：{e}")
            return False
    
    def get_order_status(self, order_id: str, symbol: str) -> Optional[Order]:
        """获取订单状态"""
        try:
            order_response = self.exchange.fetch_order(order_id, symbol)
            if order_id in self.orders:
                order = self.orders[order_id]
                order.status = OrderStatus(order_response["status"])
                order.filled_amount = order_response.get("filled", 0)
                order.filled_price = order_response.get("average", 0)
                order.updated_at = datetime.now()
                return order
        except Exception as e:
            logger.error(f"❌ 获取订单状态失败：{e}")
            return None
        return None
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Position]:
        """获取所有持仓"""
        return list(self.positions.values())
    
    def update_positions(self, prices: Dict[str, float]):
        """更新所有持仓的当前价格"""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_price(prices[symbol])
    
    def close_position(
        self,
        symbol: str,
        amount: Optional[float] = None,
    ) -> Optional[Order]:
        """平仓"""
        if symbol not in self.positions:
            logger.warning(f"⚠️  没有 {symbol} 的持仓")
            return None
        
        position = self.positions[symbol]
        
        # 确定平仓方向
        if amount is None:
            amount = position.amount
        
        side = OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY
        
        # 创建平仓订单
        order = self.create_order(
            symbol=symbol,
            side=side,
            amount=amount,
            order_type=OrderType.MARKET,
        )
        
        if order and order.status == OrderStatus.FILLED:
            # 计算已实现盈亏
            pnl = position.unrealized_pnl * (amount / position.amount)
            position.realized_pnl += pnl
            self.capital += pnl
            
            # 更新或移除持仓
            if amount >= position.amount:
                del self.positions[symbol]
            else:
                position.amount -= amount
            
            # 记录交易历史
            self.trade_history.append({
                "symbol": symbol,
                "side": side.value,
                "amount": amount,
                "price": order.filled_price,
                "pnl": pnl,
                "timestamp": datetime.now().isoformat(),
            })
            
            logger.info(f"✅ 平仓成功 - {symbol} 盈亏：${pnl:.2f}")
        
        return order
    
    def get_portfolio_summary(self) -> Dict:
        """获取账户汇总"""
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        total_realized_pnl = sum(p.realized_pnl for p in self.positions.values())
        
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.capital,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "total_pnl": total_unrealized_pnl + total_realized_pnl,
            "total_pnl_pct": (total_unrealized_pnl + total_realized_pnl) / self.initial_capital * 100,
            "open_positions": len(self.positions),
            "total_orders": len(self.orders),
            "trade_count": len(self.trade_history),
        }
