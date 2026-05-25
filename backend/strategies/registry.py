"""
策略注册表 - 自动发现和注册策略
"""
import importlib
import pkgutil
import logging
from typing import Dict, Type, List, Optional
from pathlib import Path

from .base import Strategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    策略注册表
    
    支持：
    - 自动发现策略模块
    - 按名称获取策略类
    - 按分类筛选策略
    """
    
    _instance = None
    _strategies: Dict[str, Type[Strategy]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, strategy_class: Type[Strategy]):
        """注册策略类"""
        name = strategy_class.name
        if name in cls._strategies:
            logger.warning(f"策略 {name} 已被注册，将覆盖")
        cls._strategies[name] = strategy_class
        logger.debug(f"策略已注册：{name} ({strategy_class.__name__})")
    
    @classmethod
    def get(cls, name: str) -> Optional[Type[Strategy]]:
        """获取策略类"""
        return cls._strategies.get(name)
    
    @classmethod
    def create(cls, name: str, params: dict = None) -> Optional[Strategy]:
        """创建策略实例"""
        strategy_class = cls.get(name)
        if strategy_class:
            return strategy_class(params)
        return None
    
    @classmethod
    def list_all(cls) -> Dict[str, Type[Strategy]]:
        """列出所有策略"""
        return cls._strategies.copy()
    
    @classmethod
    def list_by_category(cls, category: str) -> List[Type[Strategy]]:
        """按分类列出策略"""
        return [
            strategy for strategy in cls._strategies.values()
            if strategy.category == category
        ]
    
    @classmethod
    def list_categories(cls) -> List[str]:
        """列出所有策略分类"""
        categories = set(s.category for s in cls._strategies.values())
        return sorted(list(categories))
    
    @classmethod
    def auto_discover(cls, package_name: str = "strategies"):
        """
        自动发现策略模块
        
        Args:
            package_name: 策略包名
        """
        try:
            package = importlib.import_module(package_name)
            package_path = Path(package.__path__[0])
            
            # 遍历所有子模块
            for _, name, is_pkg in pkgutil.iter_modules([str(package_path)]):
                if is_pkg:
                    # 递归发现子包
                    cls.auto_discover(f"{package_name}.{name}")
                else:
                    # 导入模块
                    try:
                        module = importlib.import_module(f"{package_name}.{name}")
                        # 查找模块中的 Strategy 子类
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type) and
                                issubclass(attr, Strategy) and
                                attr is not Strategy and
                                hasattr(attr, "name")
                            ):
                                cls.register(attr)
                    except Exception as e:
                        logger.warning(f"导入模块 {name} 失败：{e}")
        
        except Exception as e:
            logger.error(f"自动发现策略失败：{e}")
    
    @classmethod
    def clear(cls):
        """清空注册表"""
        cls._strategies.clear()


# 创建全局注册表实例
registry = StrategyRegistry()

# 自动发现策略
try:
    registry.auto_discover("strategies")
    logger.info(f"策略自动发现完成，已注册 {len(registry.list_all())} 个策略")
except Exception as e:
    logger.warning(f"策略自动发现失败：{e}")

# 手动注册策略 (确保可靠加载)
try:
    # --- 趋势策略 ---
    from strategies.trend.ma_cross import MACrossStrategy
    from strategies.trend.ma_single import MASingleStrategy
    from strategies.trend.breakout import BreakoutStrategy
    from strategies.trend.macd import MACDStrategy
    
    registry.register(MACrossStrategy)
    registry.register(MASingleStrategy)
    registry.register(BreakoutStrategy)
    registry.register(MACDStrategy)
    
    # --- 均值回归策略 ---
    from strategies.mean_reversion.rsi_reversion import RSIReversionStrategy
    from strategies.mean_reversion.bollinger_bands import BollingerBandsStrategy
    
    registry.register(RSIReversionStrategy)
    registry.register(BollingerBandsStrategy)
    
    # --- 动量策略 ---
    from strategies.momentum.dual_thrust import DualThrustStrategy
    from strategies.momentum.kdj import KDJStrategy
    
    registry.register(DualThrustStrategy)
    registry.register(KDJStrategy)
    
    # --- 波动率策略 ---
    from strategies.volatility.atr_trailing import ATRTrailingStrategy
    from strategies.volatility.grid_trading import GridTradingStrategy
    
    registry.register(ATRTrailingStrategy)
    registry.register(GridTradingStrategy)
    
    # --- 做市策略 ---
    from strategies.market_making.spread_market_maker import SpreadMarketMakerStrategy
    
    registry.register(SpreadMarketMakerStrategy)
    
    # --- 组合策略 ---
    from strategies.composite import PortfolioStrategy, EnsembleStrategy, SectorRotationStrategy
    
    registry.register(PortfolioStrategy)
    registry.register(EnsembleStrategy)
    registry.register(SectorRotationStrategy)
    
    # --- AI 策略 (通过适配器接入) ---
    from ai.strategy_adapter import SentimentStrategyAdapter, EnsemblePredictorAdapter
    
    registry.register(SentimentStrategyAdapter)
    registry.register(EnsemblePredictorAdapter)
    
    logger.info(f"策略手动注册完成，共 {len(registry.list_all())} 个策略")
except Exception as e:
    logger.warning(f"策略手动注册失败：{e}")


# 便捷函数
def get_strategy_class(name: str):
    """获取策略类"""
    return registry.get(name)


def create_strategy(name: str, params: dict = None):
    """创建策略实例"""
    return registry.create(name, params)
