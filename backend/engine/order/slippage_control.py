"""
滑点控制 - 减少交易滑点损失
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SlippageMode(Enum):
    """滑点控制模式"""
    NONE = "none"           # 无控制
    PERCENTAGE = "percentage"  # 百分比限制
    FIXED = "fixed"         # 固定金额限制
    DYNAMIC = "dynamic"     # 动态调整


@dataclass
class SlippageConfig:
    """
    滑点配置
    
    Attributes:
        mode: 滑点控制模式
        max_slippage_pct: 最大滑点百分比 (0-1)
        max_slippage_fixed: 最大滑点固定金额
        price_improvement_ratio: 价格改善比例要求
        enable_dynamic: 是否启用动态调整
    """
    mode: SlippageMode = SlippageMode.PERCENTAGE
    max_slippage_pct: float = 0.001  # 0.1%
    max_slippage_fixed: float = 0.0
    price_improvement_ratio: float = 0.5
    enable_dynamic: bool = True


class SlippageController:
    """
    滑点控制器
    
    监控和控制交易滑点，优化成交价格
    """
    
    def __init__(self, config: Optional[SlippageConfig] = None):
        """
        Args:
            config: 滑点配置
        """
        self.config = config or SlippageConfig()
        
        # 历史滑点统计
        self._slippage_history: list[float] = []
        self._total_slippage_cost = Decimal('0')
        self._trade_count = 0
        
        # 动态调整参数
        self._recent_slippage_avg = 0.0
        self._volatility_factor = 1.0
    
    def check_slippage(
        self,
        expected_price: Decimal,
        actual_price: Decimal,
        side: str,
        quantity: Decimal
    ) -> Tuple[bool, float, Decimal]:
        """
        检查滑点是否在可接受范围内
        
        Args:
            expected_price: 预期价格
            actual_price: 实际成交价格
            side: 买卖方向
            quantity: 数量
            
        Returns:
            (是否可接受，滑点百分比，滑点成本)
        """
        if expected_price <= 0:
            return True, 0.0, Decimal('0')
        
        # 计算滑点
        if side == "buy":
            # 买入：实际价格高于预期价格为负滑点
            slippage = (actual_price - expected_price) / expected_price
        else:
            # 卖出：实际价格低于预期价格为负滑点
            slippage = (expected_price - actual_price) / expected_price
        
        slippage_pct = float(slippage)
        slippage_cost = abs(slippage * quantity * expected_price)
        
        # 记录历史
        self._slippage_history.append(slippage_pct)
        self._total_slippage_cost += slippage_cost
        self._trade_count += 1
        
        # 检查是否超限
        is_acceptable = self._is_acceptable_slippage(slippage_pct)
        
        if not is_acceptable:
            logger.warning(
                f"滑点超限：{slippage_pct:.4%} "
                f"(预期：{expected_price}, 实际：{actual_price})"
            )
        
        return is_acceptable, slippage_pct, slippage_cost
    
    def _is_acceptable_slippage(self, slippage_pct: float) -> bool:
        """
        判断滑点是否可接受
        
        Args:
            slippage_pct: 滑点百分比
            
        Returns:
            bool: 是否可接受
        """
        if self.config.mode == SlippageMode.NONE:
            return True
        
        if self.config.mode == SlippageMode.PERCENTAGE:
            return abs(slippage_pct) <= self.config.max_slippage_pct
        
        if self.config.mode == SlippageMode.DYNAMIC:
            # 动态调整阈值
            dynamic_threshold = self._calculate_dynamic_threshold()
            return abs(slippage_pct) <= dynamic_threshold
        
        return True
    
    def _calculate_dynamic_threshold(self) -> float:
        """
        计算动态滑点阈值
        
        基于历史滑点和市场波动率调整
        
        Returns:
            float: 动态阈值
        """
        if not self.config.enable_dynamic or len(self._slippage_history) < 5:
            return self.config.max_slippage_pct
        
        # 计算近期平均滑点
        recent = self._slippage_history[-10:]
        self._recent_slippage_avg = sum(recent) / len(recent)
        
        # 计算滑点波动率
        variance = sum((s - self._recent_slippage_avg) ** 2 for s in recent) / len(recent)
        self._volatility_factor = 1.0 + min(variance * 100, 0.5)  # 最多增加 50%
        
        # 动态阈值 = 基础阈值 × 波动率因子
        dynamic_threshold = self.config.max_slippage_pct * self._volatility_factor
        
        return dynamic_threshold
    
    def get_optimal_limit_price(
        self,
        current_price: Decimal,
        side: str,
        urgency: float = 0.5
    ) -> Decimal:
        """
        计算最优限价单价格
        
        Args:
            current_price: 当前市场价格
            side: 买卖方向
            urgency: 紧急程度 (0-1, 1 最紧急)
            
        Returns:
            Decimal: 最优限价
        """
        if self.config.mode == SlippageMode.NONE:
            return current_price
        
        # 基础滑点容忍度
        base_slippage = Decimal(str(self.config.max_slippage_pct))
        
        # 根据紧急程度调整
        urgency_factor = Decimal(str(0.5 + urgency * 0.5))  # 0.5-1.0
        
        if side == "buy":
            # 买入：设置略高于市价的限价，增加成交概率
            limit_price = current_price * (1 + base_slippage * urgency_factor)
        else:
            # 卖出：设置略低于市价的限价，增加成交概率
            limit_price = current_price * (1 - base_slippage * urgency_factor)
        
        return limit_price.quantize(Decimal('0.00000001'))
    
    def get_statistics(self) -> dict:
        """获取滑点统计"""
        avg_slippage = sum(self._slippage_history) / len(self._slippage_history) if self._slippage_history else 0.0
        max_slippage = max(self._slippage_history) if self._slippage_history else 0.0
        min_slippage = min(self._slippage_history) if self._slippage_history else 0.0
        
        return {
            "trade_count": self._trade_count,
            "total_slippage_cost": str(self._total_slippage_cost),
            "avg_slippage_pct": f"{avg_slippage:.4%}",
            "max_slippage_pct": f"{max_slippage:.4%}",
            "min_slippage_pct": f"{min_slippage:.4%}",
            "recent_avg_slippage": f"{self._recent_slippage_avg:.4%}",
            "volatility_factor": f"{self._volatility_factor:.2f}",
            "config": {
                "mode": self.config.mode.value,
                "max_slippage_pct": f"{self.config.max_slippage_pct:.4%}",
                "enable_dynamic": self.config.enable_dynamic,
            }
        }
    
    def reset(self):
        """重置统计"""
        self._slippage_history.clear()
        self._total_slippage_cost = Decimal('0')
        self._trade_count = 0
        self._recent_slippage_avg = 0.0
        self._volatility_factor = 1.0
