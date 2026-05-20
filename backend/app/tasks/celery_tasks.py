"""
Celery 任务定义

这些任务是 scheduler.py 中异步任务的 Celery 包装。
在单机部署时使用 APScheduler，在分布式部署时使用 Celery Beat。
"""
import asyncio
import logging
from functools import wraps

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    """在 Celery worker 中运行 async 函数"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


@celery_app.task(
    name="app.tasks.celery_tasks.collect_market_data_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def collect_market_data_task(self):
    """采集高频市场数据 (1m, 5m, 15m)"""
    try:
        from app.tasks.scheduler import collect_market_data
        run_async(collect_market_data())
    except Exception as exc:
        logger.error(f"Celery 市场数据采集失败: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.celery_tasks.collect_hourly_data_task",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def collect_hourly_data_task(self):
    """采集低频K线数据 (1h, 4h, 1d)"""
    try:
        from app.tasks.scheduler import collect_hourly_data
        run_async(collect_hourly_data())
    except Exception as exc:
        logger.error(f"Celery 小时级数据采集失败: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.celery_tasks.calculate_daily_pnl_task",
    bind=True,
    max_retries=1,
)
def calculate_daily_pnl_task(self):
    """计算每日盈亏"""
    try:
        from app.tasks.scheduler import calculate_daily_pnl
        run_async(calculate_daily_pnl())
    except Exception as exc:
        logger.error(f"Celery 每日盈亏计算失败: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.celery_tasks.send_daily_report_task",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def send_daily_report_task(self):
    """发送每日报告"""
    try:
        from app.tasks.scheduler import send_daily_report
        run_async(send_daily_report())
    except Exception as exc:
        logger.error(f"Celery 日报发送失败: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.celery_tasks.cleanup_old_data_task",
    bind=True,
    max_retries=1,
)
def cleanup_old_data_task(self):
    """清理旧数据"""
    try:
        from app.tasks.scheduler import cleanup_old_data
        run_async(cleanup_old_data())
    except Exception as exc:
        logger.error(f"Celery 数据清理失败: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.celery_tasks.check_system_health_task",
    bind=True,
    max_retries=0,
)
def check_system_health_task(self):
    """系统健康检查"""
    try:
        from app.tasks.scheduler import check_system_health
        run_async(check_system_health())
    except Exception as exc:
        logger.error(f"Celery 健康检查失败: {exc}")


# === 按需触发的任务（非定时） ===

@celery_app.task(
    name="app.tasks.celery_tasks.run_backtest_task",
    bind=True,
    max_retries=0,
    soft_time_limit=300,
    time_limit=600,
)
def run_backtest_task(self, strategy_name, symbol, params, start_time, end_time, timeframe, initial_capital=100000):
    """
    运行回测任务（耗时操作，适合放到 Celery）
    
    Args:
        strategy_name: 策略名称
        symbol: 交易对
        params: 策略参数
        start_time: 开始时间戳
        end_time: 结束时间戳
        timeframe: 时间周期
        initial_capital: 初始资金
    """
    try:
        logger.info(f"🔬 [Celery] 开始回测: {strategy_name} {symbol} {timeframe}")
        
        from strategies.registry import create_strategy
        from engine.backtester.core import Backtester
        from data.persistence.kline_storage import get_kline_storage
        from datetime import datetime
        
        # 从数据库获取历史数据
        storage = get_kline_storage()
        data = storage.get_klines(
            symbol=symbol,
            timeframe=timeframe,
            start_time=datetime.fromtimestamp(start_time / 1000) if start_time > 1e10 else datetime.fromtimestamp(start_time),
            end_time=datetime.fromtimestamp(end_time / 1000) if end_time > 1e10 else datetime.fromtimestamp(end_time),
            limit=10000,
        )
        
        if data.empty:
            return {"error": "没有足够的历史数据", "status": "failed"}
        
        # 创建策略
        strategy = create_strategy(strategy_name, params)
        if not strategy:
            return {"error": f"策略 {strategy_name} 不存在", "status": "failed"}
        
        # 运行回测
        backtester = Backtester(initial_capital=initial_capital)
        report = backtester.run(strategy=strategy, data=data)
        
        result = {
            "status": "completed",
            "strategy": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "total_return": report.total_return,
            "sharpe_ratio": report.sharpe_ratio,
            "max_drawdown": report.max_drawdown,
            "total_trades": report.total_trades,
            "win_rate": report.win_rate,
            "final_capital": report.final_capital,
        }
        
        logger.info(
            f"✅ [Celery] 回测完成: {strategy_name} {symbol} | "
            f"收益率: {report.total_return:.2%} | 夏普: {report.sharpe_ratio:.2f}"
        )
        
        return result
        
    except Exception as exc:
        logger.error(f"❌ [Celery] 回测失败: {exc}", exc_info=True)
        return {"error": str(exc), "status": "failed"}
