"""
任务调度 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.core.exceptions import success_response, NotFoundError
from app.tasks import get_scheduler, init_default_tasks

router = APIRouter(tags=["任务调度"])


class AddIntervalTaskRequest(BaseModel):
    """添加间隔任务请求"""
    name: str = Field(..., description="任务名称")
    seconds: Optional[int] = Field(None, description="间隔秒数")
    minutes: Optional[int] = Field(None, description="间隔分钟数")
    hours: Optional[int] = Field(None, description="间隔小时数")


class AddCronTaskRequest(BaseModel):
    """添加 Cron 任务请求"""
    name: str = Field(..., description="任务名称")
    minute: Optional[str] = Field(None, description="分钟 (Cron)")
    hour: Optional[str] = Field(None, description="小时 (Cron)")
    day_of_week: Optional[str] = Field(None, description="星期 (Cron)")


@router.get("/stats")
async def get_task_stats():
    """获取任务统计"""
    scheduler = get_scheduler()
    return {
        "stats": scheduler.get_stats(),
    }


@router.get("/list")
async def list_tasks():
    """列出所有任务"""
    scheduler = get_scheduler()
    tasks = scheduler.get_all_tasks()
    
    return {
        "tasks": tasks,
        "total": len(tasks),
    }


@router.post("/interval")
async def add_interval_task(request: AddIntervalTaskRequest):
    """添加间隔任务"""
    scheduler = get_scheduler()
    
    # 映射任务函数 (这里使用预定义的任务)
    task_funcs = {
        "collect_market_data": "collect_market_data",
        "check_system_health": "check_system_health",
    }
    
    if request.name not in task_funcs:
        # 对于演示，我们只记录任务
        scheduler._tasks[request.name] = {
            "type": "interval",
            "func": "demo_task",
            "trigger": f"每 {request.seconds or 0}s {request.minutes or 0}m {request.hours or 0}h",
            "created_at": datetime.now().isoformat(),
        }
        
        return success_response(
            data={"name": request.name},
            message=f"演示任务已添加：{request.name}"
        )
    
    # 实际任务需要实现具体逻辑
    # 这里简化处理
    return success_response(message="任务添加功能开发中")


@router.post("/cron")
async def add_cron_task(request: AddCronTaskRequest):
    """添加 Cron 任务"""
    scheduler = get_scheduler()
    
    # 映射任务函数
    task_funcs = {
        "calculate_daily_pnl": "calculate_daily_pnl",
        "cleanup_old_data": "cleanup_old_data",
        "send_daily_report": "send_daily_report",
    }
    
    if request.name not in task_funcs:
        scheduler._tasks[request.name] = {
            "type": "cron",
            "func": "demo_task",
            "trigger": f"{request.minute} {request.hour} {request.day_of_week}",
            "created_at": datetime.now().isoformat(),
        }
        
        return success_response(
            data={"name": request.name},
            message=f"演示任务已添加：{request.name}"
        )
    
    return success_response(message="任务添加功能开发中")


@router.delete("/remove/{task_name}")
async def remove_task(task_name: str):
    """移除任务"""
    scheduler = get_scheduler()
    
    if task_name not in scheduler.get_all_tasks():
        raise NotFoundError("任务", task_name)
    
    scheduler.remove_task(task_name)
    
    return success_response(message=f"任务已移除：{task_name}")


@router.post("/init")
async def initialize_tasks():
    """初始化默认任务"""
    init_default_tasks()
    
    scheduler = get_scheduler()
    return success_response(
        data=scheduler.get_stats(),
        message="默认任务已初始化"
    )


@router.get("/health")
async def check_health():
    """检查调度器健康状态"""
    scheduler = get_scheduler()
    
    stats = scheduler.get_stats()
    
    return {
        "status": "healthy" if stats["running"] else "stopped",
        "running": stats["running"],
        "task_count": stats["task_count"],
    }
