import os
from celery import Celery
from django.conf import settings

# 设置默认的Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('wallet')

# 使用字符串表示，这样worker不用序列化配置对象
app.config_from_object('django.conf:settings', namespace='CELERY')

# 从所有已注册的Django应用中加载任务模块
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# 配置定时任务
app.conf.beat_schedule = {
    'update-token-prices-hourly': {
        'task': 'wallets.tasks.update_token_prices',
        'schedule': 3600.0,  # 每小时执行一次
        'args': (),
    },
    'update-wallet-balances-daily': {
        'task': 'wallets.tasks.update_wallet_balances',
        'schedule': 86400.0,  # 每天执行一次
        'args': (),
    },
    'update-token-metadata-weekly': {
        'task': 'wallets.tasks.update_token_metadata',
        'schedule': 604800.0,  # 每周执行一次
        'args': (),
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
