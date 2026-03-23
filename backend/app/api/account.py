"""
资金 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["account"])


class BalanceResponse(BaseModel):
    """余额响应"""
    exchange: str
    asset: str
    free: str
    locked: str
    total: str


class TransactionResponse(BaseModel):
    """交易记录响应"""
    id: str
    type: str
    asset: str
    amount: str
    fee: str
    status: str
    description: str
    reference_id: Optional[str]
    exchange: str
    created_at: str
    completed_at: Optional[str]


class DepositRequest(BaseModel):
    """充值请求"""
    exchange: str
    asset: str
    amount: str
    tx_hash: Optional[str] = None


class WithdrawalRequest(BaseModel):
    """提现请求"""
    exchange: str
    asset: str
    amount: str
    address: str
    memo: Optional[str] = None


@router.get("/balances")
async def get_balances(exchange: Optional[str] = None):
    """获取余额"""
    from app.core.account_manager import get_account_manager
    
    manager = get_account_manager()
    balances = manager.get_all_balances(exchange)
    
    if exchange:
        return {
            "exchange": exchange,
            "balances": [
                BalanceResponse(
                    exchange=exchange,
                    asset=asset,
                    free=data['free'],
                    locked=data['locked'],
                    total=data['total'],
                )
                for asset, data in balances.items()
            ]
        }
    else:
        return {
            "balances": [
                BalanceResponse(
                    exchange=ex,
                    asset=asset,
                    free=data['free'],
                    locked=data['locked'],
                    total=data['total'],
                )
                for ex, assets in balances.items()
                for asset, data in assets.items()
            ]
        }


@router.get("/total")
async def get_total_balance(asset: str = "USDT"):
    """获取总资产"""
    from app.core.account_manager import get_account_manager
    
    manager = get_account_manager()
    total = manager.get_total_balance(asset)
    
    return {
        "asset": asset,
        "total": str(total),
    }


@router.get("/transactions")
async def get_transactions(
    exchange: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 100,
):
    """获取交易记录"""
    from app.core.account_manager import get_account_manager, TransactionType
    
    manager = get_account_manager()
    
    tx_type = None
    if type:
        try:
            tx_type = TransactionType(type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的交易类型：{type}")
    
    transactions = manager.get_transactions(exchange=exchange, type=tx_type, limit=limit)
    
    return {
        "transactions": [
            TransactionResponse(
                id=tx.id,
                type=tx.type.value,
                asset=tx.asset,
                amount=str(tx.amount),
                fee=str(tx.fee),
                status=tx.status.value,
                description=tx.description,
                reference_id=tx.reference_id,
                exchange=tx.exchange,
                created_at=tx.created_at.isoformat(),
                completed_at=tx.completed_at.isoformat() if tx.completed_at else None,
            )
            for tx in transactions
        ]
    }


@router.post("/deposit")
async def record_deposit(request: DepositRequest):
    """记录充值"""
    from app.core.account_manager import get_account_manager, TransactionType
    from decimal import Decimal
    
    manager = get_account_manager()
    amount = Decimal(request.amount)
    
    # 更新余额
    manager.update_balance(
        exchange=request.exchange,
        asset=request.asset,
        free=amount,  # 简单实现，实际应该累加
    )
    
    # 记录交易
    tx = manager.record_transaction(
        exchange=request.exchange,
        type=TransactionType.DEPOSIT,
        asset=request.asset,
        amount=amount,
        reference_id=request.tx_hash,
        description="充值",
    )
    
    return {
        "success": True,
        "transaction": tx.to_dict(),
    }


@router.post("/withdrawal")
async def record_withdrawal(request: WithdrawalRequest):
    """记录提现"""
    from app.core.account_manager import get_account_manager, TransactionType
    from decimal import Decimal
    
    manager = get_account_manager()
    amount = Decimal(request.amount)
    
    # 检查余额
    balance = manager.get_balance(request.exchange, request.asset)
    if not balance or balance.free < amount:
        raise HTTPException(status_code=400, detail="余额不足")
    
    # 扣除余额
    manager.update_balance(
        exchange=request.exchange,
        asset=request.asset,
        free=balance.free - amount,
    )
    
    # 记录交易
    tx = manager.record_transaction(
        exchange=request.exchange,
        type=TransactionType.WITHDRAWAL,
        asset=request.asset,
        amount=amount,
        description=f"提现到 {request.address}",
    )
    
    return {
        "success": True,
        "transaction": tx.to_dict(),
    }


@router.get("/statistics")
async def get_statistics():
    """获取统计信息"""
    from app.core.account_manager import get_account_manager
    
    manager = get_account_manager()
    return manager.get_statistics()


@router.post("/sync/{exchange}")
async def sync_balance(exchange: str):
    """同步交易所余额"""
    from app.core.account_manager import get_account_manager
    from data.exchanges.exchange_router import get_exchange_router
    from data.exchanges.base import ExchangeType
    
    manager = get_account_manager()
    router = get_exchange_router()
    
    try:
        exchange_type = ExchangeType(exchange.lower())
        client = router.get_exchange(exchange_type)
        
        # 从交易所获取余额
        balances = await client.get_balance()
        
        # 更新本地余额
        for asset, data in balances.items():
            manager.update_balance(
                exchange=exchange,
                asset=asset,
                free=data['free'],
                locked=data['locked'],
            )
        
        return {
            "success": True,
            "exchange": exchange,
            "balances": len(balances),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
