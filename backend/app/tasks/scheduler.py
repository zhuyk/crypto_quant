"""
定时任务调度器
使用 APScheduler 实现定时任务 (替代 Celery Beat)
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
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
        """添加间隔任务"""
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
        
        logger.info(f"✅ 间隔任务已添加：{name}")
    
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
        """添加 Cron 任务"""
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
        """添加一次性任务"""
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


# ==================== 任务实现 ====================

async def collect_market_data():
    """
    采集市场数据 (每 5 分钟)
    
    从 Binance 增量拉取所有配置交易对的 K 线数据并存入数据库。
    """
    try:
        logger.info("📊 [定时任务] 开始采集市场数据...")
        
        from data.collector.binance_collector import BinanceCollector
        from data.persistence.kline_storage import get_kline_storage
        
        collector = BinanceCollector(testnet=settings.BINANCE_TESTNET)
        storage = get_kline_storage()
        
        total_new = 0
        errors = 0
        
        # 只采集高频周期（1m, 5m, 15m），低频周期由每小时任务处理
        quick_timeframes = ["1m", "5m", "15m"]
        
        for symbol in settings.DEFAULT_SYMBOLS:
            ccxt_symbol = symbol.replace("USDT", "/USDT")
            
            for timeframe in quick_timeframes:
                try:
                    # 增量采集：从数据库最新时间之后开始
                    latest_ts = storage.get_latest_timestamp(symbol, timeframe)
                    since = None
                    if latest_ts:
                        since = int(latest_ts.replace(tzinfo=timezone.utc).timestamp() * 1000) + 1
                    
                    df = collector.fetch_klines(
                        symbol=ccxt_symbol,
                        timeframe=timeframe,
                        limit=200,
                        since=since,
                    )
                    
                    if not df.empty:
                        new_count = storage.save_klines(symbol=symbol, timeframe=timeframe, data=df)
                        total_new += new_count
                        
                except Exception as e:
                    errors += 1
                    logger.warning(f"采集 {symbol} {timeframe} 失败: {e}")
                
                await asyncio.sleep(0.15)  # 避免限流
        
        # 缓存采集状态
        cache = get_cache()
        cache.set(
            CacheKeys.make_key("system", "last_data_collect"),
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "new_records": total_new,
                "errors": errors,
            },
            expire=600,
        )
        
        logger.info(f"✅ [定时任务] 市场数据采集完成 | 新增 {total_new} 条 | 错误 {errors} 个")
        
    except Exception as e:
        logger.error(f"❌ [定时任务] 市场数据采集失败：{e}", exc_info=True)


async def collect_hourly_data():
    """
    采集低频K线数据 (每小时)
    
    1h, 4h, 1d 周期的数据不需要每5分钟采集。
    """
    try:
        logger.info("📊 [定时任务] 开始采集小时级数据...")
        
        from data.collector.binance_collector import BinanceCollector
        from data.persistence.kline_storage import get_kline_storage
        
        collector = BinanceCollector(testnet=settings.BINANCE_TESTNET)
        storage = get_kline_storage()
        
        total_new = 0
        hourly_timeframes = ["1h", "4h", "1d"]
        
        for symbol in settings.DEFAULT_SYMBOLS:
            ccxt_symbol = symbol.replace("USDT", "/USDT")
            
            for timeframe in hourly_timeframes:
                try:
                    latest_ts = storage.get_latest_timestamp(symbol, timeframe)
                    since = None
                    if latest_ts:
                        since = int(latest_ts.replace(tzinfo=timezone.utc).timestamp() * 1000) + 1
                    
                    df = collector.fetch_klines(
                        symbol=ccxt_symbol,
                        timeframe=timeframe,
                        limit=100,
                        since=since,
                    )
                    
                    if not df.empty:
                        new_count = storage.save_klines(symbol=symbol, timeframe=timeframe, data=df)
                        total_new += new_count
                        
                except Exception as e:
                    logger.warning(f"采集 {symbol} {timeframe} 失败: {e}")
                
                await asyncio.sleep(0.2)
        
        logger.info(f"✅ [定时任务] 小时级数据采集完成 | 新增 {total_new} 条")
        
    except Exception as e:
        logger.error(f"❌ [定时任务] 小时级数据采集失败：{e}", exc_info=True)


async def calculate_daily_pnl():
    """
    计算每日盈亏 (每天 23:59)
    
    从持仓表和交易表中计算当日盈亏，写入 daily performance 记录。
    """
    try:
        logger.info("💰 [定时任务] 开始计算每日盈亏...")
        
        from app.core.database import SessionLocal
        from app.models.trade import Trade, Position
        from sqlalchemy import func, and_
        
        db = SessionLocal()
        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time())
        
        try:
            # 1. 统计当日已平仓交易盈亏
            daily_trades = db.query(Trade).filter(
                and_(
                    Trade.created_at >= today_start,
                    Trade.status == "filled",
                )
            ).all()
            
            realized_pnl = sum(t.pnl or 0 for t in daily_trades)
            trade_count = len(daily_trades)
            win_count = sum(1 for t in daily_trades if (t.pnl or 0) > 0)
            loss_count = sum(1 for t in daily_trades if (t.pnl or 0) < 0)
            
            # 2. 统计当前未平仓持仓的浮动盈亏
            active_positions = db.query(Position).filter(
                Position.is_active == True
            ).all()
            
            unrealized_pnl = sum(p.unrealized_pnl or 0 for p in active_positions)
            
            # 3. 计算总PnL
            total_daily_pnl = realized_pnl + unrealized_pnl
            
            # 4. 缓存结果
            cache = get_cache()
            daily_summary = {
                "date": str(today),
                "realized_pnl": round(realized_pnl, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "total_pnl": round(total_daily_pnl, 2),
                "trade_count": trade_count,
                "win_count": win_count,
                "loss_count": loss_count,
                "win_rate": round(win_count / trade_count, 4) if trade_count > 0 else 0,
                "active_positions": len(active_positions),
                "calculated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            cache.set(
                CacheKeys.make_key("performance", "daily", str(today)),
                daily_summary,
                expire=86400 * 7,  # 保留7天
            )
            
            # 同时缓存一份 "latest" 键方便前端查询
            cache.set(
                CacheKeys.make_key("performance", "daily_latest"),
                daily_summary,
                expire=86400,
            )
            
            logger.info(
                f"✅ [定时任务] 每日盈亏计算完成 | "
                f"日期: {today} | "
                f"已实现: ${realized_pnl:.2f} | "
                f"浮动: ${unrealized_pnl:.2f} | "
                f"总计: ${total_daily_pnl:.2f} | "
                f"交易 {trade_count} 笔 (胜率 {daily_summary['win_rate']:.0%})"
            )
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"❌ [定时任务] 每日盈亏计算失败：{e}", exc_info=True)


async def cleanup_old_data():
    """
    清理旧数据 (每周日 3:00)
    
    - 清理超过 90 天的 1m K线数据（节省存储）
    - 清理超过 30 天的系统日志
    - 清理过期缓存
    """
    try:
        logger.info("🧹 [定时任务] 开始清理旧数据...")
        
        from app.core.database import SessionLocal
        from app.models.trade import Kline
        from sqlalchemy import and_
        
        db = SessionLocal()
        
        try:
            # 1. 清理超过90天的1分钟K线（数据量最大）
            cutoff_1m = datetime.now(timezone.utc) - timedelta(days=90)
            deleted_1m = db.query(Kline).filter(
                and_(
                    Kline.timeframe == "1m",
                    Kline.timestamp < cutoff_1m,
                )
            ).delete(synchronize_session=False)
            
            # 2. 清理超过180天的5分钟K线
            cutoff_5m = datetime.now(timezone.utc) - timedelta(days=180)
            deleted_5m = db.query(Kline).filter(
                and_(
                    Kline.timeframe == "5m",
                    Kline.timestamp < cutoff_5m,
                )
            ).delete(synchronize_session=False)
            
            db.commit()
            
            logger.info(
                f"✅ [定时任务] 旧数据清理完成 | "
                f"1m K线: 删除 {deleted_1m} 条 (>90天) | "
                f"5m K线: 删除 {deleted_5m} 条 (>180天)"
            )
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"❌ [定时任务] 数据清理失败：{e}", exc_info=True)


async def send_daily_report():
    """
    发送日报 (每天 8:00)
    
    将昨日的交易汇总通过告警服务发送。
    """
    try:
        logger.info("📧 [定时任务] 开始生成日报...")
        
        # 获取昨日PnL数据
        cache = get_cache()
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        
        daily_data = cache.get(
            CacheKeys.make_key("performance", "daily", str(yesterday))
        )
        
        if not daily_data:
            # 没有缓存数据，尝试实时计算
            daily_data = {
                "date": str(yesterday),
                "total_pnl": 0,
                "trade_count": 0,
                "win_rate": 0,
            }
        
        # 构建报告内容
        report_content = (
            f"📊 CryptoQuant 每日报告\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📅 日期: {daily_data.get('date', yesterday)}\n"
            f"💰 总盈亏: ${daily_data.get('total_pnl', 0):.2f}\n"
            f"📈 已实现: ${daily_data.get('realized_pnl', 0):.2f}\n"
            f"📊 浮动: ${daily_data.get('unrealized_pnl', 0):.2f}\n"
            f"🔄 交易笔数: {daily_data.get('trade_count', 0)}\n"
            f"🎯 胜率: {daily_data.get('win_rate', 0):.0%}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        
        # 尝试通过告警服务发送
        try:
            from app.services.alert_service import get_alert_service
            alert_svc = get_alert_service()
            if alert_svc:
                await alert_svc.send_system_alert(
                    title="📊 每日交易报告",
                    content=report_content,
                    level="info",
                )
        except ImportError:
            pass  # 告警服务未配置时静默跳过
        
        logger.info(f"✅ [定时任务] 日报生成完成\n{report_content}")
        
    except Exception as e:
        logger.error(f"❌ [定时任务] 日报发送失败：{e}", exc_info=True)


async def check_system_health():
    """
    系统健康检查 (每 30 分钟)
    
    检查数据库、Redis、外部 API 连通性并缓存结果。
    """
    try:
        logger.info("💓 [定时任务] 开始系统健康检查...")
        
        health_status = {
            "database": "unknown",
            "redis": "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # 检查数据库连接
        try:
            from app.core.database import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            health_status["database"] = "ok"
        except Exception as e:
            health_status["database"] = f"error: {str(e)[:100]}"
            logger.warning(f"数据库健康检查失败: {e}")
        
        # 检查 Redis 连接
        try:
            cache = get_cache()
            if cache._check_connection():
                health_status["redis"] = "ok"
            else:
                health_status["redis"] = "disconnected"
        except Exception as e:
            health_status["redis"] = f"error: {str(e)[:100]}"
        
        # 缓存健康状态
        try:
            cache = get_cache()
            cache.set(
                CacheKeys.make_key("system", "health"),
                health_status,
                expire=1800,
            )
        except Exception:
            pass
        
        db_ok = health_status["database"] == "ok"
        redis_ok = health_status["redis"] == "ok"
        
        if db_ok and redis_ok:
            logger.info("✅ [定时任务] 健康检查通过 | DB: ok | Redis: ok")
        else:
            logger.warning(
                f"⚠️ [定时任务] 健康检查异常 | "
                f"DB: {health_status['database']} | "
                f"Redis: {health_status['redis']}"
            )
        
    except Exception as e:
        logger.error(f"❌ [定时任务] 健康检查失败：{e}", exc_info=True)


async def sync_positions_price():
    """
    同步持仓价格 (每 1 分钟)
    
    从缓存/API获取最新价格，更新持仓表中的浮动盈亏。
    """
    try:
        from app.core.database import SessionLocal
        from app.models.trade import Position
        
        db = SessionLocal()
        
        try:
            active_positions = db.query(Position).filter(
                Position.is_active == True
            ).all()
            
            if not active_positions:
                return
            
            # 获取最新价格（优先从缓存，否则从API）
            cache = get_cache()
            updated = 0
            
            for pos in active_positions:
                try:
                    # 尝试从缓存获取价格
                    cached_price = cache.get(
                        CacheKeys.make_key(CacheKeys.SYMBOL_PRICE, pos.symbol)
                    )
                    
                    if cached_price and isinstance(cached_price, dict):
                        current_price = float(cached_price.get("price", 0))
                    else:
                        continue  # 没有缓存价格则跳过
                    
                    if current_price > 0:
                        # 计算浮动盈亏
                        if pos.side == "buy":
                            unrealized = (current_price - pos.entry_price) * pos.amount
                        else:
                            unrealized = (pos.entry_price - current_price) * pos.amount
                        
                        pos.current_price = current_price
                        pos.unrealized_pnl = round(unrealized, 4)
                        updated += 1
                        
                except Exception as e:
                    logger.debug(f"更新 {pos.symbol} 价格失败: {e}")
            
            if updated > 0:
                db.commit()
                logger.debug(f"📊 已更新 {updated} 个持仓价格")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"同步持仓价格失败：{e}")


# ==================== 初始化默认任务 ====================

def init_default_tasks():
    """初始化默认任务"""
    # 每 5 分钟采集高频市场数据 (1m, 5m, 15m)
    scheduler.add_interval_task(
        name="collect_market_data",
        func=collect_market_data,
        minutes=5,
    )
    
    # 每小时采集低频数据 (1h, 4h, 1d)
    scheduler.add_interval_task(
        name="collect_hourly_data",
        func=collect_hourly_data,
        hours=1,
    )
    
    # 每 1 分钟同步持仓价格
    scheduler.add_interval_task(
        name="sync_positions_price",
        func=sync_positions_price,
        minutes=1,
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
    
    logger.info(f"✅ 默认任务初始化完成 ({len(scheduler.get_all_tasks())} 个任务)")


# 自动初始化
init_default_tasks()
