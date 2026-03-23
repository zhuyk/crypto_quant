"""
策略市场 API 路由
"""

from fastapi import APIRouter

router = APIRouter(tags=["策略市场"])

@router.get("/strategies")
async def get_strategies():
    """获取策略列表"""
    return {"strategies": []}

@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """获取策略详情"""
    return {"id": strategy_id, "name": "策略详情"}
