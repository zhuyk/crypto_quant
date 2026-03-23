"""
策略 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

from strategies.base import Strategy
from strategies.trend.ma_cross import MACrossStrategy

logger = logging.getLogger(__name__)

router = APIRouter(tags=["策略"])


class StrategyInfo(BaseModel):
    """策略信息"""
    name: str
    category: str
    version: str
    author: str
    description: str
    timeframes: List[str]
    params: Dict[str, Any]


class StrategyListResponse(BaseModel):
    """策略列表响应"""
    strategies: List[StrategyInfo]


@router.get("/list", response_model=StrategyListResponse)
async def list_strategies():
    """获取所有可用策略"""
    # 注册所有策略
    available_strategies: List[type] = [
        MACrossStrategy,
        # TODO: 添加更多策略
    ]
    
    strategies = []
    for strategy_class in available_strategies:
        # 创建临时实例获取元数据
        temp_instance = strategy_class()
        strategies.append(StrategyInfo(
            name=temp_instance.name,
            category=temp_instance.category,
            version=temp_instance.version,
            author=temp_instance.author,
            description=temp_instance.description,
            timeframes=temp_instance.timeframes,
            params=temp_instance.params,
        ))
    
    return StrategyListResponse(strategies=strategies)


@router.get("/{strategy_name}")
async def get_strategy(strategy_name: str):
    """获取策略详情"""
    strategy_class = _get_strategy_class(strategy_name)
    
    if not strategy_class:
        raise HTTPException(status_code=404, detail=f"策略不存在：{strategy_name}")
    
    instance = strategy_class()
    
    return {
        "name": instance.name,
        "category": instance.category,
        "version": instance.version,
        "author": instance.author,
        "description": instance.description,
        "timeframes": instance.timeframes,
        "params": instance.params,
        "metadata": instance.get_metadata(),
    }


@router.post("/{strategy_name}/validate")
async def validate_strategy_params(strategy_name: str, params: Dict[str, Any]):
    """验证策略参数"""
    try:
        strategy_class = _get_strategy_class(strategy_name)
        
        if not strategy_class:
            raise HTTPException(status_code=404, detail=f"策略不存在：{strategy_name}")
        
        # 创建实例测试参数
        instance = strategy_class(params)
        
        # 验证参数
        is_valid = instance._initialized
        
        return {
            "valid": is_valid,
            "params": instance.params,
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
        }


def _get_strategy_class(strategy_name: str) -> Optional[type]:
    """获取策略类"""
    strategies = {
        "ma_cross": MACrossStrategy,
        # TODO: 添加更多策略
    }
    return strategies.get(strategy_name)
