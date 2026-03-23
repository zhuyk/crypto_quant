"""
API Key 管理器
"""

import secrets
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class APIKeyStatus(Enum):
    """API Key 状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class APIKey:
    """
    API Key
    
    Attributes:
        id: API Key ID
        key: API Key（哈希）
        key_prefix: Key 前缀（用于识别）
        user_id: 所属用户
        name: 名称
        permissions: 权限列表
        status: 状态
        expires_at: 过期时间
        last_used: 最后使用
        created_at: 创建时间
        ip_whitelist: IP 白名单
    """
    id: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    key: str = ""
    key_prefix: str = ""
    user_id: str = ""
    name: str = ""
    permissions: Set[str] = field(default_factory=set)
    status: APIKeyStatus = APIKeyStatus.ACTIVE
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    ip_whitelist: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """转换为字典（不暴露完整 Key）"""
        return {
            "id": self.id,
            "key_prefix": self.key_prefix,
            "user_id": self.user_id,
            "name": self.name,
            "permissions": list(self.permissions),
            "status": self.status.value,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "created_at": self.created_at.isoformat(),
            "ip_whitelist": self.ip_whitelist,
        }


class APIKeyManager:
    """
    API Key 管理器
    
    管理 API Key 的创建、验证、权限控制
    """
    
    def __init__(self):
        """初始化 API Key 管理器"""
        # API Key 存储：{key_id: APIKey}
        self._keys: Dict[str, APIKey] = {}
        
        # Key 哈希索引：{key_hash: key_id}
        self._key_index: Dict[str, str] = {}
        
        # 用户 Key 索引：{user_id: [key_id]}
        self._user_keys: Dict[str, List[str]] = {}
    
    def _hash_key(self, key: str) -> str:
        """哈希 API Key"""
        return hashlib.sha256(key.encode('utf-8')).hexdigest()
    
    def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: Optional[List[str]] = None,
        expires_days: Optional[int] = None,
        ip_whitelist: Optional[List[str]] = None,
    ) -> tuple[str, APIKey]:
        """
        创建 API Key
        
        Args:
            user_id: 用户 ID
            name: 名称
            permissions: 权限列表
            expires_days: 过期天数
            ip_whitelist: IP 白名单
            
        Returns:
            (明文 Key, APIKey 对象)
        """
        # 生成 API Key
        raw_key = secrets.token_urlsafe(32)
        key_hash = self._hash_key(raw_key)
        key_prefix = raw_key[:8]
        
        # 创建 API Key
        api_key = APIKey(
            key=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            name=name,
            permissions=set(permissions or []),
            ip_whitelist=ip_whitelist or [],
        )
        
        # 设置过期时间
        if expires_days:
            api_key.expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        # 存储
        self._keys[api_key.id] = api_key
        self._key_index[key_hash] = api_key.id
        
        if user_id not in self._user_keys:
            self._user_keys[user_id] = []
        self._user_keys[user_id].append(api_key.id)
        
        logger.info(f"创建 API Key：{name} ({api_key.id}) for user {user_id}")
        
        # 只返回一次明文 Key
        return f"{key_prefix}{'*' * 24}", api_key
    
    def validate_api_key(self, raw_key: str, client_ip: Optional[str] = None) -> Optional[APIKey]:
        """
        验证 API Key
        
        Args:
            raw_key: 明文 Key
            client_ip: 客户端 IP
            
        Returns:
            APIKey: API Key 对象（有效）
        """
        key_hash = self._hash_key(raw_key)
        key_id = self._key_index.get(key_hash)
        
        if not key_id:
            return None
        
        api_key = self._keys.get(key_id)
        if not api_key:
            return None
        
        # 检查状态
        if api_key.status != APIKeyStatus.ACTIVE:
            logger.warning(f"API Key 状态异常：{api_key.id} {api_key.status.value}")
            return None
        
        # 检查过期
        if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
            api_key.status = APIKeyStatus.EXPIRED
            logger.warning(f"API Key 已过期：{api_key.id}")
            return None
        
        # 检查 IP 白名单
        if client_ip and api_key.ip_whitelist:
            if client_ip not in api_key.ip_whitelist:
                logger.warning(f"API Key IP 不在白名单：{api_key.id} {client_ip}")
                return None
        
        # 更新最后使用时间
        api_key.last_used = datetime.utcnow()
        
        return api_key
    
    def revoke_api_key(self, key_id: str) -> bool:
        """撤销 API Key"""
        api_key = self._keys.get(key_id)
        if not api_key:
            return False
        
        api_key.status = APIKeyStatus.REVOKED
        logger.info(f"撤销 API Key：{key_id}")
        
        return True
    
    def update_api_key(
        self,
        key_id: str,
        name: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        expires_days: Optional[int] = None,
        ip_whitelist: Optional[List[str]] = None,
    ) -> bool:
        """更新 API Key"""
        api_key = self._keys.get(key_id)
        if not api_key:
            return False
        
        if name:
            api_key.name = name
        if permissions is not None:
            api_key.permissions = set(permissions)
        if expires_days:
            api_key.expires_at = datetime.utcnow() + timedelta(days=expires_days)
        if ip_whitelist is not None:
            api_key.ip_whitelist = ip_whitelist
        
        logger.info(f"更新 API Key：{key_id}")
        return True
    
    def get_api_key(self, key_id: str) -> Optional[APIKey]:
        """获取 API Key"""
        return self._keys.get(key_id)
    
    def get_user_keys(self, user_id: str) -> List[APIKey]:
        """获取用户所有 API Key"""
        key_ids = self._user_keys.get(user_id, [])
        return [self._keys[kid] for kid in key_ids if kid in self._keys]
    
    def has_permission(self, key_id: str, permission: str) -> bool:
        """检查 API Key 是否有权限"""
        api_key = self._keys.get(key_id)
        if not api_key:
            return False
        
        # 管理员权限（通配符）
        if "*" in api_key.permissions or "admin:*" in api_key.permissions:
            return True
        
        return permission in api_key.permissions
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        active_keys = sum(1 for k in self._keys.values() if k.status == APIKeyStatus.ACTIVE)
        expired_keys = sum(1 for k in self._keys.values() if k.status == APIKeyStatus.EXPIRED)
        revoked_keys = sum(1 for k in self._keys.values() if k.status == APIKeyStatus.REVOKED)
        
        return {
            "total_keys": len(self._keys),
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "revoked_keys": revoked_keys,
            "users_with_keys": len(self._user_keys),
        }


# 全局 API Key 管理器实例
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """获取 API Key 管理器实例"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager
