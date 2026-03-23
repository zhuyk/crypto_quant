"""
交易所 API Key 管理 API
"""

from fastapi import APIRouter, HTTPException, status, Request
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from ..core.auth.auth_middleware import get_current_user_from_request
from ..core.auth.user_manager import get_user_manager
from ..core.exchange_key_manager import get_exchange_key_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/exchange-keys", tags=["交易所 API Key"])


def get_current_user_or_401(request: Request) -> dict:
    """获取当前用户，未登录时抛出 401"""
    user_info = get_current_user_from_request(request)
    if not user_info:
        raise HTTPException(status_code=401, detail="未授权访问，请先登录")
    return user_info


class ExchangeKeyCreate(BaseModel):
    """创建交易所 API Key 请求"""
    exchange: str = Field(..., description="交易所名称：binance/okx/bybit/htx")
    name: str = Field(..., description="名称，例如：主账户交易 Key")
    api_key: str = Field(..., description="API Key")
    api_secret: str = Field(..., description="API Secret")
    passphrase: Optional[str] = Field(None, description="API Passphrase（OKX/Bybit 需要）")
    permissions: List[str] = Field(default_factory=lambda: ["trade", "read"], description="权限列表")
    is_testnet: bool = Field(False, description="是否测试网")


class ExchangeKeyUpdate(BaseModel):
    """更新交易所 API Key 请求"""
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class ExchangeKeyResponse(BaseModel):
    """交易所 API Key 响应"""
    id: str
    user_id: str
    exchange: str
    name: str
    api_key_prefix: str
    permissions: List[str]
    is_active: bool
    is_testnet: bool
    created_at: datetime
    updated_at: datetime
    last_used: Optional[datetime] = None


@router.post("", response_model=ExchangeKeyResponse, summary="添加交易所 API Key")
async def create_exchange_key(request: Request, data: ExchangeKeyCreate):
    """添加新的交易所 API Key"""
    user_info = get_current_user_or_401(request)
    manager = get_exchange_key_manager()
    
    if not data.api_key or not data.api_secret:
        raise HTTPException(status_code=400, detail="API Key 和 Secret 不能为空")
    
    try:
        key_id = manager.create_key(
            user_id=user_info["user_id"],
            exchange=data.exchange,
            name=data.name,
            api_key=data.api_key,
            api_secret=data.api_secret,
            passphrase=data.passphrase,
            permissions=data.permissions,
            is_testnet=data.is_testnet,
        )
        
        key_data = manager.get_key(key_id, user_info["user_id"])
        if not key_data:
            raise HTTPException(status_code=500, detail="创建失败")
        
        return ExchangeKeyResponse(**key_data)
        
    except Exception as e:
        logger.error(f"创建交易所 API Key 失败：{e}")
        raise HTTPException(status_code=500, detail=f"创建失败：{str(e)}")


@router.get("", response_model=List[ExchangeKeyResponse], summary="获取交易所 API Key 列表")
async def get_exchange_keys(request: Request, exchange: Optional[str] = None):
    """获取当前用户的所有交易所 API Key"""
    user_info = get_current_user_or_401(request)
    manager = get_exchange_key_manager()
    
    keys = manager.list_keys(user_info["user_id"], exchange)
    return [ExchangeKeyResponse(**key) for key in keys]


@router.get("/{key_id}", response_model=ExchangeKeyResponse, summary="获取交易所 API Key 详情")
async def get_exchange_key(request: Request, key_id: str):
    """获取指定交易所 API Key 的详情"""
    user_info = get_current_user_or_401(request)
    manager = get_exchange_key_manager()
    
    key_data = manager.get_key(key_id, user_info["user_id"])
    if not key_data:
        raise HTTPException(status_code=404, detail="API Key 不存在或无权访问")
    
    return ExchangeKeyResponse(**key_data)


@router.put("/{key_id}", response_model=ExchangeKeyResponse, summary="更新交易所 API Key")
async def update_exchange_key(request: Request, key_id: str, data: ExchangeKeyUpdate):
    """更新交易所 API Key 配置"""
    user_info = get_current_user_or_401(request)
    manager = get_exchange_key_manager()
    
    existing = manager.get_key(key_id, user_info["user_id"])
    if not existing:
        raise HTTPException(status_code=404, detail="API Key 不存在或无权访问")
    
    try:
        update_data = data.dict(exclude_unset=True)
        manager.update_key(key_id, user_info["user_id"], **update_data)
        
        key_data = manager.get_key(key_id, user_info["user_id"])
        return ExchangeKeyResponse(**key_data)
        
    except Exception as e:
        logger.error(f"更新交易所 API Key 失败：{e}")
        raise HTTPException(status_code=500, detail=f"更新失败：{str(e)}")


@router.delete("/{key_id}", summary="删除交易所 API Key")
async def delete_exchange_key(request: Request, key_id: str):
    """删除交易所 API Key（软删除，标记为 inactive）"""
    user_info = get_current_user_or_401(request)
    manager = get_exchange_key_manager()
    
    existing = manager.get_key(key_id, user_info["user_id"])
    if not existing:
        raise HTTPException(status_code=404, detail="API Key 不存在或无权访问")
    
    try:
        manager.delete_key(key_id, user_info["user_id"])
        return {"message": "API Key 已删除"}
        
    except Exception as e:
        logger.error(f"删除交易所 API Key 失败：{e}")
        raise HTTPException(status_code=500, detail=f"删除失败：{str(e)}")


@router.post("/{key_id}/test", summary="测试交易所 API Key 连接")
async def test_exchange_key(request: Request, key_id: str):
    """测试交易所 API Key 是否可用"""
    user_info = get_current_user_or_401(request)
    manager = get_exchange_key_manager()
    
    key_data = manager.get_key(key_id, user_info["user_id"])
    if not key_data:
        raise HTTPException(status_code=404, detail="API Key 不存在或无权访问")
    
    try:
        result = await manager.test_connection(key_id, user_info["user_id"])
        return {
            "success": result["success"],
            "message": result.get("message", ""),
            "balance": result.get("balance"),
        }
        
    except Exception as e:
        logger.error(f"测试交易所 API Key 失败：{e}")
        return {"success": False, "message": str(e)}


@router.get("/stats/summary", summary="获取交易所 API Key 统计")
async def get_exchange_keys_summary(request: Request):
    """获取当前用户的交易所 API Key 统计信息"""
    user_info = get_current_user_or_401(request)
    manager = get_exchange_key_manager()
    
    stats = manager.get_user_stats(user_info["user_id"])
    return stats
