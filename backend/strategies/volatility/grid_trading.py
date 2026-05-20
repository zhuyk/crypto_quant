"""
网格交易策略

核心逻辑:
- 在价格区间内设置等间距网格线
- 价格下穿网格线 → 买入 (逢低买)
- 价格上穿网格线 → 卖出 (逢高卖)
- 适合震荡行情，通过高抛低吸赚取波动收益
- 支持等差网格和等比网格
"""
import pandas as pd
import numpy as np
from typing import Optional, List
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType

logger = logging.getLogger(__name__)


class GridTradingStrategy(Strategy):
    """
    网格交易策略
    
    适用场景: 震荡区间、无明确趋势
    优势: 无需预测方向、自动高抛低吸、适合 24h 加密市场
    风险: 单边行情可能满格亏损
    """
    
    name = "grid_trading"
    category = "volatility"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "网格交易策略 - 区间内自动高抛低吸"
    
    timeframes = ["5m", "15m", "1h"]
    
    params = {
        "grid_type": "arithmetic",  # 网格类型: arithmetic (等差) / geometric (等比)
        "grid_count": 10,           # 网格数量
        "upper_price": 0,           # 网格上界 (0=自动计算)
        "lower_price": 0,           # 网格下界 (0=自动计算)
        "auto_range_period": 48,    # 自动计算区间的回溯周期
        "auto_range_mult": 1.0,     # 区间倍数 (1.0=100% 波动范围)
        "order_size_pct": 0.05,     # 每格下单量占总资金比例
        "stop_loss_pct": 0.15,      # 整体止损 (跌破下界多少平仓)
        "take_profit_pct": 0.10,    # 整体止盈 (突破上界多少平仓)
        "trend_filter": True,       # 趋势过滤 (强趋势中不开网格)
        "trend_ma_period": 100,     # 趋势均线周期
        "max_grids_one_side": 5,    # 单边最大持仓格数
    }
    
    def on_init(self):
        self._grid_levels: List[float] = []
        self._triggered_buy: set = set()   # 已触发买入的网格层
        self._triggered_sell: set = set()  # 已触发卖出的网格层
        self._grid_initialized = False
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """生成网格交易信号"""
        if not self.validate_data(data):
            return None
        
        if len(data) < max(self.params["auto_range_period"], 50):
            return None
        
        high = data["high"]
        low = data["low"]
        close = data["close"]
        
        current_price = close.iloc[-1]
        prev_price = close.iloc[-2]
        symbol = data["symbol"].iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # 初始化网格
        if not self._grid_initialized:
            self._init_grid(high, low, close, current_price)
        
        if not self._grid_levels:
            return None
        
        # 趋势过滤：强趋势时不交易
        if self.params["trend_filter"]:
            ma = close.rolling(self.params["trend_ma_period"]).mean().iloc[-1]
            deviation = abs(current_price - ma) / ma
            if deviation > 0.08:  # 偏离均线 8% 以上视为强趋势
                return None
        
        # 检查整体止损/止盈
        grid_lower = self._grid_levels[0]
        grid_upper = self._grid_levels[-1]
        
        # 止损：跌破下界
        if current_price < grid_lower * (1 - self.params["stop_loss_pct"]):
            if self._positions:
                self._reset_grid()
                return Signal(
                    symbol=symbol,
                    side=SignalSide.CLOSE,
                    signal_type=SignalType.EXIT,
                    price=current_price,
                    strength=0.9,
                    metadata={"signal_reason": "grid_stop_loss", "grid_lower": grid_lower},
                )
        
        # 止盈：突破上界
        if current_price > grid_upper * (1 + self.params["take_profit_pct"]):
            if self._positions:
                self._reset_grid()
                return Signal(
                    symbol=symbol,
                    side=SignalSide.CLOSE,
                    signal_type=SignalType.EXIT,
                    price=current_price,
                    strength=0.9,
                    metadata={"signal_reason": "grid_take_profit", "grid_upper": grid_upper},
                )
        
        # === 网格买卖逻辑 ===
        for i, level in enumerate(self._grid_levels):
            grid_id = f"grid_{i}"
            
            # 价格从上方穿越网格线 → 买入信号
            if prev_price > level >= current_price:
                if grid_id not in self._triggered_buy:
                    # 检查单边持仓限制
                    if len(self._triggered_buy) >= self.params["max_grids_one_side"]:
                        continue
                    
                    self._triggered_buy.add(grid_id)
                    self._triggered_sell.discard(grid_id)  # 清除对应卖出标记
                    
                    strength = self._calc_grid_strength(current_price, level, i, len(self._grid_levels))
                    
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.LONG,
                        signal_type=SignalType.ENTRY,
                        price=current_price,
                        stop_loss=grid_lower * (1 - self.params["stop_loss_pct"]),
                        take_profit=self._grid_levels[min(i + 2, len(self._grid_levels) - 1)],
                        strength=strength,
                        metadata={
                            "grid_level": round(level, 4),
                            "grid_index": i,
                            "grid_count": len(self._grid_levels),
                            "signal_reason": "grid_buy",
                            "active_buy_grids": len(self._triggered_buy),
                        },
                    )
            
            # 价格从下方穿越网格线 → 卖出信号
            elif prev_price < level <= current_price:
                if grid_id not in self._triggered_sell:
                    if len(self._triggered_sell) >= self.params["max_grids_one_side"]:
                        continue
                    
                    self._triggered_sell.add(grid_id)
                    self._triggered_buy.discard(grid_id)
                    
                    strength = self._calc_grid_strength(current_price, level, i, len(self._grid_levels))
                    
                    # 如果有多头持仓则平仓，否则做空
                    side = SignalSide.CLOSE if self._positions else SignalSide.SHORT
                    sig_type = SignalType.EXIT if self._positions else SignalType.ENTRY
                    
                    return Signal(
                        symbol=symbol,
                        side=side,
                        signal_type=sig_type,
                        price=current_price,
                        stop_loss=grid_upper * (1 + self.params["stop_loss_pct"]),
                        take_profit=self._grid_levels[max(i - 2, 0)],
                        strength=strength,
                        metadata={
                            "grid_level": round(level, 4),
                            "grid_index": i,
                            "grid_count": len(self._grid_levels),
                            "signal_reason": "grid_sell",
                            "active_sell_grids": len(self._triggered_sell),
                        },
                    )
        
        return None
    
    def _init_grid(self, high: pd.Series, low: pd.Series, close: pd.Series, current_price: float):
        """初始化网格线"""
        upper = self.params["upper_price"]
        lower = self.params["lower_price"]
        
        # 自动计算网格区间
        if upper <= 0 or lower <= 0:
            period = self.params["auto_range_period"]
            recent_high = high.iloc[-period:].max()
            recent_low = low.iloc[-period:].min()
            
            # 扩展区间
            range_size = (recent_high - recent_low) * self.params["auto_range_mult"]
            center = (recent_high + recent_low) / 2
            
            upper = center + range_size / 2
            lower = center - range_size / 2
        
        if upper <= lower:
            logger.warning("网格上下界无效")
            return
        
        # 生成网格线
        grid_count = self.params["grid_count"]
        
        if self.params["grid_type"] == "geometric":
            # 等比网格
            ratio = (upper / lower) ** (1 / grid_count)
            self._grid_levels = [lower * (ratio ** i) for i in range(grid_count + 1)]
        else:
            # 等差网格
            step = (upper - lower) / grid_count
            self._grid_levels = [lower + step * i for i in range(grid_count + 1)]
        
        self._grid_initialized = True
        self._triggered_buy.clear()
        self._triggered_sell.clear()
        
        logger.info(
            f"📊 网格初始化完成 | 类型={self.params['grid_type']} | "
            f"区间=[{lower:.2f}, {upper:.2f}] | "
            f"格数={grid_count} | 步长={self._grid_levels[1] - self._grid_levels[0]:.4f}"
        )
    
    def _reset_grid(self):
        """重置网格状态"""
        self._grid_initialized = False
        self._grid_levels.clear()
        self._triggered_buy.clear()
        self._triggered_sell.clear()
    
    @staticmethod
    def _calc_grid_strength(price: float, level: float, idx: int, total: int) -> float:
        """
        计算网格信号强度
        
        越靠近网格边缘强度越高（因为反弹空间更大）
        """
        # 靠近边缘的信号更强
        position_ratio = idx / total  # 0=底部, 1=顶部
        
        # 买入信号：越低越强
        if price <= level:
            edge_score = 1 - position_ratio
        else:
            edge_score = position_ratio
        
        # 穿越精度
        precision = 1 - min(abs(price - level) / level, 0.01) * 100
        
        return min(edge_score * 0.6 + precision * 0.4, 1.0)
