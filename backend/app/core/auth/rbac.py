"""
RBAC - 基于角色的访问控制
"""

from enum import Enum
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Permission(Enum):
    """
    权限枚举
    
    格式：resource:action
    """
    # 交易相关
    TRADE_EXECUTE = "trade:execute"
    TRADE_CANCEL = "trade:cancel"
    TRADE_VIEW = "trade:view"
    
    # 策略相关
    STRATEGY_CREATE = "strategy:create"
    STRATEGY_UPDATE = "strategy:update"
    STRATEGY_DELETE = "strategy:delete"
    STRATEGY_VIEW = "strategy:view"
    
    # 资金相关
    ACCOUNT_VIEW = "account:view"
    ACCOUNT_DEPOSIT = "account:deposit"
    ACCOUNT_WITHDRAW = "account:withdraw"
    ACCOUNT_TRANSFER = "account:transfer"
    
    # 管理相关
    ADMIN_USER_CREATE = "admin:user:create"
    ADMIN_USER_UPDATE = "admin:user:update"
    ADMIN_USER_DELETE = "admin:user:delete"
    ADMIN_USER_VIEW = "admin:user:view"
    ADMIN_CONFIG_UPDATE = "admin:config:update"
    ADMIN_CONFIG_VIEW = "admin:config:view"
    
    # 审计相关
    AUDIT_VIEW = "audit:view"
    AUDIT_EXPORT = "audit:export"
    
    # 系统相关
    SYSTEM_START = "system:start"
    SYSTEM_STOP = "system:stop"
    SYSTEM_RESTART = "system:restart"
    SYSTEM_STATUS = "system:status"


class Role(Enum):
    """
    角色枚举
    
    预定义角色，每个角色有一组权限
    """
    # 超级管理员 - 所有权限
    ADMIN = "admin"
    
    # 交易员 - 交易相关权限
    TRADER = "trader"
    
    # 策略师 - 策略管理权限
    STRATEGIST = "strategist"
    
    # 分析师 - 只读权限
    ANALYST = "analyst"
    
    # 审计员 - 审计相关权限
    AUDITOR = "auditor"
    
    # 只读用户
    VIEWER = "viewer"


# 角色权限映射
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: set(Permission),  # 所有权限
    
    Role.TRADER: {
        Permission.TRADE_EXECUTE,
        Permission.TRADE_CANCEL,
        Permission.TRADE_VIEW,
        Permission.ACCOUNT_VIEW,
        Permission.STRATEGY_VIEW,
        Permission.SYSTEM_STATUS,
    },
    
    Role.STRATEGIST: {
        Permission.STRATEGY_CREATE,
        Permission.STRATEGY_UPDATE,
        Permission.STRATEGY_DELETE,
        Permission.STRATEGY_VIEW,
        Permission.TRADE_VIEW,
        Permission.ACCOUNT_VIEW,
    },
    
    Role.ANALYST: {
        Permission.TRADE_VIEW,
        Permission.STRATEGY_VIEW,
        Permission.ACCOUNT_VIEW,
        Permission.AUDIT_VIEW,
        Permission.SYSTEM_STATUS,
    },
    
    Role.AUDITOR: {
        Permission.AUDIT_VIEW,
        Permission.AUDIT_EXPORT,
        Permission.TRADE_VIEW,
        Permission.ACCOUNT_VIEW,
        Permission.STRATEGY_VIEW,
    },
    
    Role.VIEWER: {
        Permission.TRADE_VIEW,
        Permission.ACCOUNT_VIEW,
        Permission.SYSTEM_STATUS,
    },
}


@dataclass
class CustomRole:
    """
    自定义角色
    
    Attributes:
        name: 角色名称
        permissions: 权限集合
        description: 角色描述
        created_at: 创建时间
    """
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_permission(self, permission: Permission):
        """添加权限"""
        self.permissions.add(permission)
    
    def remove_permission(self, permission: Permission):
        """移除权限"""
        self.permissions.discard(permission)
    
    def has_permission(self, permission: Permission) -> bool:
        """检查是否有权限"""
        return permission in self.permissions


class RoleManager:
    """
    角色管理器
    
    管理角色和权限的分配
    """
    
    def __init__(self):
        """初始化角色管理器"""
        # 自定义角色
        self._custom_roles: Dict[str, CustomRole] = {}
        
        # 用户角色映射：{user_id: Set[Role]}
        self._user_roles: Dict[str, Set[Role]] = {}
        
        # 用户自定义角色映射：{user_id: Set[str]}
        self._user_custom_roles: Dict[str, Set[str]] = {}
    
    def create_custom_role(
        self,
        name: str,
        permissions: List[Permission],
        description: str = "",
    ) -> CustomRole:
        """
        创建自定义角色
        
        Args:
            name: 角色名称
            permissions: 权限列表
            description: 描述
            
        Returns:
            CustomRole: 自定义角色
        """
        if name in self._custom_roles:
            raise ValueError(f"角色已存在：{name}")
        
        role = CustomRole(
            name=name,
            permissions=set(permissions),
            description=description,
        )
        
        self._custom_roles[name] = role
        logger.info(f"创建自定义角色：{name} ({len(permissions)} 权限)")
        
        return role
    
    def delete_custom_role(self, name: str):
        """删除自定义角色"""
        if name not in self._custom_roles:
            raise ValueError(f"角色不存在：{name}")
        
        del self._custom_roles[name]
        logger.info(f"删除自定义角色：{name}")
    
    def assign_role(self, user_id: str, role: Role):
        """
        分配角色给用户
        
        Args:
            user_id: 用户 ID
            role: 角色
        """
        if user_id not in self._user_roles:
            self._user_roles[user_id] = set()
        
        self._user_roles[user_id].add(role)
        logger.info(f"用户 {user_id} 分配角色：{role.value}")
    
    def revoke_role(self, user_id: str, role: Role):
        """
        撤销用户角色
        
        Args:
            user_id: 用户 ID
            role: 角色
        """
        if user_id in self._user_roles:
            self._user_roles[user_id].discard(role)
            logger.info(f"用户 {user_id} 撤销角色：{role.value}")
    
    def assign_custom_role(self, user_id: str, role_name: str):
        """分配自定义角色"""
        if role_name not in self._custom_roles:
            raise ValueError(f"角色不存在：{role_name}")
        
        if user_id not in self._user_custom_roles:
            self._user_custom_roles[user_id] = set()
        
        self._user_custom_roles[user_id].add(role_name)
        logger.info(f"用户 {user_id} 分配自定义角色：{role_name}")
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        获取用户所有权限
        
        Args:
            user_id: 用户 ID
            
        Returns:
            Set[Permission]: 权限集合
        """
        permissions = set()
        
        # 预定义角色权限
        for role in self._user_roles.get(user_id, set()):
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
        
        # 自定义角色权限
        for role_name in self._user_custom_roles.get(user_id, set()):
            custom_role = self._custom_roles.get(role_name)
            if custom_role:
                permissions.update(custom_role.permissions)
        
        return permissions
    
    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """
        检查用户是否有权限
        
        Args:
            user_id: 用户 ID
            permission: 权限
            
        Returns:
            bool: 是否有权限
        """
        permissions = self.get_user_permissions(user_id)
        return permission in permissions
    
    def has_any_permission(self, user_id: str, permissions: List[Permission]) -> bool:
        """检查用户是否有任一权限"""
        user_permissions = self.get_user_permissions(user_id)
        return any(p in user_permissions for p in permissions)
    
    def has_all_permissions(self, user_id: str, permissions: List[Permission]) -> bool:
        """检查用户是否有所有权限"""
        user_permissions = self.get_user_permissions(user_id)
        return all(p in user_permissions for p in permissions)
    
    def get_user_roles(self, user_id: str) -> dict:
        """获取用户所有角色"""
        return {
            "predefined_roles": [r.value for r in self._user_roles.get(user_id, set())],
            "custom_roles": list(self._user_custom_roles.get(user_id, set())),
        }
    
    def is_admin(self, user_id: str) -> bool:
        """检查是否是管理员"""
        return Role.ADMIN in self._user_roles.get(user_id, set())
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        return {
            "custom_roles_count": len(self._custom_roles),
            "users_with_roles": len(self._user_roles),
            "predefined_roles": [r.value for r in Role],
        }


# 全局角色管理器实例
_role_manager: Optional[RoleManager] = None


def get_role_manager() -> RoleManager:
    """获取角色管理器实例"""
    global _role_manager
    if _role_manager is None:
        _role_manager = RoleManager()
    return _role_manager
