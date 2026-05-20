"""
认证 API 路由
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
import logging

from app.core.auth.rbac import get_role_manager, Role, Permission
from app.core.auth.user_manager import get_user_manager, UserStatus
from app.core.auth.api_key_manager import get_api_key_manager
from app.core.auth.audit_logger import get_audit_logger, AuditAction
from app.core.auth.auth_middleware import require_auth, require_permission, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


# ========== 请求模型 ==========

class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str
    email: EmailStr
    password: str = Field(..., min_length=6)


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(..., min_length=6)


class CreateAPIKeyRequest(BaseModel):
    """创建 API Key 请求"""
    name: str
    permissions: Optional[List[str]] = None
    expires_days: Optional[int] = None
    ip_whitelist: Optional[List[str]] = None


# ========== 响应模型 ==========

class LoginResponse(BaseModel):
    """登录响应"""
    success: bool
    session_id: str
    user: dict


class UserInfo(BaseModel):
    """用户信息"""
    id: str
    username: str
    email: str
    status: str
    roles: list
    two_factor_enabled: bool


class APIKeyInfo(BaseModel):
    """API Key 信息"""
    id: str
    key_prefix: str
    name: str
    permissions: list
    status: str
    expires_at: Optional[str]
    created_at: str


# ========== 认证端点 ==========

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    用户登录
    
    返回会话 ID，用于后续请求认证
    """
    user_manager = get_user_manager()
    role_manager = get_role_manager()
    audit_logger = get_audit_logger()
    
    # 如果是默认管理员账户且不存在，自动创建
    if request.username == 'admin' and request.password == 'admin123456':
        existing_user = user_manager.get_user_by_username('admin')
        if not existing_user:
            admin = user_manager.create_user(
                username='admin',
                email='admin@cryptoquant.com',
                password='admin123456',
                roles=['admin'],
            )
            if admin:
                role_manager.assign_role(admin['id'], Role.ADMIN)
                logger.info("✅ 自动创建默认管理员账户")
            else:
                logger.warning("⚠️  创建默认管理员账户失败")
    
    # 认证
    session_id = user_manager.authenticate(request.username, request.password)
    
    if not session_id:
        # 记录失败
        audit_logger.log(
            action=AuditAction.LOGIN,
            username=request.username,
            status="failure",
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 获取用户
    user = user_manager.get_user_by_username(request.username)
    
    # 记录成功
    user_id = user.get('id') if isinstance(user, dict) else user.id
    username = user.get('username') if isinstance(user, dict) else user.username
    audit_logger.log(
        action=AuditAction.LOGIN,
        user_id=user_id,
        username=username,
        status="success",
    )
    
    # 转换为 dict
    if isinstance(user, dict):
        user_dict = {k: v for k, v in user.items() if k != 'password_hash'}
        user_dict['status'] = 'active' if user_dict.get('is_active') else 'inactive'
    else:
        user_dict = user.to_dict()
    
    return LoginResponse(
        success=True,
        session_id=session_id,
        user=user_dict,
    )


@router.post("/logout")
async def logout(request: Request):
    """用户登出"""
    user_manager = get_user_manager()
    user_info = await require_auth(request)
    
    session_id = request.cookies.get("session_id")
    if session_id:
        user_manager.logout(session_id)
    
    audit_logger = get_audit_logger()
    audit_logger.log(
        action=AuditAction.LOGOUT,
        user_id=user_info["user_id"],
        username=user_info["username"],
    )
    
    return {"success": True}


@router.post("/register")
async def register(request: RegisterRequest):
    """用户注册"""
    user_manager = get_user_manager()
    role_manager = get_role_manager()
    audit_logger = get_audit_logger()
    
    try:
        # 创建用户（默认 VIEWER 角色）
        user = user_manager.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            roles=["viewer"],
        )
        
        # 记录审计
        audit_logger.log(
            action=AuditAction.USER_CREATE,
            user_id=user.id,
            username=user.username,
            status="success",
        )
        
        return {
            "success": True,
            "user": user.to_dict(),
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(request: Request):
    """获取当前用户信息"""
    user_info = await require_auth(request)
    user_manager = get_user_manager()
    
    user = user_manager.get_user(user_info["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # Handle both dict and object
    if isinstance(user, dict):
        user_id = user.get('id')
        username = user.get('username')
        email = user.get('email', '')
        status = 'active' if user.get('is_active', False) else 'inactive'
        two_factor_enabled = user.get('two_factor_enabled', False)
    else:
        user_id = user.id
        username = user.username
        email = user.email
        status = user.status.value
        two_factor_enabled = user.two_factor_enabled
    
    return UserInfo(
        id=user_id,
        username=username,
        email=email,
        status=status,
        roles=user_info.get("roles", []),
        two_factor_enabled=two_factor_enabled,
    )


@router.post("/password/change")
async def change_password(request: ChangePasswordRequest, req: Request):
    """修改密码"""
    user_manager = get_user_manager()
    user_info = await require_auth(req)
    audit_logger = get_audit_logger()
    
    user = user_manager.get_user(user_info["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 验证旧密码
    if not user_manager._verify_password(request.old_password, user.password_hash):
        audit_logger.log(
            action=AuditAction.PASSWORD_CHANGE,
            user_id=user.id,
            status="failure",
            details={"reason": "wrong_old_password"},
        )
        raise HTTPException(status_code=400, detail="旧密码错误")
    
    # 更新密码
    user.password_hash = user_manager._hash_password(request.new_password)
    
    audit_logger.log(
        action=AuditAction.PASSWORD_CHANGE,
        user_id=user.id,
        status="success",
    )
    
    return {"success": True}


# ========== 用户管理端点（管理员） ==========

@router.get("/users", dependencies=[Depends(require_admin)])
async def list_users():
    """获取用户列表（仅管理员）"""
    user_manager = get_user_manager()
    
    users = []
    for user in user_manager._users.values():
        users.append(user.to_dict())
    
    return {"users": users}


@router.post("/users/{user_id}/role", dependencies=[Depends(require_admin)])
async def assign_role(user_id: str, role: str, request: Request):
    """分配角色（仅管理员）"""
    user_manager = get_user_manager()
    role_manager = get_role_manager()
    audit_logger = get_audit_logger()
    
    user = user_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    try:
        role_enum = Role(role.lower())
        role_manager.assign_role(user_id, role_enum)
        
        audit_logger.log(
            action=AuditAction.ROLE_ASSIGN,
            user_id=user_id,
            username=user.username,
            details={"role": role},
        )
        
        return {"success": True}
        
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的角色：{role}")


@router.delete("/users/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(user_id: str, request: Request):
    """删除用户（仅管理员）"""
    user_manager = get_user_manager()
    audit_logger = get_audit_logger()
    
    user = user_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user_manager.delete_user(user_id)
    
    audit_logger.log(
        action=AuditAction.USER_DELETE,
        user_id=user_id,
        username=user.username,
    )
    
    return {"success": True}


# ========== API Key 管理 ==========

@router.post("/api-keys", response_model=dict)
async def create_api_key(request: CreateAPIKeyRequest, req: Request):
    """创建 API Key"""
    user_info = await require_auth(req)
    api_key_manager = get_api_key_manager()
    audit_logger = get_audit_logger()
    
    key_prefix, api_key = api_key_manager.create_api_key(
        user_id=user_info["user_id"],
        name=request.name,
        permissions=request.permissions,
        expires_days=request.expires_days,
        ip_whitelist=request.ip_whitelist,
    )
    
    audit_logger.log(
        action=AuditAction.API_KEY_CREATE,
        user_id=user_info["user_id"],
        details={"name": request.name},
    )
    
    return {
        "success": True,
        "api_key": {
            "id": api_key.id,
            "key": key_prefix,  # 只显示前缀
            "name": api_key.name,
            "permissions": list(api_key.permissions),
        },
        "warning": "请保存好 API Key，这是唯一一次显示完整 Key",
    }


@router.get("/api-keys")
async def list_api_keys(request: Request):
    """获取我的 API Key 列表"""
    user_info = await require_auth(request)
    api_key_manager = get_api_key_manager()
    
    keys = api_key_manager.get_user_keys(user_info["user_id"])
    
    return {
        "api_keys": [key.to_dict() for key in keys],
    }


@router.post("/api-keys/{key_id}/revoke")
async def revoke_api_key(key_id: str, request: Request):
    """撤销 API Key"""
    user_info = await require_auth(request)
    api_key_manager = get_api_key_manager()
    audit_logger = get_audit_logger()
    
    api_key = api_key_manager.get_api_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    
    if api_key.user_id != user_info["user_id"]:
        raise HTTPException(status_code=403, detail="无权操作此 API Key")
    
    api_key_manager.revoke_api_key(key_id)
    
    audit_logger.log(
        action=AuditAction.API_KEY_REVOKE,
        user_id=user_info["user_id"],
        details={"key_id": key_id},
    )
    
    return {"success": True}


# ========== 审计日志 ==========

@router.get("/audit/logs")
async def get_audit_logs(
    request: Request,
    action: Optional[str] = None,
    limit: int = 100,
):
    """获取审计日志"""
    user_info = await require_auth(request)
    audit_logger = get_audit_logger()
    role_manager = get_role_manager()
    
    # 检查是否有审计查看权限
    if not role_manager.has_permission(user_info["user_id"], Permission.AUDIT_VIEW):
        raise HTTPException(status_code=403, detail="无权查看审计日志")
    
    audit_action = None
    if action:
        try:
            audit_action = AuditAction(action)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的操作类型：{action}")
    
    records = audit_logger.get_records(action=audit_action, limit=limit)
    
    return {
        "logs": [r.to_dict() for r in records],
    }


# ========== 统计信息 ==========

@router.get("/statistics")
async def get_auth_statistics(request: Request):
    """获取认证统计"""
    user_info = await require_auth(request)
    
    user_manager = get_user_manager()
    role_manager = get_role_manager()
    api_key_manager = get_api_key_manager()
    audit_logger = get_audit_logger()
    
    return {
        "users": user_manager.get_statistics(),
        "roles": role_manager.get_statistics(),
        "api_keys": api_key_manager.get_statistics(),
        "audit": audit_logger.get_statistics(),
    }
