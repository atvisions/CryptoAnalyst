from django.apps import AppConfig

class CryptoAnalystConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'CryptoAnalyst'
    verbose_name = '加密货币分析系统'

    def ready(self):
        """应用启动时执行"""
        import CryptoAnalyst.signals  # 导入信号处理器 