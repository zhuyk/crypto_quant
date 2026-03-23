"""
社交跟单 API 路由
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import logging

from app.core.auth.auth_middleware import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["social"])


class FollowRequest(BaseModel):
    """关注请求"""
    trader_id: str
    amount: Optional[float] = None


class TraderInfo(BaseModel):
    """交易员信息"""
    trader_id: str
    username: str
    total_return: float
    sharpe_ratio: float
    win_rate: float
    follower_count: int
    avatar: Optional[str] = None


@router.get("/social/leaderboard")
async def get_leaderboard(
    request: Request,
    sort_by: str = "total_return",
    time_period: str = "all",
    limit: int = 50,
):
    """获取交易员排行榜"""
    # 模拟数据
    traders = [
        {
            "trader_id": "trader_001",
            "username": "CryptoKing",
            "total_return": 156.8,
            "sharpe_ratio": 2.3,
            "win_rate": 68.5,
            "follower_count": 1234,
            "avatar": None,
        },
        {
            "trader_id": "trader_002",
            "username": "BTCMaster",
            "total_return": 124.3,
            "sharpe_ratio": 1.9,
            "win_rate": 62.1,
            "follower_count": 987,
            "avatar": None,
        },
        {
            "trader_id": "trader_003",
            "username": "EthWhale",
            "total_return": 98.7,
            "sharpe_ratio": 1.7,
            "win_rate": 59.3,
            "follower_count": 756,
            "avatar": None,
        },
    ]
    
    # 排序
    if sort_by == "total_return":
        traders.sort(key=lambda x: x["total_return"], reverse=True)
    elif sort_by == "sharpe_ratio":
        traders.sort(key=lambda x: x["sharpe_ratio"], reverse=True)
    elif sort_by == "win_rate":
        traders.sort(key=lambda x: x["win_rate"], reverse=True)
    elif sort_by == "follower_count":
        traders.sort(key=lambda x: x["follower_count"], reverse=True)
    
    return {
        "traders": traders[:limit],
        "total": len(traders),
    }


@router.get("/social/my-followings")
async def get_my_followings(request: Request):
    """获取我的关注列表"""
    user_info = await require_auth(request)
    
    # 返回空列表（暂未实现）
    return {
        "followings": [],
        "total": 0,
    }


@router.post("/social/follow")
async def follow_trader(request: FollowRequest, req: Request):
    """关注交易员"""
    user_info = await require_auth(req)
    
    logger.info(f"用户 {user_info['username']} 关注交易员 {request.trader_id}")
    
    return {
        "success": True,
        "message": "关注成功",
    }


@router.post("/social/unfollow/{trader_id}")
async def unfollow_trader(trader_id: str, request: Request):
    """取消关注交易员"""
    user_info = await require_auth(request)
    
    logger.info(f"用户 {user_info['username']} 取消关注交易员 {trader_id}")
    
    return {
        "success": True,
        "message": "取消关注成功",
    }


@router.get("/social/portfolios")
async def get_portfolios(
    request: Request,
    trader_id: Optional[str] = None,
    limit: int = 20,
):
    """获取投资组合"""
    # 模拟数据
    portfolios = [
        {
            "portfolio_id": "pf_001",
            "trader_id": "trader_001",
            "trader_name": "CryptoKing",
            "total_value": 125000.0,
            "daily_pnl": 2.3,
            "total_pnl": 156.8,
            "positions": [
                {"symbol": "BTCUSDT", "side": "long", "size": 1.5},
                {"symbol": "ETHUSDT", "side": "long", "size": 10.0},
            ],
        },
    ]
    
    return {
        "portfolios": portfolios[:limit],
        "total": len(portfolios),
    }
