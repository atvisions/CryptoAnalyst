from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def should_update_token_metadata(token, force_update=False, cache_ttl_hours=168):  # 168小时 = 7天
    """
    判断代币元数据是否需要更新

    Args:
        token: Token模型实例
        force_update: 是否强制更新
        cache_ttl_hours: 缓存有效期（小时）

    Returns:
        bool: 是否需要更新
    """
    # 如果强制更新，直接返回True
    if force_update:
        return True

    # 如果代币没有last_updated字段或者last_updated为空，需要更新
    if not token.last_updated:
        logger.info(f"代币 {token.symbol} ({token.address}) 没有last_updated字段，需要更新元数据")
        return True

    # 计算缓存是否过期
    cache_expiry = token.last_updated + timedelta(hours=cache_ttl_hours)
    now = timezone.now()

    # 如果缓存过期，需要更新
    if now > cache_expiry:
        logger.info(f"代币 {token.symbol} ({token.address}) 元数据缓存已过期，上次更新时间: {token.last_updated}，需要更新")
        return True

    # 如果代币的关键字段为空，需要更新
    if not token.logo_url or not token.name or not token.symbol:
        logger.info(f"代币 {token.symbol} ({token.address}) 关键字段为空，需要更新元数据")
        return True

    # 如果代币价格为0，但不是所有代币都是0价格，可能需要更新
    if token.current_price_usd == 0 and token.symbol not in ['Unknown', 'TEST']:
        # 这里可以添加一些逻辑，判断是否是应该有价格的代币
        # 例如，对于主流代币，如果价格为0，可能需要更新
        if token.symbol in ['ETH', 'BTC', 'SOL', 'KDA', 'USDT', 'USDC', 'DAI']:
            logger.info(f"主流代币 {token.symbol} ({token.address}) 价格为0，需要更新元数据")
            return True

    logger.info(f"代币 {token.symbol} ({token.address}) 元数据缓存有效，不需要更新")
    return False

def should_update_token_price(token, force_update=False, cache_ttl_minutes=15):
    """
    判断代币价格是否需要更新

    Args:
        token: Token模型实例
        force_update: 是否强制更新
        cache_ttl_minutes: 缓存有效期（分钟）

    Returns:
        bool: 是否需要更新
    """
    # 如果强制更新，直接返回True
    if force_update:
        return True

    # 如果代币没有last_updated字段或者last_updated为空，需要更新
    if not token.last_updated:
        return True

    # 计算缓存是否过期（价格缓存时间比元数据短）
    cache_expiry = token.last_updated + timedelta(minutes=cache_ttl_minutes)
    now = timezone.now()

    # 如果缓存过期，需要更新
    if now > cache_expiry:
        return True

    # 如果代币价格为0，但不是所有代币都是0价格，可能需要更新
    if token.current_price_usd == 0 and token.symbol not in ['Unknown', 'TEST']:
        # 这里可以添加一些逻辑，判断是否是应该有价格的代币
        if token.symbol in ['ETH', 'BTC', 'SOL', 'KDA', 'USDT', 'USDC', 'DAI']:
            return True

    return False

def batch_tokens_by_update_need(tokens, force_update=False, metadata_ttl_hours=168, price_ttl_minutes=15):  # 168小时 = 7天
    """
    将代币按照更新需求分批

    Args:
        tokens: Token查询集
        force_update: 是否强制更新
        metadata_ttl_hours: 元数据缓存有效期（小时）
        price_ttl_minutes: 价格缓存有效期（分钟）

    Returns:
        tuple: (需要更新元数据的代币列表, 只需要更新价格的代币列表, 不需要更新的代币列表)
    """
    need_metadata_update = []
    need_price_update = []
    no_update_needed = []

    for token in tokens:
        if should_update_token_metadata(token, force_update, metadata_ttl_hours):
            need_metadata_update.append(token)
        elif should_update_token_price(token, force_update, price_ttl_minutes):
            need_price_update.append(token)
        else:
            no_update_needed.append(token)

    return need_metadata_update, need_price_update, no_update_needed
