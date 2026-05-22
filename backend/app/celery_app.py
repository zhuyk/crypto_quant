"""
Celery 应用配置

docker-compose 中的 celery worker/beat 通过此模块启动:
  celery -A app.celery_app worker -l info
  celery -A app.celery_app beat -l info
"""
import os
import sys
from pathlib import Path

# 确保 backend 目录在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# 创建 Celery 实例
celery_app = Celery(
    "cryptoquant",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery 配置
celery_app.conf.update(
    # 序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # 时区
    timezone="UTC",
    enable_utc=True,
    
    # 任务执行
    task_soft_time_limit=300,   # 软超时 5 分钟
    task_time_limit=600,        # 硬超时 10 分钟
    task_acks_late=True,        # 任务完成后才确认
    worker_prefetch_multiplier=1,  # 一次只取一个任务
    
    # 结果
    result_expires=3600,  # 结果保留 1 小时
    
    # 重试
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Worker
    worker_max_tasks_per_child=200,  # 防止内存泄漏
    worker_hijack_root_logger=False,
)

# 自动发现任务
celery_app.autodiscover_tasks(["app.tasks"])

# Beat 定时任务配置（与 APScheduler 的定时任务对应，用于分布式部署）
celery_app.conf.beat_schedule = {
    # 每 5 分钟采集高频行情数据
    "collect-market-data-5min": {
        "task": "app.tasks.celery_tasks.collect_market_data_task",
        "schedule": 300.0,  # 5 minutes
    },
    # 每小时采集低频K线
    "collect-hourly-data": {
        "task": "app.tasks.celery_tasks.collect_hourly_data_task",
        "schedule": 3600.0,  # 1 hour
    },
    # 每天 23:59 计算每日盈亏
    "calculate-daily-pnl": {
        "task": "app.tasks.celery_tasks.calculate_daily_pnl_task",
        "schedule": crontab(hour=23, minute=59),
    },
    # 每天 8:00 发送日报
    "send-daily-report": {
        "task": "app.tasks.celery_tasks.send_daily_report_task",
        "schedule": crontab(hour=8, minute=0),
    },
    # 每周日 3:00 清理旧数据
    "cleanup-old-data": {
        "task": "app.tasks.celery_tasks.cleanup_old_data_task",
        "schedule": crontab(hour=3, minute=0, day_of_week="sunday"),
    },
    # 每 30 分钟健康检查
    "system-health-check": {
        "task": "app.tasks.celery_tasks.check_system_health_task",
        "schedule": 1800.0,  # 30 minutes
    },
}
