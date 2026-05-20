"""
策略市场 API 路由
"""

from fastapi import APIRouter, HTTPException
from app.core.database import SessionLocal
from app.models.strategy import Strategy

router = APIRouter(tags=["策略市场"])

@router.get("/strategies")
async def get_strategies():
    """获取策略列表"""
    try:
        db = SessionLocal()
        strategies = db.query(Strategy).filter(Strategy.is_active == True).all()
        db.close()
        
        result = []
        for strategy in strategies:
            result.append({
                "id": strategy.id,
                "name": strategy.name,
                "category": strategy.category,
                "description": strategy.description,
                "default_params": strategy.default_params,
            })
        
        return {"strategies": result}
    except Exception as e:
        print(f"Error in get_strategies: {e}")
        raise HTTPException(status_code=500, detail=f"获取策略列表失败: {str(e)}")

@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: int):
    """获取策略详情"""
    try:
        db = SessionLocal()
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        db.close()
        
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        return {
            "id": strategy.id,
            "name": strategy.name,
            "category": strategy.category,
            "description": strategy.description,
            "default_params": strategy.default_params,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_strategy: {e}")
        raise HTTPException(status_code=500, detail=f"获取策略详情失败: {str(e)}")
