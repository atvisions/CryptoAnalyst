import os
from celery import Celery

# 设置默认的Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('wallet')

# 使用 Redis 作为消息代理和结果后端
app.conf.broker_url = 'redis://localhost:6379/0'
app.conf.result_backend = 'redis://localhost:6379/0'

# 使用字符串，这样worker不用序列化配置对象
app.config_from_object('django.conf:settings', namespace='CELERY')

# 从所有已注册的Django应用中加载任务模块
app.autodiscover_tasks()

# 配置定时任务
app.conf.beat_schedule = {
    # 每15分钟刷新代币价格
    'refresh-token-prices-every-15-minutes': {
        'task': 'wallets.tasks.refresh_token_prices',
        'schedule': 60.0 * 15,  # 15分钟
    },
    # 每5分钟刷新钱包余额缓存
    'refresh-wallet-balances-every-5-minutes': {
        'task': 'wallets.tasks.refresh_wallet_balances',
        'schedule': 60.0 * 5,  # 5分钟
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
