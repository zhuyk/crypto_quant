"""
标准化 API 响应格式

所有 API 端点应使用本模块提供的响应模型和工具函数，
确保前端接收到一致的数据结构。

标准格式:
{
    "success": true/false,
    "message": "描述信息",
    "data": { ... },           // 成功时的数据
    "error_code": "XXX",       // 失败时的错误码
    "details": { ... },        // 失败时的详细信息
    "meta": { ... }            // 可选的元信息（分页等）
}
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ============================================================
# 标准响应模型
# ============================================================


class ApiResponse(BaseModel):
    """
    通用 API 响应模型

    所有接口的响应都应符合此结构。
    """
    success: bool = True
    message: str = "success"
    data: Optional[Any] = None
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class PaginatedResponse(BaseModel):
    """
    分页响应模型

    用于列表类接口。
    """
    success: bool = True
    message: str = "success"
    data: List[Any] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ErrorResponse(BaseModel):
    """
    错误响应模型

    所有错误响应的结构。
    """
    success: bool = False
    message: str
    error_code: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 响应构建工具函数
# ============================================================


def ok(
    data: Any = None,
    message: str = "success",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    构建成功响应

    Args:
        data: 响应数据
        message: 成功描述
        meta: 附加元信息

    Returns:
        标准响应字典

    Example:
        @router.get("/users")
        async def list_users():
            users = db.query(User).all()
            return ok(data=users, meta={"total": len(users)})
    """
    response: Dict[str, Any] = {
        "success": True,
        "message": message,
        "data": data,
    }
    if meta:
        response["meta"] = meta
    return response


def ok_list(
    items: List[Any],
    total: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    message: str = "success",
) -> Dict[str, Any]:
    """
    构建分页列表响应

    Args:
        items: 数据列表
        total: 总数（None 则取 items 长度）
        page: 当前页
        page_size: 每页大小
        message: 描述

    Example:
        @router.get("/trades")
        async def list_trades(page: int = 1, size: int = 20):
            trades = get_trades(page, size)
            return ok_list(trades, total=100, page=page, page_size=size)
    """
    actual_total = total if total is not None else len(items)
    total_pages = (actual_total + page_size - 1) // page_size if page_size > 0 else 1

    return {
        "success": True,
        "message": message,
        "data": items,
        "meta": {
            "total": actual_total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


def fail(
    message: str,
    error_code: str = "ERROR",
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 400,
) -> Dict[str, Any]:
    """
    构建失败响应

    注意: 这只是构建响应体，HTTP status code 需要在路由中通过
    HTTPException 或 JSONResponse 单独设置。

    Args:
        message: 错误描述
        error_code: 错误码
        details: 错误详情
        status_code: HTTP 状态码（仅记录，不影响返回）

    Example:
        raise HTTPException(status_code=400, detail=fail("参数无效", "INVALID_PARAMS"))
    """
    response: Dict[str, Any] = {
        "success": False,
        "message": message,
        "error_code": error_code,
    }
    if details:
        response["details"] = details
    return response


def created(
    data: Any = None,
    message: str = "创建成功",
) -> Dict[str, Any]:
    """构建 201 创建成功响应"""
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def deleted(
    message: str = "删除成功",
    resource_id: Optional[Any] = None,
) -> Dict[str, Any]:
    """构建删除成功响应"""
    response: Dict[str, Any] = {
        "success": True,
        "message": message,
    }
    if resource_id is not None:
        response["data"] = {"id": resource_id}
    return response


# ============================================================
# 兼容旧接口（保持 backward compatibility）
# ============================================================

def success_response(data: Any = None, message: str = "success") -> Dict[str, Any]:
    """
    [兼容] 生成标准成功响应

    等同于 ok()，保留以兼容旧代码。
    """
    return ok(data=data, message=message)


def error_response(
    error_code: str,
    message: str,
    status_code: int = 500,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    [兼容] 生成标准错误响应

    保留以兼容旧代码。
    """
    return {
        "success": False,
        "error_code": error_code,
        "message": message,
        "status_code": status_code,
        "details": details or {},
    }
