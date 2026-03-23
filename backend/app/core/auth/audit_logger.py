"""
审计日志 - 记录所有重要操作
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class AuditAction(Enum):
    """审计操作类型"""
    # 认证相关
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGE = "auth.password_change"
    TWO_FACTOR_ENABLE = "auth.2fa_enable"
    TWO_FACTOR_DISABLE = "auth.2fa_disable"
    
    # 用户管理
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    ROLE_ASSIGN = "user.role_assign"
    ROLE_REVOKE = "user.role_revoke"
    
    # API Key
    API_KEY_CREATE = "apikey.create"
    API_KEY_REVOKE = "apikey.revoke"
    API_KEY_UPDATE = "apikey.update"
    API_KEY_USE = "apikey.use"
    
    # 交易相关
    TRADE_EXECUTE = "trade.execute"
    TRADE_CANCEL = "trade.cancel"
    TRADE_MODIFY = "trade.modify"
    
    # 资金相关
    DEPOSIT = "account.deposit"
    WITHDRAWAL = "account.withdrawal"
    TRANSFER = "account.transfer"
    
    # 策略相关
    STRATEGY_CREATE = "strategy.create"
    STRATEGY_UPDATE = "strategy.update"
    STRATEGY_DELETE = "strategy.delete"
    STRATEGY_START = "strategy.start"
    STRATEGY_STOP = "strategy.stop"
    
    # 系统相关
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_CONFIG_CHANGE = "system.config_change"
    
    # 安全相关
    PERMISSION_DENIED = "security.permission_denied"
    RATE_LIMIT = "security.rate_limit"
    SUSPICIOUS_ACTIVITY = "security.suspicious"


class AuditLevel(Enum):
    """审计级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditRecord:
    """
    审计记录
    
    Attributes:
        id: 记录 ID
        action: 操作类型
        level: 级别
        user_id: 用户 ID
        username: 用户名
        resource: 资源
        resource_id: 资源 ID
        ip_address: IP 地址
        user_agent: User-Agent
        details: 详细信息
        status: 状态（success/failure）
        timestamp: 时间戳
    """
    id: str
    action: AuditAction
    level: AuditLevel = AuditLevel.INFO
    user_id: Optional[str] = None
    username: Optional[str] = None
    resource: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    status: str = "success"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "action": self.action.value,
            "level": self.level.value,
            "user_id": self.user_id,
            "username": self.username,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def to_json(self) -> str:
        """转换为 JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogger:
    """
    审计日志记录器
    
    记录所有重要操作，支持：
    - 异步写入
    - 日志轮转
    - 查询过滤
    - 导出
    """
    
    def __init__(self, max_records: int = 10000):
        """
        Args:
            max_records: 最大保留记录数
        """
        self.max_records = max_records
        
        # 审计记录存储
        self._records: List[AuditRecord] = []
        
        # 索引：{user_id: [record_id]}
        self._user_index: Dict[str, List[str]] = {}
        
        # 索引：{action: [record_id]}
        self._action_index: Dict[str, List[str]] = {}
        
        # 记录 ID 索引
        self._id_index: Dict[str, AuditRecord] = {}
    
    def log(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        level: Optional[AuditLevel] = None,
    ) -> AuditRecord:
        """
        记录审计日志
        
        Args:
            action: 操作类型
            user_id: 用户 ID
            username: 用户名
            resource: 资源
            resource_id: 资源 ID
            ip_address: IP 地址
            details: 详细信息
            status: 状态
            level: 级别
            
        Returns:
            AuditRecord: 审计记录
        """
        import uuid
        
        # 确定级别
        if level is None:
            if status == "failure":
                level = AuditLevel.WARNING
            elif action in [AuditAction.PERMISSION_DENIED, AuditAction.SUSPICIOUS_ACTIVITY]:
                level = AuditLevel.WARNING
            else:
                level = AuditLevel.INFO
        
        # 创建记录
        record = AuditRecord(
            id=str(uuid.uuid4()),
            action=action,
            level=level,
            user_id=user_id,
            username=username,
            resource=resource,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details or {},
            status=status,
        )
        
        # 存储
        self._records.append(record)
        self._id_index[record.id] = record
        
        # 更新索引
        if user_id:
            if user_id not in self._user_index:
                self._user_index[user_id] = []
            self._user_index[user_id].append(record.id)
        
        if action.value not in self._action_index:
            self._action_index[action.value] = []
        self._action_index[action.value].append(record.id)
        
        # 清理旧记录
        if len(self._records) > self.max_records:
            self._cleanup_old_records()
        
        # 写入日志
        self._write_to_log(record)
        
        return record
    
    def _write_to_log(self, record: AuditRecord):
        """写入日志文件"""
        log_record = {
            "timestamp": record.timestamp.isoformat(),
            "level": "AUDIT",
            "action": record.action.value,
            "user": record.username or record.user_id,
            "status": record.status,
            "ip": record.ip_address,
            "details": record.details,
        }
        
        if record.level == AuditLevel.CRITICAL:
            logger.critical(f"AUDIT: {record.action.value} - {json.dumps(log_record)}")
        elif record.level == AuditLevel.ERROR:
            logger.error(f"AUDIT: {record.action.value} - {json.dumps(log_record)}")
        elif record.level == AuditLevel.WARNING:
            logger.warning(f"AUDIT: {record.action.value} - {json.dumps(log_record)}")
        else:
            logger.info(f"AUDIT: {record.action.value} - {json.dumps(log_record)}")
    
    def _cleanup_old_records(self):
        """清理旧记录"""
        # 保留最近的 max_records 条
        remove_count = len(self._records) - self.max_records
        
        if remove_count <= 0:
            return
        
        # 移除旧记录
        for record in self._records[:remove_count]:
            self._id_index.pop(record.id, None)
            
            if record.user_id:
                user_list = self._user_index.get(record.user_id, [])
                if record.id in user_list:
                    user_list.remove(record.id)
            
            action_list = self._action_index.get(record.action.value, [])
            if record.id in action_list:
                action_list.remove(record.id)
        
        self._records = self._records[-self.max_records:]
        
        logger.info(f"清理 {remove_count} 条旧审计记录")
    
    def get_records(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[AuditLevel] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditRecord]:
        """
        查询审计记录
        
        Args:
            user_id: 用户 ID 过滤
            action: 操作类型过滤
            start_time: 开始时间
            end_time: 结束时间
            level: 级别过滤
            status: 状态过滤
            limit: 数量限制
            offset: 偏移量
            
        Returns:
            List[AuditRecord]: 审计记录列表
        """
        results = self._records
        
        # 过滤
        if user_id:
            record_ids = self._user_index.get(user_id, [])
            results = [r for r in results if r.id in record_ids]
        
        if action:
            record_ids = self._action_index.get(action.value, [])
            results = [r for r in results if r.id in record_ids]
        
        if start_time:
            results = [r for r in results if r.timestamp >= start_time]
        
        if end_time:
            results = [r for r in results if r.timestamp <= end_time]
        
        if level:
            results = [r for r in results if r.level == level]
        
        if status:
            results = [r for r in results if r.status == status]
        
        # 排序（最新在前）
        results = sorted(results, key=lambda r: r.timestamp, reverse=True)
        
        # 分页
        return results[offset:offset + limit]
    
    def export_records(
        self,
        format: str = "json",
        **kwargs
    ) -> str:
        """
        导出审计记录
        
        Args:
            format: 导出格式（json/csv）
            **kwargs: 过滤参数
            
        Returns:
            str: 导出的数据
        """
        records = self.get_records(**kwargs, limit=10000)
        
        if format == "json":
            return json.dumps([r.to_dict() for r in records], indent=2, ensure_ascii=False)
        
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            fieldnames = [
                "id", "action", "level", "user_id", "username",
                "resource", "ip_address", "status", "timestamp"
            ]
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in records:
                writer.writerow({
                    "id": record.id,
                    "action": record.action.value,
                    "level": record.level.value,
                    "user_id": record.user_id,
                    "username": record.username,
                    "resource": record.resource,
                    "ip_address": record.ip_address,
                    "status": record.status,
                    "timestamp": record.timestamp.isoformat(),
                })
            
            return output.getvalue()
        
        else:
            raise ValueError(f"不支持的格式：{format}")
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        # 按操作类型统计
        action_counts = {}
        for record in self._records:
            action = record.action.value
            action_counts[action] = action_counts.get(action, 0) + 1
        
        # 按级别统计
        level_counts = {level.value: 0 for level in AuditLevel}
        for record in self._records:
            level_counts[record.level.value] += 1
        
        # 失败操作
        failed_count = sum(1 for r in self._records if r.status == "failure")
        
        return {
            "total_records": len(self._records),
            "action_counts": action_counts,
            "level_counts": level_counts,
            "failed_count": failed_count,
            "unique_users": len(self._user_index),
        }


# 全局审计日志实例
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取审计日志实例"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
