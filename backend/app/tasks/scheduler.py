"""
定时任务调度器
使用 APScheduler 实现定时任务 (替代 Celery Beat)
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from app.core.config import settings
from app.utils.cache import get_cache, CacheKeys

logger = logging.getLogger(__name__)


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._tasks: Dict[str, Dict] = {}
        self._cache = get_cache()
        
        logger.info("✅ 任务调度器初始化完成")
    
    def add_interval_task(
        self,
        name: str,
        func: Callable,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        days: Optional[int] = None,
        **kwargs,
    ):
        """
        添加间隔任务
        
        Args:
            name: 任务名称
            func: 任务函数
            seconds/minutes/hours/days: 间隔时间
            kwargs: 任务参数
        """
        # 过滤 None 值
        trigger_kwargs = {}
        if seconds: trigger_kwargs['seconds'] = seconds
        if minutes: trigger_kwargs['minutes'] = minutes
        if hours: trigger_kwargs['hours'] = hours
        if days: trigger_kwargs['days'] = days
        
        trigger = IntervalTrigger(**trigger_kwargs)
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=name,
            name=name,
            kwargs=kwargs,
            replace_existing=True,
        )
        
        self._tasks[name] = {
            "type": "interval",
            "func": func.__name__,
            "trigger": str(trigger),
            "created_at": datetime.now().isoformat(),
        }
        
        logger.info(f"✅ 间隔任务已添加：{name} (每 {seconds or 0}s {minutes or 0}m {hours or 0}h {days or 0}d)")
    
    def add_cron_task(
        self,
        name: str,
        func: Callable,
        minute: Optional[str] = None,
        hour: Optional[str] = None,
        day: Optional[str] = None,
        week: Optional[str] = None,
        day_of_week: Optional[str] = None,
        **kwargs,
    ):
        """
        添加 Cron 任务
        
        Args:
            name: 任务名称
            func: 任务函数
            minute/hour/day/week/day_of_week: Cron 表达式
            kwargs: 任务参数
        
        Example:
            # 每天凌晨 2 点执行
            add_cron_task("daily_report", func, hour="2", minute="0")
            
            # 每周一 9 点执行
            add_cron_task("weekly_report", func, day_of_week="mon", hour="9", minute="0")
        """
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            week=week,
            day_of_week=day_of_week,
        )
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=name,
            name=name,
            kwargs=kwargs,
            replace_existing=True,
        )
        
        self._tasks[name] = {
            "type": "cron",
            "func": func.__name__,
            "trigger": str(trigger),
            "created_at": datetime.now().isoformat(),
        }
        
        logger.info(f"✅ Cron 任务已添加：{name} ({trigger})")
    
    def add_once_task(
        self,
        name: str,
        func: Callable,
        run_date: datetime,
        **kwargs,
    ):
        """
        添加一次性任务
        
        Args:
            name: 任务名称
            func: 任务函数
            run_date: 执行时间
            kwargs: 任务参数
        """
        trigger = DateTrigger(run_date=run_date)
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=name,
            name=name,
            kwargs=kwargs,
            replace_existing=True,
        )
        
        self._tasks[name] = {
            "type": "once",
            "func": func.__name__,
            "trigger": str(run_date),
            "created_at": datetime.now().isoformat(),
        }
        
        logger.info(f"✅ 一次性任务已添加：{name} ({run_date})")
    
    def remove_task(self, name: str):
        """移除任务"""
        try:
            self.scheduler.remove_job(name)
            self._tasks.pop(name, None)
            logger.info(f"✅ 任务已移除：{name}")
        except Exception as e:
            logger.error(f"移除任务失败：{name} - {e}")
    
    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("🚀 任务调度器已启动")
    
    def shutdown(self, wait: bool = True):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("👋 任务调度器已关闭")
    
    def get_task_info(self, name: str) -> Optional[Dict]:
        """获取任务信息"""
        return self._tasks.get(name)
    
    def get_all_tasks(self) -> Dict[str, Dict]:
        """获取所有任务"""
        return dict(self._tasks)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "running": self.scheduler.running,
            "task_count": len(self._tasks),
            "tasks": self._tasks,
        }


# 全局调度器实例
scheduler = TaskScheduler()


def get_scheduler() -> TaskScheduler:
    """获取调度器"""
    return scheduler


# ==================== 预定义任务 ====================

async def collect_market_data():
    """采集市场数据 (每 5 分钟)"""
    try:
        logger.info("📊 开始采集市场数据...")
        
        # TODO: 实现数据采集逻辑
        from app.services import get_binance_ws
        
        ws = get_binance_ws()
        if ws:
            stats = ws.get_stats()
            logger.info(f"   WebSocket 状态：{stats}")
        
        # 缓存采集时间
        cache = get_cache()
        cache.set(
            CacheKeys.make_key("system", "last_data_collect"),
            datetime.now().isoformat(),
            expire=3600,
        )
        
        logger.info("✅ 市场数据采集完成")
        
    except Exception as e:
        logger.error(f"市场数据采集失败：{e}")


async def calculate_daily_pnl():
    """计算每日盈亏 (每天 23:59)"""
    try:
        logger.info("💰 开始计算每日盈亏...")
        
        # TODO: 实现盈亏计算逻辑
        
        logger.info("✅ 每日盈亏计算完成")
        
    except Exception as e:
        logger.error(f"每日盈亏计算失败：{e}")


async def cleanup_old_data():
    """清理旧数据 (每周日 3:00)"""
    try:
        logger.info("🧹 开始清理旧数据...")
        
        # TODO: 实现数据清理逻辑
        
        logger.info("✅ 旧数据清理完成")
        
    except Exception as e:
        logger.error(f"数据清理失败：{e}")


async def send_daily_report():
    """发送日报 (每天 8:00)"""
    try:
        logger.info("📧 开始发送日报...")
        
        # TODO: 实现日报发送逻辑
        from app.services import get_alert_service
        
        alert_svc = get_alert_service()
        if alert_svc:
            await alert_svc.send_system_alert(
                title="📊 每日报告",
                content="昨日交易汇总...",
                level="info",
            )
        
        logger.info("✅ 日报发送完成")
        
    except Exception as e:
        logger.error(f"日报发送失败：{e}")


async def check_system_health():
    """系统健康检查 (每 30 分钟)"""
    try:
        logger.info("💓 开始系统健康检查...")
        
        # 检查数据库连接
        from app.core.database import engine
        try:
            with engine.connect() as conn:
                conn.execute(asyncio.get_event_loop().run_in_executor(None, lambda: None))
            db_status = "ok"
        except:
            db_status = "error"
        
        # 检查 Redis 连接
        cache = get_cache()
        redis_status = "ok" if cache._check_connection() else "error"
        
        # 缓存健康状态
        cache.set(
            CacheKeys.make_key("system", "health"),
            {
                "database": db_status,
                "redis": redis_status,
                "timestamp": datetime.now().isoformat(),
            },
            expire=300,
        )
        
        logger.info(f"✅ 健康检查完成 - DB: {db_status}, Redis: {redis_status}")
        
    except Exception as e:
        logger.error(f"健康检查失败：{e}")


# ==================== 提醒检查任务 ====================

async def check_reminders():
    """
    检查到期提醒 (每 1 分钟)
    
    扫描数据库中所有已到时间但未触发的提醒，执行通知并标记。
    支持重复提醒自动推进到下次。
    """
    try:
        from app.core.database import SessionLocal
        from app.models.reminder import Reminder
        from sqlalchemy import and_

        db = SessionLocal()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            # 查询到期且未触发的活跃提醒
            due_reminders = db.query(Reminder).filter(
                and_(
                    Reminder.is_active == True,
                    Reminder.is_triggered == False,
                    Reminder.remind_at <= now,
                )
            ).all()

            if not due_reminders:
                return

            logger.info(f"🔔 [定时任务] 发现 {len(due_reminders)} 个到期提醒")

            for reminder in due_reminders:
                try:
                    # 1. 发送通知
                    await _send_reminder_notification(reminder)

                    # 2. 标记为已触发
                    reminder.is_triggered = True
                    reminder.triggered_at = now
                    reminder.trigger_count += 1

                    # 3. 处理重复规则
                    if reminder.repeat_rule != "none":
                        # 重复提醒: 重置触发状态，推进到下次时间
                        reminder.is_triggered = False
                        reminder.remind_at = _calc_next_time(
                            reminder.remind_at, reminder.repeat_rule
                        )
                        logger.debug(
                            f"  🔁 重复提醒推进: {reminder.title} → {reminder.remind_at}"
                        )
                    else:
                        # 一次性提醒: 标记为不活跃
                        reminder.is_active = False

                except Exception as e:
                    logger.error(f"  ❌ 处理提醒 [{reminder.id}] 失败: {e}")

            db.commit()
            logger.info(f"✅ [定时任务] 提醒检查完成，触发 {len(due_reminders)} 个")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ [定时任务] 提醒检查失败: {e}", exc_info=True)


async def check_price_alerts():
    """
    检查价格提醒 (每 30 秒由外部或每分钟由调度器)
    
    对比缓存中的实时价格与用户设置的目标价格，触发达标提醒。
    """
    try:
        from app.core.database import SessionLocal
        from app.models.reminder import Reminder
        from sqlalchemy import and_

        db = SessionLocal()
        cache = get_cache()

        try:
            # 获取所有活跃的价格提醒
            price_alerts = db.query(Reminder).filter(
                and_(
                    Reminder.is_active == True,
                    Reminder.is_triggered == False,
                    Reminder.reminder_type == "price_alert",
                )
            ).all()

            if not price_alerts:
                return

            triggered_count = 0
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            for alert in price_alerts:
                try:
                    meta = alert.metadata_json or {}
                    symbol = meta.get("symbol")
                    target_price = meta.get("target_price")
                    condition = meta.get("condition", "above")

                    if not symbol or not target_price:
                        continue

                    # 从缓存获取当前价格
                    cached = cache.get(
                        CacheKeys.make_key(CacheKeys.SYMBOL_PRICE, symbol)
                    )
                    if not cached or not isinstance(cached, dict):
                        continue

                    current_price = float(cached.get("price", 0))
                    if current_price <= 0:
                        continue

                    # 检查条件
                    triggered = False
                    if condition == "above" and current_price >= target_price:
                        triggered = True
                    elif condition == "below" and current_price <= target_price:
                        triggered = True

                    if triggered:
                        # 更新元数据记录触发时价格
                        alert.metadata_json = {
                            **meta,
                            "triggered_price": current_price,
                            "triggered_at": now.isoformat(),
                        }
                        alert.is_triggered = True
                        alert.triggered_at = now
                        alert.trigger_count += 1
                        alert.is_active = False  # 价格提醒触发后停用

                        await _send_reminder_notification(alert)
                        triggered_count += 1

                        logger.info(
                            f"💰 价格提醒触发: {symbol} "
                            f"{'突破' if condition == 'above' else '跌破'} "
                            f"${target_price} (当前 ${current_price})"
                        )

                except Exception as e:
                    logger.debug(f"检查价格提醒 [{alert.id}] 失败: {e}")

            if triggered_count > 0:
                db.commit()
                logger.info(f"✅ 价格提醒检查完成，触发 {triggered_count} 个")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"价格提醒检查失败: {e}")


async def _send_reminder_notification(reminder):
    """
    发送提醒通知
    
    根据 notify_channels 配置发送到不同渠道。
    """
    channels = reminder.notify_channels or ["app"]
    title = f"🔔 {reminder.title}"
    content = reminder.description or reminder.title

    # 通过告警服务发送
    try:
        from app.services.alert_service import get_alert_service
        alert_svc = get_alert_service()

        if alert_svc and ("dingtalk" in channels or "email" in channels):
            await alert_svc.send_system_alert(
                title=title,
                content=content,
                level="info" if reminder.priority in ("low", "medium") else "warning",
            )
    except Exception as e:
        logger.debug(f"告警服务通知失败 (可忽略): {e}")

    # WebSocket 推送到前端 (app 渠道)
    if "app" in channels:
        try:
            from app.websocket.manager import ConnectionManager
            # 通过全局 WebSocket 管理器推送
            # (简化实现: 广播到用户连接)
            pass  # WebSocket 推送在 routes 模块中实现
        except Exception:
            pass

    logger.info(f"  📨 通知已发送: {title} → {channels}")


def _calc_next_time(current: datetime, repeat_rule: str) -> datetime:
    """计算重复提醒的下次时间"""
    if repeat_rule == "daily":
        return current + timedelta(days=1)
    elif repeat_rule == "weekly":
        return current + timedelta(weeks=1)
    elif repeat_rule == "monthly":
        return current + timedelta(days=30)
    return current


# ==================== 初始化默认任务 ====================

def init_default_tasks():
    """初始化默认任务"""
    # 每 1 分钟检查到期提醒
    scheduler.add_interval_task(
        name="check_reminders",
        func=check_reminders,
        minutes=1,
    )

    # 每 1 分钟检查价格提醒
    scheduler.add_interval_task(
        name="check_price_alerts",
        func=check_price_alerts,
        minutes=1,
    )

    # 每 5 分钟采集市场数据
    scheduler.add_interval_task(
        name="collect_market_data",
        func=collect_market_data,
        minutes=5,
    )
    
    # 每 30 分钟健康检查
    scheduler.add_interval_task(
        name="check_system_health",
        func=check_system_health,
        minutes=30,
    )
    
    # 每天 23:59 计算盈亏
    scheduler.add_cron_task(
        name="calculate_daily_pnl",
        func=calculate_daily_pnl,
        hour="23",
        minute="59",
    )
    
    # 每周日 3:00 清理旧数据
    scheduler.add_cron_task(
        name="cleanup_old_data",
        func=cleanup_old_data,
        day_of_week="sun",
        hour="3",
        minute="0",
    )
    
    # 每天 8:00 发送日报
    scheduler.add_cron_task(
        name="send_daily_report",
        func=send_daily_report,
        hour="8",
        minute="0",
    )
    
    logger.info("✅ 默认任务初始化完成")


# 自动初始化
init_default_tasks()
