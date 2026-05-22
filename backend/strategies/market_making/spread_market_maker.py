"""
价差做市策略

核心逻辑:
- 在买卖盘口两侧同时挂限价单，赚取 Bid-Ask Spread
- 动态调整报价距离：波动率高时加宽价差，低时收紧
- 库存管理：持仓偏离中性时调整报价偏移 (Inventory Skew)
- 风控：最大持仓上限、单边暴露限制、快速撤单机制
- 适合流动性好、波动适中的交易对
"""
import pandas as pd
import numpy as np
from typing import Optional
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType

logger = logging.getLogger(__name__)


class SpreadMarketMakerStrategy(Strategy):
    """
    价差做市策略
    
    适用场景: 流动性充足的主流交易对 (BTC/ETH)、震荡行情
    收益来源: Bid-Ask Spread + 网格利润
    风险: 单边行情库存积压、极端波动穿仓
    """
    
    name = "spread_market_maker"
    category = "market_making"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "价差做市策略 - 双边挂单赚取价差"
    
    timeframes = ["1m", "5m", "15m"]
    
    params = {
        # 报价参数
        "base_spread_pct": 0.002,       # 基础价差 (0.2%)
        "min_spread_pct": 0.001,        # 最小价差
        "max_spread_pct": 0.01,         # 最大价差
        "order_levels": 3,              # 每侧挂单层数
        "level_spacing_pct": 0.001,     # 层间距
        
        # 波动率自适应
        "volatility_period": 20,        # 波动率计算周期
        "volatility_mult": 2.0,         # 波动率 → 价差映射系数
        
        # 库存管理
        "max_inventory": 5.0,           # 最大库存 (单位数量)
        "inventory_skew_factor": 0.5,   # 库存偏斜系数 (0=不偏斜, 1=全偏斜)
        "target_inventory": 0.0,        # 目标库存 (0=中性)
        
        # 风控
        "max_position_value_pct": 0.1,  # 最大持仓价值占资金比例
        "stop_loss_pct": 0.05,          # 整体止损
        "pause_on_trend": True,         # 强趋势暂停做市
        "trend_threshold": 0.03,        # 趋势阈值 (价格偏离MA的比例)
        "trend_ma_period": 50,          # 趋势均线周期
        
        # 重新报价
        "requote_threshold": 0.001,     # 价格变动超过此值则重新报价
    }
    
    def on_init(self):
        self._current_inventory = 0.0   # 当前库存
        self._last_mid_price = None     # 上次中间价
        self._total_trades = 0          # 成交次数
        self._total_spread_earned = 0.0 # 累计赚取价差
        self._is_paused = False         # 是否暂停
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """生成做市信号"""
        if not self.validate_data(data):
            return None
        
        if len(data) < max(self.params["volatility_period"], self.params["trend_ma_period"]) + 5:
            return None
        
        close = data["close"]
        high = data["high"]
        low = data["low"]
        volume = data["volume"]
        
        current_price = close.iloc[-1]
        symbol = data["symbol"].iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # === 趋势检测 - 强趋势暂停 ===
        if self.params["pause_on_trend"]:
            ma = close.rolling(self.params["trend_ma_period"]).mean().iloc[-1]
            price_deviation = (current_price - ma) / ma
            
            if abs(price_deviation) > self.params["trend_threshold"]:
                if not self._is_paused:
                    logger.info(f"⏸️  做市暂停 - 检测到趋势 (偏离={price_deviation:.2%})")
                    self._is_paused = True
                
                # 如果有库存，趋势方向对库存不利则平仓
                if self._current_inventory != 0:
                    inventory_adverse = (
                        (self._current_inventory > 0 and price_deviation < -self.params["trend_threshold"]) or
                        (self._current_inventory < 0 and price_deviation > self.params["trend_threshold"])
                    )
                    if inventory_adverse:
                        return Signal(
                            symbol=symbol,
                            side=SignalSide.CLOSE,
                            signal_type=SignalType.EXIT,
                            price=current_price,
                            strength=0.9,
                            metadata={
                                "signal_reason": "mm_trend_adverse_close",
                                "inventory": self._current_inventory,
                                "price_deviation": round(price_deviation, 4),
                            },
                        )
                return None
            else:
                if self._is_paused:
                    logger.info(f"▶️  做市恢复 - 趋势消退")
                    self._is_paused = False
        
        # === 计算动态价差 ===
        volatility = close.pct_change().rolling(self.params["volatility_period"]).std().iloc[-1]
        
        # 波动率自适应价差
        dynamic_spread = self.params["base_spread_pct"] + volatility * self.params["volatility_mult"]
        dynamic_spread = max(self.params["min_spread_pct"], min(dynamic_spread, self.params["max_spread_pct"]))
        
        # === 库存偏斜 (Inventory Skew) ===
        # 库存多 → 提高卖价/降低买价 (鼓励卖出减库存)
        # 库存空 → 降低卖价/提高买价 (鼓励买入增库存)
        inventory_ratio = self._current_inventory / self.params["max_inventory"] if self.params["max_inventory"] > 0 else 0
        skew = inventory_ratio * self.params["inventory_skew_factor"] * dynamic_spread
        
        # 计算买卖报价
        mid_price = current_price
        bid_price = mid_price * (1 - dynamic_spread / 2) - skew * mid_price
        ask_price = mid_price * (1 + dynamic_spread / 2) - skew * mid_price
        
        self._last_mid_price = mid_price
        
        # === 检查是否需要重新报价 ===
        # (在回测中模拟：价格穿越了我们的报价)
        
        # 价格下跌触及买价 → 买入信号
        if low.iloc[-1] <= bid_price and self._current_inventory < self.params["max_inventory"]:
            self._current_inventory += 1
            self._total_trades += 1
            
            # 止损
            stop_loss = bid_price * (1 - self.params["stop_loss_pct"])
            # 目标卖价
            take_profit = ask_price
            
            strength = self._calc_strength(volatility, volume, abs(inventory_ratio))
            
            return Signal(
                symbol=symbol,
                side=SignalSide.LONG,
                signal_type=SignalType.ENTRY,
                price=bid_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strength=strength,
                metadata={
                    "signal_reason": "mm_bid_fill",
                    "bid_price": round(bid_price, 4),
                    "ask_price": round(ask_price, 4),
                    "spread_pct": round(dynamic_spread * 100, 3),
                    "inventory": self._current_inventory,
                    "skew": round(skew, 6),
                    "volatility": round(volatility, 6),
                },
            )
        
        # 价格上涨触及卖价 → 卖出信号
        elif high.iloc[-1] >= ask_price and self._current_inventory > -self.params["max_inventory"]:
            self._current_inventory -= 1
            self._total_trades += 1
            self._total_spread_earned += dynamic_spread * mid_price
            
            stop_loss = ask_price * (1 + self.params["stop_loss_pct"])
            take_profit = bid_price
            
            strength = self._calc_strength(volatility, volume, abs(inventory_ratio))
            
            # 如果有多头库存则平仓，否则开空
            if self._current_inventory >= 0 and self._positions:
                side = SignalSide.CLOSE
                sig_type = SignalType.EXIT
            else:
                side = SignalSide.SHORT
                sig_type = SignalType.ENTRY
            
            return Signal(
                symbol=symbol,
                side=side,
                signal_type=sig_type,
                price=ask_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strength=strength,
                metadata={
                    "signal_reason": "mm_ask_fill",
                    "bid_price": round(bid_price, 4),
                    "ask_price": round(ask_price, 4),
                    "spread_pct": round(dynamic_spread * 100, 3),
                    "inventory": self._current_inventory,
                    "skew": round(skew, 6),
                    "spread_earned_total": round(self._total_spread_earned, 2),
                },
            )
        
        return None
    
    def _calc_strength(self, volatility: float, volume: pd.Series, inv_ratio: float) -> float:
        """
        计算信号强度
        
        做市信号强度取决于:
        1. 价差空间（波动率越大越好）
        2. 成交量（流动性越好越好）
        3. 库存健康度（库存越中性越好）
        """
        # 1. 波动率 → 价差空间
        vol_score = min(volatility * 100, 1.0)  # 归一化
        
        # 2. 流动性
        avg_vol = volume.rolling(20).mean().iloc[-1]
        current_vol = volume.iloc[-1]
        liquidity_score = min(current_vol / avg_vol, 1.0) if avg_vol > 0 else 0.5
        
        # 3. 库存健康度 (越中性越好)
        inventory_score = 1.0 - min(inv_ratio, 1.0)
        
        return min(vol_score * 0.3 + liquidity_score * 0.3 + inventory_score * 0.4, 1.0)
    
    def get_metadata(self) -> dict:
        """获取策略元数据 (含做市专属统计)"""
        base = super().get_metadata()
        base["mm_stats"] = {
            "current_inventory": self._current_inventory,
            "total_trades": self._total_trades,
            "total_spread_earned": round(self._total_spread_earned, 2),
            "is_paused": self._is_paused,
        }
        return base
