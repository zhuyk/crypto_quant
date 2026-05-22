"""
Celery 入口模块

docker-compose 中通过 `celery -A app.celery` 引用此模块。
实际配置在 app.celery_app 中。
"""
from app.celery_app import celery_app  # noqa: F401

# 让 `celery -A app.celery` 能发现 app 实例
app = celery_app
