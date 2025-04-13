# 导入celery配置
from .celery import app as celery_app

__all__ = ('celery_app',)