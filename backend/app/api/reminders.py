"""
日历提醒 API

支持:
- CRUD 提醒事项
- 按日期范围查询
- 手动触发/标记完成
- 批量操作
- 预设模板 (价格提醒、费率提醒、合约到期等)
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

from app.core.database import SessionLocal
from app.models.reminder import Reminder

logger = logging.getLogger(__name__)

router = APIRouter(tags=["日历提醒"])


# ============================================================
# Request / Response Models
# ============================================================

class ReminderCreate(BaseModel):
    """创建提醒请求"""
    title: str = Field(..., description="提醒标题", max_length=256)
    description: Optional[str] = Field(None, description="详细描述")
    remind_at: str = Field(..., description="提醒时间 (ISO 格式, 如 2026-05-23T09:00:00Z)")
    reminder_type: str = Field("custom", description="类型: price_alert/funding_rate/rebalance/custom/expiry/report")
    priority: str = Field("medium", description="优先级: low/medium/high/critical")
    repeat_rule: str = Field("none", description="重复: none/daily/weekly/monthly/custom_cron")
    repeat_cron: Optional[str] = Field(None, description="自定义 cron (repeat_rule=custom_cron 时)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="关联数据 JSON")
    notify_channels: List[str] = Field(default=["app"], description="通知方式: app/email/dingtalk")


class ReminderUpdate(BaseModel):
    """更新提醒请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    remind_at: Optional[str] = None
    reminder_type: Optional[str] = None
    priority: Optional[str] = None
    repeat_rule: Optional[str] = None
    repeat_cron: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    notify_channels: Optional[List[str]] = None
    is_active: Optional[bool] = None


class PriceAlertCreate(BaseModel):
    """价格提醒快捷创建"""
    symbol: str = Field(..., description="交易对 (如 BTCUSDT)")
    target_price: float = Field(..., description="目标价格")
    condition: str = Field("above", description="条件: above/below")
    notify_channels: List[str] = Field(default=["app"], description="通知方式")


class FundingRateAlertCreate(BaseModel):
    """资金费率提醒快捷创建"""
    symbol: str = Field(..., description="交易对")
    min_rate: float = Field(0.001, description="最小费率阈值 (触发条件)")
    exchange: str = Field("binance", description="交易所")
    notify_channels: List[str] = Field(default=["app"], description="通知方式")


# ============================================================
# CRUD 端点
# ============================================================

@router.get("/list")
async def list_reminders(
    user_id: int = Query(1, description="用户 ID"),
    active_only: bool = Query(True, description="只显示活跃的"),
    reminder_type: Optional[str] = Query(None, description="按类型筛选"),
    start_date: Optional[str] = Query(None, description="开始日期 (ISO)"),
    end_date: Optional[str] = Query(None, description="结束日期 (ISO)"),
    limit: int = Query(50, description="最大数量"),
):
    """获取提醒列表"""
    db = SessionLocal()
    try:
        query = db.query(Reminder).filter(Reminder.user_id == user_id)

        if active_only:
            query = query.filter(Reminder.is_active == True)

        if reminder_type:
            query = query.filter(Reminder.reminder_type == reminder_type)

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                query = query.filter(Reminder.remind_at >= start_dt)
            except ValueError:
                pass

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                query = query.filter(Reminder.remind_at <= end_dt)
            except ValueError:
                pass

        reminders = query.order_by(Reminder.remind_at.asc()).limit(limit).all()

        return {
            "success": True,
            "count": len(reminders),
            "reminders": [r.to_dict() for r in reminders],
        }
    finally:
        db.close()


@router.get("/upcoming")
async def get_upcoming_reminders(
    user_id: int = Query(1, description="用户 ID"),
    hours: int = Query(24, description="未来多少小时内"),
    limit: int = Query(10, description="最大数量"),
):
    """获取即将到来的提醒"""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        future = now + timedelta(hours=hours)

        reminders = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.is_active == True,
            Reminder.is_triggered == False,
            Reminder.remind_at >= now,
            Reminder.remind_at <= future,
        ).order_by(Reminder.remind_at.asc()).limit(limit).all()

        return {
            "success": True,
            "count": len(reminders),
            "reminders": [r.to_dict() for r in reminders],
        }
    finally:
        db.close()


@router.get("/calendar")
async def get_calendar_view(
    user_id: int = Query(1, description="用户 ID"),
    year: int = Query(2026, description="年份"),
    month: int = Query(5, description="月份"),
):
    """
    获取日历视图数据
    
    返回指定月份每天的提醒数量和列表，供前端日历组件渲染。
    """
    db = SessionLocal()
    try:
        # 计算月份范围
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)

        reminders = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.remind_at >= start,
            Reminder.remind_at < end,
        ).order_by(Reminder.remind_at.asc()).all()

        # 按日分组
        days: Dict[str, List[dict]] = {}
        for r in reminders:
            day_key = r.remind_at.strftime("%Y-%m-%d")
            if day_key not in days:
                days[day_key] = []
            days[day_key].append(r.to_dict())

        return {
            "success": True,
            "year": year,
            "month": month,
            "total_reminders": len(reminders),
            "days": days,
        }
    finally:
        db.close()


@router.get("/{reminder_id}")
async def get_reminder(reminder_id: int):
    """获取单个提醒详情"""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            raise HTTPException(status_code=404, detail="提醒不存在")
        return {"success": True, "reminder": reminder.to_dict()}
    finally:
        db.close()


@router.post("/create")
async def create_reminder(req: ReminderCreate, user_id: int = Query(1)):
    """创建新提醒"""
    db = SessionLocal()
    try:
        # 解析时间
        try:
            remind_at = datetime.fromisoformat(req.remind_at.replace("Z", "+00:00"))
            # 存储为 naive UTC
            if remind_at.tzinfo:
                remind_at = remind_at.replace(tzinfo=None)
        except ValueError:
            raise HTTPException(status_code=400, detail="remind_at 格式错误，请使用 ISO 格式")

        reminder = Reminder(
            user_id=user_id,
            title=req.title,
            description=req.description,
            remind_at=remind_at,
            reminder_type=req.reminder_type,
            priority=req.priority,
            repeat_rule=req.repeat_rule,
            repeat_cron=req.repeat_cron,
            metadata_json=req.metadata,
            notify_channels=req.notify_channels,
        )

        db.add(reminder)
        db.commit()
        db.refresh(reminder)

        logger.info(f"📅 创建提醒: {reminder.title} @ {reminder.remind_at}")

        return {
            "success": True,
            "message": "提醒创建成功",
            "reminder": reminder.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建提醒失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.put("/{reminder_id}")
async def update_reminder(reminder_id: int, req: ReminderUpdate):
    """更新提醒"""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            raise HTTPException(status_code=404, detail="提醒不存在")

        # 更新字段
        if req.title is not None:
            reminder.title = req.title
        if req.description is not None:
            reminder.description = req.description
        if req.remind_at is not None:
            try:
                remind_at = datetime.fromisoformat(req.remind_at.replace("Z", "+00:00"))
                if remind_at.tzinfo:
                    remind_at = remind_at.replace(tzinfo=None)
                reminder.remind_at = remind_at
            except ValueError:
                raise HTTPException(status_code=400, detail="remind_at 格式错误")
        if req.reminder_type is not None:
            reminder.reminder_type = req.reminder_type
        if req.priority is not None:
            reminder.priority = req.priority
        if req.repeat_rule is not None:
            reminder.repeat_rule = req.repeat_rule
        if req.repeat_cron is not None:
            reminder.repeat_cron = req.repeat_cron
        if req.metadata is not None:
            reminder.metadata_json = req.metadata
        if req.notify_channels is not None:
            reminder.notify_channels = req.notify_channels
        if req.is_active is not None:
            reminder.is_active = req.is_active

        db.commit()
        db.refresh(reminder)

        return {"success": True, "message": "提醒已更新", "reminder": reminder.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/{reminder_id}")
async def delete_reminder(reminder_id: int):
    """删除提醒"""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            raise HTTPException(status_code=404, detail="提醒不存在")

        db.delete(reminder)
        db.commit()

        return {"success": True, "message": "提醒已删除"}
    finally:
        db.close()


@router.post("/{reminder_id}/trigger")
async def trigger_reminder(reminder_id: int):
    """手动触发提醒 (标记为已触发)"""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            raise HTTPException(status_code=404, detail="提醒不存在")

        reminder.is_triggered = True
        reminder.triggered_at = datetime.now(timezone.utc).replace(tzinfo=None)
        reminder.trigger_count += 1

        # 如果是重复提醒，重置触发状态并计算下次时间
        if reminder.repeat_rule != "none":
            reminder.is_triggered = False
            reminder.remind_at = _calculate_next_remind_time(
                reminder.remind_at, reminder.repeat_rule
            )

        db.commit()
        db.refresh(reminder)

        return {"success": True, "message": "提醒已触发", "reminder": reminder.to_dict()}
    finally:
        db.close()


@router.post("/{reminder_id}/dismiss")
async def dismiss_reminder(reminder_id: int):
    """关闭/忽略提醒"""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            raise HTTPException(status_code=404, detail="提醒不存在")

        if reminder.repeat_rule == "none":
            # 非重复提醒直接停用
            reminder.is_active = False
        else:
            # 重复提醒推进到下次
            reminder.is_triggered = False
            reminder.remind_at = _calculate_next_remind_time(
                reminder.remind_at, reminder.repeat_rule
            )

        reminder.triggered_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()

        return {"success": True, "message": "提醒已关闭"}
    finally:
        db.close()


# ============================================================
# 快捷模板
# ============================================================

@router.post("/template/price_alert")
async def create_price_alert(req: PriceAlertCreate, user_id: int = Query(1)):
    """
    快捷创建价格提醒
    
    当价格达到目标值时触发通知。
    """
    condition_text = "突破" if req.condition == "above" else "跌破"
    title = f"💰 {req.symbol} {condition_text} ${req.target_price}"
    description = f"当 {req.symbol} 价格{condition_text} {req.target_price} USDT 时提醒"

    db = SessionLocal()
    try:
        reminder = Reminder(
            user_id=user_id,
            title=title,
            description=description,
            remind_at=datetime(2099, 12, 31),  # 价格提醒不基于时间，由监控服务触发
            reminder_type="price_alert",
            priority="high",
            repeat_rule="none",
            metadata_json={
                "symbol": req.symbol,
                "target_price": req.target_price,
                "condition": req.condition,
            },
            notify_channels=req.notify_channels,
        )

        db.add(reminder)
        db.commit()
        db.refresh(reminder)

        return {"success": True, "message": f"价格提醒已创建: {title}", "reminder": reminder.to_dict()}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/template/funding_rate_alert")
async def create_funding_rate_alert(req: FundingRateAlertCreate, user_id: int = Query(1)):
    """
    快捷创建资金费率提醒
    
    当指定交易对的 funding rate 超过阈值时触发通知。
    """
    title = f"📊 {req.symbol} 费率提醒 (>{req.min_rate*100:.2f}%)"
    description = f"当 {req.exchange} 上 {req.symbol} 的资金费率超过 {req.min_rate*100:.3f}% 时提醒"

    db = SessionLocal()
    try:
        reminder = Reminder(
            user_id=user_id,
            title=title,
            description=description,
            remind_at=datetime(2099, 12, 31),  # 由监控服务触发
            reminder_type="funding_rate",
            priority="medium",
            repeat_rule="none",
            metadata_json={
                "symbol": req.symbol,
                "min_rate": req.min_rate,
                "exchange": req.exchange,
            },
            notify_channels=req.notify_channels,
        )

        db.add(reminder)
        db.commit()
        db.refresh(reminder)

        return {"success": True, "message": f"费率提醒已创建", "reminder": reminder.to_dict()}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/stats")
async def get_reminder_stats(user_id: int = Query(1)):
    """获取提醒统计"""
    db = SessionLocal()
    try:
        total = db.query(Reminder).filter(Reminder.user_id == user_id).count()
        active = db.query(Reminder).filter(
            Reminder.user_id == user_id, Reminder.is_active == True
        ).count()
        triggered_today = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.triggered_at >= datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, tzinfo=None
            ),
        ).count()

        # 即将到来 (24h 内)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        upcoming = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.is_active == True,
            Reminder.is_triggered == False,
            Reminder.remind_at >= now,
            Reminder.remind_at <= now + timedelta(hours=24),
        ).count()

        return {
            "success": True,
            "stats": {
                "total": total,
                "active": active,
                "triggered_today": triggered_today,
                "upcoming_24h": upcoming,
            },
        }
    finally:
        db.close()


# ============================================================
# Helper
# ============================================================

def _calculate_next_remind_time(current: datetime, repeat_rule: str) -> datetime:
    """计算重复提醒的下次触发时间"""
    if repeat_rule == "daily":
        return current + timedelta(days=1)
    elif repeat_rule == "weekly":
        return current + timedelta(weeks=1)
    elif repeat_rule == "monthly":
        # 简单加 30 天
        return current + timedelta(days=30)
    else:
        # none 或 custom_cron 不自动推进
        return current
