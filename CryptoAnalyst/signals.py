from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Token, TechnicalAnalysis, MarketData, AnalysisReport
from .utils import logger

@receiver(post_save, sender=TechnicalAnalysis)
def log_technical_analysis_update(sender, instance, created, **kwargs):
    """记录技术分析数据更新"""
    try:
        logger.info(f"更新代币 {instance.token.symbol} 的技术分析数据")
    except Exception as e:
        logger.error(f"更新代币技术分析数据失败: {str(e)}")

@receiver(post_save, sender=MarketData)
def log_market_data_update(sender, instance, created, **kwargs):
    """记录市场数据更新"""
    try:
        logger.info(f"更新代币 {instance.token.symbol} 的市场数据")
    except Exception as e:
        logger.error(f"更新代币市场数据失败: {str(e)}") 