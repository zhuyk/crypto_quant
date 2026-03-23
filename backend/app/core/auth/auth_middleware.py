"""
认证中间件 - FastAPI 认证拦截
"""

from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from functools import wraps
import logging

from .rbac import Permission, get_role_manager
from .user_manager import get_user_manager
from .api_key_manager import get_api_key_manager
from .audit_logger import get_audit_logger, AuditAction

logger = logging.getLogger(__name__)

# HTTP Bearer 认证
security = HTTPBearer(auto_error=False)


def get_current_user_from_request(request: Request) -> Optional[dict]:
    """
    从请求中获取当前用户
    
    Args:
        request: FastAPI 请求
        
    Returns:
        dict: 用户信息 {user_id, username, auth_type}
    """
    # 尝试从会话获取（优先从 cookies）
    session_id = request.cookies.get("session_id")
    
    # 如果没有 cookies，尝试从 Authorization Bearer token 获取
    if not session_id:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # 检查是否是 session_id 格式（不是 API key）
            user_manager = get_user_manager()
            user = user_manager.validate_session(token)
            if user:
                # Handle both dict and object
                if isinstance(user, dict):
                    return {
                        "user_id": user.get("user_id"),
                        "username": user.get("username"),
                        "auth_type": "session",
                    }
                else:
                    return {
                        "user_id": user.id,
                        "username": user.username,
                        "auth_type": "session",
                    }
    
    if session_id:
        user_manager = get_user_manager()
        user = user_manager.validate_session(session_id)
        if user:
            # Handle both dict and object
            if isinstance(user, dict):
                return {
                    "user_id": user.get("user_id"),
                    "username": user.get("username"),
                    "auth_type": "session",
                }
            else:
                return {
                    "user_id": user.id,
                    "username": user.username,
                    "auth_type": "session",
                }
    
    # 尝试从 API Key 获取
    api_key_manager = get_api_key_manager()
    api_key = get_api_key_from_request(request)
    
    if api_key:
        return {
            "user_id": api_key.user_id,
            "username": f"api_key:{api_key.name}",
            "auth_type": "api_key",
            "api_key_id": api_key.id,
            "permissions": api_key.permissions,
        }
    
    return None


def get_api_key_from_request(request: Request) -> Optional[object]:
    """从请求中获取 API Key"""
    # 从 Header 获取
    api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        # 从 Bearer Token 获取
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
    
    if not api_key:
        return None
    
    # 验证 API Key
    api_key_manager = get_api_key_manager()
    client_ip = request.client.host if request.client else None
    
    return api_key_manager.validate_api_key(api_key, client_ip)


async def require_auth(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Security(security)):
    """
    要求认证
    
    用于需要登录的端点
    """
    user_info = get_current_user_from_request(request)
    
    if not user_info:
        # 记录审计
        audit_logger = get_audit_logger()
        audit_logger.log(
            action=AuditAction.PERMISSION_DENIED,
            ip_address=request.client.host if request.client else None,
            details={"path": request.url.path},
            status="failure",
        )
        
        raise HTTPException(
            status_code=401,
            detail="未授权访问",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_info


def require_permission(permission: Permission):
    """
    要求特定权限的装饰器
    
    Args:
        permission: 所需权限
        
    Returns:
        decorator: 装饰器
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user_info = get_current_user_from_request(request)
            
            if not user_info:
                raise HTTPException(status_code=401, detail="未授权访问")
            
            # 检查权限
            if user_info.get("auth_type") == "api_key":
                # API Key 权限检查
                api_key_id = user_info.get("api_key_id")
                api_key_manager = get_api_key_manager()
                
                if not api_key_manager.has_permission(api_key_id, permission.value):
                    raise HTTPException(status_code=403, detail="权限不足")
            
            elif user_info.get("auth_type") == "session":
                # 用户角色权限检查
                role_manager = get_role_manager()
                
                if not role_manager.has_permission(user_info["user_id"], permission):
                    # 记录审计
                    audit_logger = get_audit_logger()
                    audit_logger.log(
                        action=AuditAction.PERMISSION_DENIED,
                        user_id=user_info["user_id"],
                        username=user_info["username"],
                        ip_address=request.client.host if request.client else None,
                        details={
                            "permission": permission.value,
                            "path": request.url.path,
                        },
                        status="failure",
                    )
                    
                    raise HTTPException(status_code=403, detail="权限不足")
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def require_any_permission(permissions: List[Permission]):
    """要求任一权限"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user_info = get_current_user_from_request(request)
            
            if not user_info:
                raise HTTPException(status_code=401, detail="未授权访问")
            
            if user_info.get("auth_type") == "api_key":
                api_key_id = user_info.get("api_key_id")
                api_key_manager = get_api_key_manager()
                
                if not any(api_key_manager.has_permission(api_key_id, p.value) for p in permissions):
                    raise HTTPException(status_code=403, detail="权限不足")
            
            elif user_info.get("auth_type") == "session":
                role_manager = get_role_manager()
                
                if not any(role_manager.has_permission(user_info["user_id"], p) for p in permissions):
                    raise HTTPException(status_code=403, detail="权限不足")
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def require_admin(func):
    """要求管理员权限"""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user_info = get_current_user_from_request(request)
        
        if not user_info:
            raise HTTPException(status_code=401, detail="未授权访问")
        
        role_manager = get_role_manager()
        
        if not role_manager.is_admin(user_info["user_id"]):
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        return await func(request, *args, **kwargs)
    
    return wrapper


class AuthMiddleware:
    """
    认证中间件
    
    用于 FastAPI 应用的全局中间件
    """
    
    def __init__(self, app, exclude_paths: Optional[List[str]] = None):
        """
        Args:
            app: FastAPI 应用
            exclude_paths: 不需要认证的路径
        """
        self.app = app
        self.exclude_paths = exclude_paths or [
            "/api/v1/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]
    
    async def __call__(self, scope, receive, send):
        """中间件调用"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope)
        
        # 检查是否需要认证
        path = request.url.path
        if any(path.startswith(p) for p in self.exclude_paths):
            await self.app(scope, receive, send)
            return
        
        # 获取用户信息
        user_info = get_current_user_from_request(request)
        
        # 添加到请求状态
        request.state.user = user_info
        
        await self.app(scope, receive, send)


def setup_auth_middleware(app):
    """
    设置认证中间件
    
    Args:
        app: FastAPI 应用
    """
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # 排除路径
        exclude_paths = [
            "/api/v1/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]
        
        if any(request.url.path.startswith(p) for p in exclude_paths):
            return await call_next(request)
        
        # 获取用户信息
        user_info = get_current_user_from_request(request)
        request.state.user = user_info
        
        # 记录 API 使用
        if user_info and user_info.get("auth_type") == "api_key":
            audit_logger = get_audit_logger()
            audit_logger.log(
                action=AuditAction.API_KEY_USE,
                user_id=user_info["user_id"],
                ip_address=request.client.host if request.client else None,
                details={"path": request.url.path},
            )
        
        return await call_next(request)
