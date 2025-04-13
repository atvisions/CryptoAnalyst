from celery import shared_task
from chains.solana.services.balance import SolanaBalanceService
import asyncio
from django.core.cache import cache
import json
import logging
from wallets.models import TokenVisibility, Wallet

logger = logging.getLogger(__name__)

@shared_task
def refresh_token_prices():
    """定时刷新常用代币的价格数据"""
    # 获取活跃钱包列表
    active_wallets = Wallet.objects.filter(is_active=True)

    # 获取常用代币地址
    popular_tokens = set()
    for wallet in active_wallets:
        # 检查缓存
        cache_key = f"token_visibility:{wallet.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            # 使用缓存数据
            token_addresses = json.loads(cached_data)
            popular_tokens.update(token_addresses)

    # 添加数据库中的代币
    db_tokens = TokenVisibility.objects.values_list('token_address', flat=True).distinct()
    popular_tokens.update(db_tokens)

    # 添加SOL原生代币
    if "native" in popular_tokens:
        popular_tokens.remove("native")
    popular_tokens.add("So11111111111111111111111111111111111111112")

    # 限制数量，避免API限制
    token_list = list(popular_tokens)[:100]

    # 刷新价格
    service = SolanaBalanceService()
    price_data = asyncio.run(service._fetch_token_prices_from_api(token_list))

    # 更新缓存
    for token_address, price_info in price_data.items():
        cache_key = f"token_price:{token_address}"
        cache.set(cache_key, json.dumps(price_info), 60 * 15)  # 15分钟

    logger.info(f"刷新了 {len(price_data)} 个代币的价格数据")
    return f"刷新了 {len(price_data)} 个代币的价格数据"

@shared_task
def refresh_wallet_balances():
    """定时刷新钱包余额缓存"""
    # 获取活跃钱包列表
    active_wallets = Wallet.objects.filter(is_active=True)

    # 清理钱包余额缓存
    for wallet in active_wallets:
        # 清理原生代币余额缓存
        native_balance_key = f"native_balance:{wallet.address}"
        cache.delete(native_balance_key)

        # 清理代币列表缓存
        token_balances_key = f"token_balances:{wallet.address}"
        cache.delete(token_balances_key)

    logger.info(f"刷新了 {len(active_wallets)} 个钱包的余额缓存")
    return f"刷新了 {len(active_wallets)} 个钱包的余额缓存"
