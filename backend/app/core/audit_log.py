"""
审计日志模块
记录所有敏感操作和安全相关事件
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, log_file: str = "logs/audit.log"):
        self.log_path = Path(log_file)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 配置审计日志（独立于应用日志）
        logger.add(
            str(self.log_path),
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
            rotation="100 MB",
            retention="90 days",  # 审计日志保留 90 天
            compression="zip",
            enqueue=True,
        )
        
        self.logger = logger.bind(module="audit")
    
    def log(
        self,
        action: str,
        resource: str,
        user_id: Optional[str] = None,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ):
        """
        记录审计事件
        
        Args:
            action: 操作类型 (CREATE, UPDATE, DELETE, LOGIN, LOGOUT, etc.)
            resource: 资源名称 (user, strategy, order, etc.)
            user_id: 用户 ID
            status: 操作状态 (success, failure)
            details: 详细信息
            ip_address: IP 地址
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "resource": resource,
            "user_id": user_id,
            "status": status,
            "ip_address": ip_address,
            "details": details or {},
        }
        
        log_msg = f"AUDIT | {action} | {resource} | {status}"
        if user_id:
            log_msg += f" | user:{user_id}"
        
        self.logger.info(log_msg, extra=event)
    
    def login(self, user_id: str, success: bool, ip_address: Optional[str] = None):
        """记录登录事件"""
        self.log(
            action="LOGIN",
            resource="auth",
            user_id=user_id,
            status="success" if success else "failure",
            ip_address=ip_address,
        )
    
    def logout(self, user_id: str, ip_address: Optional[str] = None):
        """记录登出事件"""
        self.log(
            action="LOGOUT",
            resource="auth",
            user_id=user_id,
            status="success",
            ip_address=ip_address,
        )
    
    def api_key_access(self, user_id: str, endpoint: str, ip_address: Optional[str] = None):
        """记录 API 密钥访问"""
        self.log(
            action="API_KEY_ACCESS",
            resource="api_key",
            user_id=user_id,
            status="success",
            details={"endpoint": endpoint},
            ip_address=ip_address,
        )
    
    def order_created(self, order_id: str, user_id: str, details: Dict[str, Any]):
        """记录订单创建"""
        self.log(
            action="CREATE",
            resource="order",
            user_id=user_id,
            status="success",
            details=details,
        )
    
    def order_modified(self, order_id: str, user_id: str, changes: Dict[str, Any]):
        """记录订单修改"""
        self.log(
            action="UPDATE",
            resource="order",
            user_id=user_id,
            status="success",
            details={"order_id": order_id, "changes": changes},
        )
    
    def order_cancelled(self, order_id: str, user_id: str, reason: str):
        """记录订单取消"""
        self.log(
            action="CANCEL",
            resource="order",
            user_id=user_id,
            status="success",
            details={"order_id": order_id, "reason": reason},
        )
    
    def strategy_modified(self, strategy_id: str, user_id: str, changes: Dict[str, Any]):
        """记录策略修改"""
        self.log(
            action="UPDATE",
            resource="strategy",
            user_id=user_id,
            status="success",
            details={"strategy_id": strategy_id, "changes": changes},
        )
    
    def security_event(self, event_type: str, details: Dict[str, Any], user_id: Optional[str] = None):
        """记录安全事件"""
        self.log(
            action="SECURITY_EVENT",
            resource="security",
            user_id=user_id,
            status="alert",
            details={"event_type": event_type, **details},
        )


# 全局审计日志实例
audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """获取审计日志记录器"""
    return audit_logger
