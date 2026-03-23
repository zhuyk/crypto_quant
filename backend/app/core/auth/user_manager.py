"""
用户管理器 - 使用数据库存储用户，Redis 存储会话
"""

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set
from enum import Enum
import logging

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import User as DBUser
from app.utils.cache import get_cache

logger = logging.getLogger(__name__)


class User:
    """用户数据类（用于返回，非数据库模型）"""
    def __init__(self, user_id: str, username: str, email: str = "", is_active: bool = True):
        self.id = user_id
        self.username = username
        self.email = email
        self.is_active = is_active
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
        }


class UserStatus(Enum):
    """用户状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"


class UserManager:
    """用户管理器 - 数据库 + Redis"""
    
    def __init__(self):
        """初始化用户管理器"""
        self._cache = get_cache()
        self._db: Optional[Session] = None
    
    def _get_db(self) -> Session:
        """获取数据库会话"""
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def _hash_password(self, password: str, salt: Optional[str] = None) -> str:
        """哈希密码"""
        if salt is None:
            salt = secrets.token_hex(16)
        salted = f"{salt}{password}".encode('utf-8')
        password_hash = hashlib.sha256(salted).hexdigest()
        return f"{salt}:{password_hash}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            salt, stored_hash = password_hash.split(':')
            computed_hash = hashlib.sha256(f"{salt}{password}".encode('utf-8')).hexdigest()
            return computed_hash == stored_hash
        except Exception:
            return False
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """创建用户（数据库）"""
        try:
            db = self._get_db()
            
            # 检查用户名
            existing = db.query(DBUser).filter(DBUser.username == username).first()
            if existing:
                logger.warning(f"用户名已存在：{username}")
                return None
            
            # 创建用户
            password_hash = self._hash_password(password)
            user = DBUser(
                username=username,
                email=email,
                password_hash=password_hash,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            logger.info(f"创建用户：{username} (ID: {user.id})")
            
            return {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
            }
        except Exception as e:
            db.rollback()
            logger.error(f"创建用户失败：{e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """通过用户名获取用户"""
        try:
            db = self._get_db()
            user = db.query(DBUser).filter(DBUser.username == username).first()
            if user:
                return {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "password_hash": user.password_hash,
                    "is_active": user.is_active,
                }
            return None
        except Exception as e:
            logger.error(f"查询用户失败：{e}")
            return None
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """通过用户 ID 获取用户"""
        try:
            db = self._get_db()
            user = db.query(DBUser).filter(DBUser.id == int(user_id)).first()
            if user:
                return {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "password_hash": user.password_hash,
                    "is_active": user.is_active,
                }
            return None
        except Exception as e:
            logger.error(f"查询用户失败 (ID {user_id}): {e}")
            return None
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """用户认证"""
        try:
            # 获取用户
            user = self.get_user_by_username(username)
            if not user:
                logger.warning(f"用户不存在：{username}")
                return None
            
            # 检查状态
            if not user.get("is_active", False):
                logger.warning(f"用户未激活：{username}")
                return None
            
            # 验证密码
            if not self._verify_password(password, user["password_hash"]):
                logger.warning(f"密码错误：{username}")
                return None
            
            # 创建会话 (存储到 Redis)
            session_id = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(days=7)
            session_data = {
                "user_id": user["id"],
                "username": user["username"],
                "expires_at": expires_at.isoformat(),
            }
            
            # 存储到 Redis，7 天过期
            redis_ok = self._cache.set(f"session:{session_id}", session_data, expire=7 * 24 * 3600)
            
            if redis_ok:
                logger.info(f"用户登录：{username} (session: {session_id[:8]}..., Redis ✅)")
            else:
                logger.error(f"用户登录：{username} (Redis 失败!)")
                return None
            
            return session_id
        except Exception as e:
            logger.error(f"认证失败：{e}")
            return None
    
    def logout(self, session_id: str) -> bool:
        """登出"""
        deleted = self._cache.delete(f"session:{session_id}")
        if deleted:
            logger.info(f"用户登出：{session_id[:8]}...")
            return True
        return False
    
    def validate_session(self, session_id: str) -> Optional[Dict]:
        """验证会话"""
        try:
            # 从 Redis 获取会话
            session_data = self._cache.get(f"session:{session_id}")
            
            if not session_data:
                return None
            
            # 检查过期
            try:
                expires_at = datetime.fromisoformat(session_data["expires_at"])
                if datetime.utcnow() > expires_at:
                    self._cache.delete(f"session:{session_id}")
                    return None
            except (KeyError, ValueError) as e:
                logger.warning(f"会话数据格式错误：{e}")
                self._cache.delete(f"session:{session_id}")
                return None
            
            # 返回用户信息
            return {
                "user_id": session_data["user_id"],
                "username": session_data["username"],
                "auth_type": "session",
            }
        except Exception as e:
            logger.error(f"验证会话失败：{e}")
            return None
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        try:
            db = self._get_db()
            total = db.query(DBUser).count()
            active = db.query(DBUser).filter(DBUser.is_active == True).count()
            return {
                "total_users": total,
                "active_users": active,
                "active_sessions": len(self._cache.client.keys("session:*")) if self._cache._connected else 0,
            }
        except Exception as e:
            logger.error(f"获取统计失败：{e}")
            return {}


# 全局单例
_user_manager: Optional[UserManager] = None


def get_user_manager() -> UserManager:
    """获取用户管理器实例"""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager
