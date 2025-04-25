import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# 设置默认的Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('CryptoAnalyst')

# 使用字符串表示，这样worker不用序列化配置对象
app.config_from_object('django.conf:settings', namespace='CELERY')

# 从所有已注册的Django应用中加载任务模块
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# 配置定时任务
app.conf.beat_schedule = {
    'update-market-data': {
        'task': 'CryptoAnalyst.tasks.update_market_data',
        'schedule': crontab(minute='*/5'),  # 每5分钟执行一次
        'args': (),
    },
    'update-technical-analysis': {
        'task': 'CryptoAnalyst.tasks.update_technical_analysis',
        'schedule': crontab(minute='*/15'),  # 每15分钟执行一次
        'args': (),
    },
    'update-coze-analysis': {
        'task': 'CryptoAnalyst.tasks.update_coze_analysis',
        'schedule': crontab(minute='*/30'),  # 每30分钟执行一次
        'args': (),
    },
}

# 添加一些重要的 Celery 配置
app.conf.update(
    # 任务序列化方式
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # 时区设置
    timezone='UTC',
    enable_utc=True,
    
    # 任务过期时间
    task_time_limit=300,  # 5分钟
    
    # 任务重试设置
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # 结果后端设置
    result_backend='django-db',
    result_expires=3600,  # 1小时
    
    # 并发设置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # 忽略未注册的任务
    task_ignore_result=True,
    task_store_errors_even_if_ignored=True,
    task_ignore_unknown=True,  # 忽略未知任务
)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
