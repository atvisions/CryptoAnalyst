import logging
import asyncio
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Token, Wallet, WalletToken, Chain

logger = logging.getLogger(__name__)

@shared_task
def update_token_prices():
    """
    更新所有代币的价格信息
    每小时执行一次
    """
    try:
        # 调用异步方法
        asyncio.run(_update_token_prices_async())
        logger.info(f"Successfully updated prices for all tokens at {timezone.now()}")
        return True
    except Exception as e:
        logger.error(f"Error updating token prices: {str(e)}")
        return False

async def _update_token_prices_async():
    """异步更新代币价格"""
    # 获取所有活跃的链
    active_chains = Chain.objects.filter(is_active=True)

    # 创建任务列表
    tasks = []

    for chain in active_chains:
        # 根据链类型选择相应的服务
        if chain.chain == 'SOL':
            from chains.solana.services.balance import SolanaBalanceService
            balance_service = SolanaBalanceService()

            # 获取该链上的所有代币
            tokens = Token.objects.filter(chain=chain)

            # 批量获取代币价格
            token_addresses = [token.address for token in tokens]
            if token_addresses:
                tasks.append({
                    'service': balance_service,
                    'tokens': tokens,
                    'addresses': token_addresses,
                    'chain': chain.chain
                })

        elif chain.chain in ['ETH', 'BSC', 'POLYGON', 'ARBITRUM', 'OPTIMISM', 'AVALANCHE']:
            from chains.evm.services.balance import EVMBalanceService
            balance_service = EVMBalanceService(chain.chain)

            # 获取该链上的所有代币
            tokens = Token.objects.filter(chain=chain)

            # 批量获取代币价格
            token_addresses = [token.address for token in tokens]
            if token_addresses:
                tasks.append({
                    'service': balance_service,
                    'tokens': tokens,
                    'addresses': token_addresses,
                    'chain': chain.chain
                })

    # 并行执行所有任务
    for task in tasks:
        try:
            prices = await task['service']._get_token_prices(task['addresses'])

            # 更新代币价格
            for token in task['tokens']:
                price_data = prices.get(token.address, {})
                if price_data:
                    token.current_price_usd = price_data.get("current_price", token.current_price_usd)
                    token.price_change_24h = price_data.get("price_change_24h", token.price_change_24h)
                    token.save()
                    logger.info(f"Updated price for {token.symbol} ({task['chain']}): {token.current_price_usd} USD")
        except Exception as e:
            logger.error(f"Error updating prices for {task['chain']} chain: {str(e)}")
            continue

@shared_task
def update_wallet_balances():
    """
    更新所有钱包的代币余额
    每天执行一次
    """
    try:
        # 获取最近7天内活跃的钱包
        active_time = timezone.now() - timedelta(days=7)
        active_wallets = Wallet.objects.filter(updated_at__gte=active_time, is_active=True)

        for wallet in active_wallets:
            try:
                # 根据钱包链类型调用相应的服务更新余额
                if wallet.chain == 'SOL':
                    from chains.solana.services.balance import SolanaBalanceService
                    balance_service = SolanaBalanceService()
                    balance_service.get_all_token_balances(wallet.address, wallet_id=wallet.id)
                    logger.info(f"Updated balances for wallet {wallet.address} (SOL)")

                elif wallet.chain in ['ETH', 'BSC', 'POLYGON', 'ARBITRUM', 'OPTIMISM', 'AVALANCHE']:
                    from chains.evm.services.balance import EVMBalanceService
                    balance_service = EVMBalanceService(wallet.chain)
                    balance_service.get_all_token_balances(wallet.address, wallet_id=wallet.id)
                    logger.info(f"Updated balances for wallet {wallet.address} ({wallet.chain})")

            except Exception as e:
                logger.error(f"Error updating balances for wallet {wallet.address}: {str(e)}")
                continue

        logger.info(f"Successfully updated balances for all active wallets at {timezone.now()}")
        return True
    except Exception as e:
        logger.error(f"Error updating wallet balances: {str(e)}")
        return False

@shared_task
def update_token_metadata():
    """
    更新所有代币的元数据
    每周执行一次
    """
    try:
        # 获取所有活跃的代币，强制更新元数据
        tokens_without_metadata = Token.objects.filter(is_active=True)

        for token in tokens_without_metadata:
            try:
                # 根据代币所属链选择相应的服务
                if token.chain.chain == 'SOL':
                    from chains.solana.services.token import SolanaTokenService
                    token_service = SolanaTokenService()
                    metadata = token_service.get_token_metadata(token.address)

                    if metadata:
                        # 更新基本元数据
                        token.description = metadata.get('description', '')
                        token.website = metadata.get('website', '')
                        token.twitter = metadata.get('twitter', '')
                        token.telegram = metadata.get('telegram', '')
                        token.discord = metadata.get('discord', '')

                        # 更新供应信息
                        if 'totalSupply' in metadata:
                            try:
                                token.total_supply = metadata.get('totalSupply', 0)
                            except Exception as e:
                                logger.error(f"Error setting total_supply: {e}")
                                # 尝试将字符串转换为数字
                                try:
                                    token.total_supply = float(metadata.get('totalSupply', 0))
                                except:
                                    token.total_supply = 0

                        if 'totalSupplyFormatted' in metadata:
                            token.total_supply_formatted = str(metadata.get('totalSupplyFormatted', ''))

                        if 'fullyDilutedValue' in metadata:
                            try:
                                token.fully_diluted_value = metadata.get('fullyDilutedValue', 0)
                            except Exception as e:
                                logger.error(f"Error setting fully_diluted_value: {e}")
                                # 尝试将字符串转换为数字
                                try:
                                    token.fully_diluted_value = float(metadata.get('fullyDilutedValue', 0))
                                except:
                                    token.fully_diluted_value = 0

                        # 更新标准信息
                        if 'standard' in metadata:
                            token.standard = metadata.get('standard', '')
                        if 'mint' in metadata:
                            token.mint = metadata.get('mint', '')

                        # 更新 Metaplex 元数据
                        metaplex = metadata.get('metaplex', {})
                        if metaplex:
                            if 'metadataUri' in metaplex:
                                token.metadata_uri = metaplex.get('metadataUri', '')
                            if 'masterEdition' in metaplex:
                                token.is_master_edition = metaplex.get('masterEdition', False)
                            if 'isMutable' in metaplex:
                                token.is_mutable = metaplex.get('isMutable', True)
                            if 'sellerFeeBasisPoints' in metaplex:
                                token.seller_fee_basis_points = metaplex.get('sellerFeeBasisPoints', 0)
                            if 'updateAuthority' in metaplex:
                                token.update_authority = metaplex.get('updateAuthority', '')
                            if 'primarySaleHappened' in metaplex:
                                # primarySaleHappened 可能是数字或布尔值
                                primary_sale = metaplex.get('primarySaleHappened', 0)
                                if isinstance(primary_sale, bool):
                                    token.primary_sale_happened = primary_sale
                                else:
                                    token.primary_sale_happened = bool(primary_sale)

                        token.save()
                        logger.info(f"Updated metadata for token {token.symbol} ({token.address})")

                elif token.chain.chain in ['ETH', 'BSC', 'POLYGON', 'ARBITRUM', 'OPTIMISM', 'AVALANCHE']:
                    from chains.evm.services.token import EVMTokenService
                    token_service = EVMTokenService(token.chain.chain)
                    metadata = token_service.get_token_metadata(token.address)

                    if metadata:
                        # 更新基本元数据
                        token.description = metadata.get('description', '')
                        token.website = metadata.get('website', '')
                        token.twitter = metadata.get('twitter', '')
                        token.telegram = metadata.get('telegram', '')
                        token.discord = metadata.get('discord', '')
                        # 打印更新前的元数据状态
                        logger.info(f"Before update - Token {token.symbol} ({token.address}) metadata:")
                        logger.info(f"  description: {token.description[:50] if token.description else 'None'}")
                        logger.info(f"  standard: {token.standard}")
                        logger.info(f"  mint: {token.mint}")
                        logger.info(f"  totalSupply: {token.total_supply}")
                        logger.info(f"  totalSupplyFormatted: {token.total_supply_formatted}")
                        logger.info(f"  fullyDilutedValue: {token.fully_diluted_value}")
                        logger.info(f"  metadata_uri: {token.metadata_uri}")
                        logger.info(f"  is_master_edition: {token.is_master_edition}")
                        logger.info(f"  is_mutable: {token.is_mutable}")
                        logger.info(f"  seller_fee_basis_points: {token.seller_fee_basis_points}")
                        logger.info(f"  update_authority: {token.update_authority}")
                        logger.info(f"  primary_sale_happened: {token.primary_sale_happened}")

                        token.save()

                        # 打印更新后的元数据状态
                        logger.info(f"After update - Token {token.symbol} ({token.address}) metadata:")
                        logger.info(f"  description: {token.description[:50] if token.description else 'None'}")
                        logger.info(f"  standard: {token.standard}")
                        logger.info(f"  mint: {token.mint}")
                        logger.info(f"  totalSupply: {token.total_supply}")
                        logger.info(f"  totalSupplyFormatted: {token.total_supply_formatted}")
                        logger.info(f"  fullyDilutedValue: {token.fully_diluted_value}")
                        logger.info(f"  metadata_uri: {token.metadata_uri}")
                        logger.info(f"  is_master_edition: {token.is_master_edition}")
                        logger.info(f"  is_mutable: {token.is_mutable}")
                        logger.info(f"  seller_fee_basis_points: {token.seller_fee_basis_points}")
                        logger.info(f"  update_authority: {token.update_authority}")
                        logger.info(f"  primary_sale_happened: {token.primary_sale_happened}")

                        logger.info(f"Updated metadata for token {token.symbol} ({token.address})")

            except Exception as e:
                logger.error(f"Error updating metadata for token {token.symbol} ({token.address}): {str(e)}")
                continue

        logger.info(f"Successfully updated metadata for all tokens at {timezone.now()}")
        return True
    except Exception as e:
        logger.error(f"Error updating token metadata: {str(e)}")
        return False
