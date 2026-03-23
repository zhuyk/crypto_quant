"""
资金管理系统
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from decimal import Decimal
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class TransactionType(Enum):
    """交易类型"""
    DEPOSIT = "deposit"           # 充值
    WITHDRAWAL = "withdrawal"     # 提现
    TRANSFER = "transfer"         # 转账
    TRADE = "trade"               # 交易
    FEE = "fee"                   # 手续费
    PNL = "pnl"                   # 盈亏
    INTEREST = "interest"         # 利息
    REFUND = "refund"             # 退款


class TransactionStatus(Enum):
    """交易状态"""
    PENDING = "pending"       # 待处理
    PROCESSING = "processing" # 处理中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


@dataclass
class Transaction:
    """
    交易记录
    
    Attributes:
        id: 交易 ID
        type: 交易类型
        asset: 币种
        amount: 金额
        fee: 手续费
        status: 状态
        description: 描述
        reference_id: 关联 ID（订单 ID 等）
        created_at: 创建时间
        updated_at: 更新时间
        completed_at: 完成时间
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: TransactionType = TransactionType.TRADE
    asset: str = "USDT"
    amount: Decimal = Decimal('0')
    fee: Decimal = Decimal('0')
    status: TransactionStatus = TransactionStatus.PENDING
    description: str = ""
    reference_id: Optional[str] = None
    exchange: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "asset": self.asset,
            "amount": str(self.amount),
            "fee": str(self.fee),
            "status": self.status.value,
            "description": self.description,
            "reference_id": self.reference_id,
            "exchange": self.exchange,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class AccountBalance:
    """
    账户余额
    
    Attributes:
        asset: 币种
        free: 可用余额
        locked: 冻结金额
        total: 总金额
    """
    asset: str = "USDT"
    free: Decimal = Decimal('0')
    locked: Decimal = Decimal('0')
    
    @property
    def total(self) -> Decimal:
        """总金额"""
        return self.free + self.locked
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "asset": self.asset,
            "free": str(self.free),
            "locked": str(self.locked),
            "total": str(self.total),
        }


class AccountManager:
    """
    账户管理器
    
    管理多交易所、多币种的账户余额和交易记录
    """
    
    def __init__(self):
        """初始化账户管理器"""
        # 余额：{exchange: {asset: AccountBalance}}
        self._balances: Dict[str, Dict[str, AccountBalance]] = {}
        
        # 交易记录：{exchange: [Transaction]}
        self._transactions: Dict[str, List[Transaction]] = {}
        
        # 统计
        self._total_deposits = Decimal('0')
        self._total_withdrawals = Decimal('0')
        self._total_pnl = Decimal('0')
        self._total_fees = Decimal('0')
    
    def init_account(self, exchange: str, initial_balances: Optional[Dict[str, Decimal]] = None):
        """
        初始化账户
        
        Args:
            exchange: 交易所名称
            initial_balances: 初始余额
        """
        if exchange not in self._balances:
            self._balances[exchange] = {}
        
        if exchange not in self._transactions:
            self._transactions[exchange] = []
        
        if initial_balances:
            for asset, amount in initial_balances.items():
                self._balances[exchange][asset] = AccountBalance(
                    asset=asset,
                    free=amount,
                )
        
        logger.info(f"初始化账户：{exchange}, 余额：{initial_balances}")
    
    def update_balance(
        self,
        exchange: str,
        asset: str,
        free: Optional[Decimal] = None,
        locked: Optional[Decimal] = None,
    ):
        """
        更新余额
        
        Args:
            exchange: 交易所
            asset: 币种
            free: 可用余额
            locked: 冻结金额
        """
        if exchange not in self._balances:
            self._balances[exchange] = {}
        
        if asset not in self._balances[exchange]:
            self._balances[exchange][asset] = AccountBalance(asset=asset)
        
        balance = self._balances[exchange][asset]
        
        if free is not None:
            balance.free = free
        if locked is not None:
            balance.locked = locked
        
        balance.updated_at = datetime.utcnow()
    
    def lock_balance(
        self,
        exchange: str,
        asset: str,
        amount: Decimal,
        reason: str = "",
    ) -> bool:
        """
        冻结余额
        
        Args:
            exchange: 交易所
            asset: 币种
            amount: 金额
            reason: 原因
            
        Returns:
            bool: 是否成功
        """
        if exchange not in self._balances:
            return False
        
        if asset not in self._balances[exchange]:
            return False
        
        balance = self._balances[exchange][asset]
        
        if balance.free < amount:
            logger.warning(f"余额不足：{exchange} {asset} {balance.free} < {amount}")
            return False
        
        balance.free -= amount
        balance.locked += amount
        
        logger.info(f"冻结余额：{exchange} {asset} {amount} ({reason})")
        return True
    
    def unlock_balance(
        self,
        exchange: str,
        asset: str,
        amount: Decimal,
        reason: str = "",
    ) -> bool:
        """
        解冻余额
        
        Args:
            exchange: 交易所
            asset: 币种
            amount: 金额
            reason: 原因
            
        Returns:
            bool: 是否成功
        """
        if exchange not in self._balances:
            return False
        
        if asset not in self._balances[exchange]:
            return False
        
        balance = self._balances[exchange][asset]
        
        if balance.locked < amount:
            logger.warning(f"冻结余额不足：{exchange} {asset} {balance.locked} < {amount}")
            return False
        
        balance.locked -= amount
        balance.free += amount
        
        logger.info(f"解冻余额：{exchange} {asset} {amount} ({reason})")
        return True
    
    def record_transaction(
        self,
        exchange: str,
        type: TransactionType,
        asset: str,
        amount: Decimal,
        fee: Decimal = Decimal('0'),
        reference_id: Optional[str] = None,
        description: str = "",
    ) -> Transaction:
        """
        记录交易
        
        Args:
            exchange: 交易所
            type: 交易类型
            asset: 币种
            amount: 金额
            fee: 手续费
            reference_id: 关联 ID
            description: 描述
            
        Returns:
            Transaction: 交易记录
        """
        transaction = Transaction(
            type=type,
            asset=asset,
            amount=amount,
            fee=fee,
            reference_id=reference_id,
            exchange=exchange,
            description=description,
            status=TransactionStatus.COMPLETED,
            completed_at=datetime.utcnow(),
        )
        
        # 保存记录
        if exchange not in self._transactions:
            self._transactions[exchange] = []
        self._transactions[exchange].append(transaction)
        
        # 更新统计
        if type == TransactionType.DEPOSIT:
            self._total_deposits += amount
        elif type == TransactionType.WITHDRAWAL:
            self._total_withdrawals += amount
        elif type == TransactionType.PNL:
            self._total_pnl += amount
        elif type == TransactionType.FEE:
            self._total_fees += fee
        
        logger.info(
            f"记录交易：{exchange} {type.value} {amount} {asset} "
            f"(fee: {fee}, ref: {reference_id})"
        )
        
        return transaction
    
    def get_balance(
        self,
        exchange: str,
        asset: str,
    ) -> Optional[AccountBalance]:
        """获取余额"""
        if exchange not in self._balances:
            return None
        return self._balances[exchange].get(asset)
    
    def get_all_balances(self, exchange: Optional[str] = None) -> Dict[str, dict]:
        """
        获取所有余额
        
        Args:
            exchange: 交易所（可选）
            
        Returns:
            Dict[str, dict]: 余额字典
        """
        if exchange:
            return {
                asset: balance.to_dict()
                for asset, balance in self._balances.get(exchange, {}).items()
            }
        else:
            return {
                ex: {
                    asset: balance.to_dict()
                    for asset, balance in balances.items()
                }
                for ex, balances in self._balances.items()
            }
    
    def get_total_balance(self, asset: str = "USDT") -> Decimal:
        """
        获取总资产（折合指定币种）
        
        Args:
            asset: 折合币种
            
        Returns:
            Decimal: 总资产
        """
        total = Decimal('0')
        for exchange_balances in self._balances.values():
            for balance in exchange_balances.values():
                if balance.asset == asset:
                    total += balance.total
                # TODO: 其他币种需要转换
        return total
    
    def get_transactions(
        self,
        exchange: Optional[str] = None,
        type: Optional[TransactionType] = None,
        limit: int = 100,
    ) -> List[Transaction]:
        """
        获取交易记录
        
        Args:
            exchange: 交易所
            type: 交易类型
            limit: 数量限制
            
        Returns:
            List[Transaction]: 交易记录列表
        """
        results = []
        
        if exchange:
            transactions = self._transactions.get(exchange, [])
        else:
            transactions = []
            for txs in self._transactions.values():
                transactions.extend(txs)
        
        # 筛选类型
        if type:
            transactions = [tx for tx in transactions if tx.type == type]
        
        # 按时间排序
        transactions = sorted(
            transactions,
            key=lambda x: x.created_at,
            reverse=True
        )
        
        return transactions[:limit]
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        return {
            "total_deposits": str(self._total_deposits),
            "total_withdrawals": str(self._total_withdrawals),
            "total_pnl": str(self._total_pnl),
            "total_fees": str(self._total_fees),
            "net_pnl": str(self._total_pnl - self._total_fees),
            "exchanges_count": len(self._balances),
            "total_transactions": sum(len(txs) for txs in self._transactions.values()),
        }


# 全局账户管理器实例
_account_manager: Optional[AccountManager] = None


def get_account_manager() -> AccountManager:
    """获取账户管理器实例"""
    global _account_manager
    if _account_manager is None:
        _account_manager = AccountManager()
    return _account_manager
