import logging
import asyncio
import requests
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
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

        # 判断是否是EVM兼容链（包括测试网）
        elif chain.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO'] or \
             chain.chain.startswith('ETH_') or chain.chain.startswith('BSC_') or chain.chain.startswith('MATIC_') or \
             chain.chain.startswith('ARB_') or chain.chain.startswith('OP_') or chain.chain.startswith('AVAX_') or \
             chain.chain.startswith('BASE_') or chain.chain.startswith('ZKSYNC_') or chain.chain.startswith('LINEA_') or \
             chain.chain.startswith('MANTA_') or chain.chain.startswith('FTM_') or chain.chain.startswith('CRO_'):
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

                # 判断是否是EVM兼容链（包括测试网）
                elif wallet.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA'] or \
                     wallet.chain.startswith('ETH_') or wallet.chain.startswith('BSC_') or wallet.chain.startswith('MATIC_') or \
                     wallet.chain.startswith('ARB_') or wallet.chain.startswith('OP_') or wallet.chain.startswith('AVAX_') or \
                     wallet.chain.startswith('BASE_') or wallet.chain.startswith('ZKSYNC_') or wallet.chain.startswith('LINEA_') or \
                     wallet.chain.startswith('MANTA_'):
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
def process_token_metadata_batch(token_ids, chain_code):
    """
    批量处理代币元数据
    """
    try:
        logger.info(f"开始处理 {chain_code} 链上的 {len(token_ids)} 个代币元数据")

        # 获取指定的代币列表
        tokens = Token.objects.filter(id__in=token_ids)

        # 根据链类型选择相应的服务
        if chain_code == 'SOL':
            from chains.solana.services.token import SolanaTokenService
            token_service = SolanaTokenService()
        # 判断是否是EVM兼容链（包括测试网）
        elif chain_code.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO'] or \
             chain_code.startswith('ETH_') or chain_code.startswith('BSC_') or chain_code.startswith('MATIC_') or \
             chain_code.startswith('ARB_') or chain_code.startswith('OP_') or chain_code.startswith('AVAX_') or \
             chain_code.startswith('BASE_') or chain_code.startswith('ZKSYNC_') or chain_code.startswith('LINEA_') or \
             chain_code.startswith('MANTA_') or chain_code.startswith('FTM_') or chain_code.startswith('CRO_'):
            from chains.evm.services.token import EVMTokenService
            token_service = EVMTokenService(chain_code)
        else:
            logger.error(f"不支持的链类型: {chain_code}")
            return False

        # 批量处理代币元数据
        success_count = 0
        for token in tokens:
            try:
                logger.info(f"处理代币 {token.symbol} ({token.address}) 的元数据")
                metadata = token_service.get_token_metadata(token.address)

                # 更新代币元数据
                if metadata:
                    # 更新基本信息
                    if 'name' in metadata and metadata['name']:
                        token.name = metadata['name']
                    if 'symbol' in metadata and metadata['symbol']:
                        token.symbol = metadata['symbol']
                    if 'decimals' in metadata:
                        token.decimals = int(metadata['decimals'])
                    if 'logo' in metadata and metadata['logo']:
                        token.logo_url = metadata['logo']

                    # 更新标准和mint信息
                    if 'standard' in metadata:
                        token.standard = metadata['standard']
                    if 'mint' in metadata:
                        token.mint = metadata['mint']

                    # 更新描述和社交媒体链接
                    if 'description' in metadata:
                        token.description = metadata['description']

                    # 处理链接信息
                    links = metadata.get('links', {})
                    if links:
                        if 'website' in links:
                            token.website = links['website']
                        if 'twitter' in links:
                            token.twitter = links['twitter']
                        if 'telegram' in links:
                            token.telegram = links['telegram']
                        if 'discord' in links:
                            token.discord = links['discord']

                    # 直接处理顶级链接
                    if 'website' in metadata:
                        token.website = metadata['website']
                    if 'twitter' in metadata:
                        token.twitter = metadata['twitter']
                    if 'telegram' in metadata:
                        token.telegram = metadata['telegram']
                    if 'discord' in metadata:
                        token.discord = metadata['discord']

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

                    # 更新时间戳
                    token.last_updated = timezone.now()
                    token.save()

                    success_count += 1
                    logger.info(f"成功更新代币 {token.symbol} ({token.address}) 的元数据")
            except Exception as e:
                logger.error(f"处理代币 {token.symbol} ({token.address}) 元数据时出错: {str(e)}")
                continue

        logger.info(f"完成 {chain_code} 链上的代币元数据处理，成功: {success_count}/{len(token_ids)}")
        return True
    except Exception as e:
        logger.error(f"批量处理代币元数据时出错: {str(e)}")
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

        # 按链类型分组处理
        chain_tokens = {}
        for token in tokens_without_metadata:
            chain_code = token.chain.chain
            if chain_code not in chain_tokens:
                chain_tokens[chain_code] = []
            chain_tokens[chain_code].append(token.id)

        # 为每个链启动批处理任务
        for chain_code, token_ids in chain_tokens.items():
            # 每批处理30个代币
            batch_size = 30
            for i in range(0, len(token_ids), batch_size):
                batch = token_ids[i:i+batch_size]
                logger.info(f"为 {chain_code} 链安排批处理任务，包含 {len(batch)} 个代币")
                process_token_metadata_batch.delay(batch, chain_code)

        logger.info(f"已安排所有代币元数据更新任务，共 {tokens_without_metadata.count()} 个代币")
        return True
    except Exception as e:
        logger.error(f"安排代币元数据更新任务时出错: {str(e)}")
        return False

@shared_task
def monitor_tasks(task_ids, callback_url=None):
    """
    监控任务完成状态，并在所有任务完成时发送回调
    """
    from celery.result import AsyncResult

    try:
        # 检查所有任务是否完成
        all_completed = True
        results = {}
        completed_count = 0
        failed_count = 0
        pending_count = 0

        for task_id in task_ids:
            try:
                result = AsyncResult(task_id)

                if result.ready():
                    if result.successful():
                        state = 'SUCCESS'
                        completed_count += 1
                    else:
                        state = 'FAILURE'
                        failed_count += 1
                else:
                    state = result.state
                    pending_count += 1
                    all_completed = False

                results[task_id] = {
                    'state': state,
                    'info': str(result.info) if hasattr(result, 'info') and result.info else None
                }
            except Exception as e:
                logger.error(f"检查任务 {task_id} 状态时出错: {str(e)}")
                results[task_id] = {
                    'state': 'UNKNOWN',
                    'error': str(e)
                }
                pending_count += 1
                all_completed = False

        # 计算总体进度
        total_tasks = len(task_ids)
        progress = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0

        summary = {
            'total': total_tasks,
            'completed': completed_count,
            'failed': failed_count,
            'pending': pending_count,
            'progress_percentage': round(progress, 2),
            'all_completed': all_completed
        }

        # 如果所有任务完成并且提供了回调URL，发送回调
        if all_completed and callback_url:
            try:
                # 发送回调
                payload = {
                    'task_statuses': results,
                    'summary': summary
                }
                response = requests.post(callback_url, json=payload, timeout=10)
                logger.info(f"发送回调到 {callback_url}, 状态码: {response.status_code}")
            except Exception as e:
                logger.error(f"发送回调到 {callback_url} 时出错: {str(e)}")

        # 如果任务未完成，安排一个新的监控任务
        if not all_completed:
            # 每30秒检查一次
            monitor_tasks.apply_async(args=[task_ids, callback_url], countdown=30)

        return {
            'task_statuses': results,
            'summary': summary
        }
    except Exception as e:
        logger.error(f"监控任务时出错: {str(e)}")
        return {'error': str(e)}

@shared_task
def fetch_token_metadata(token_id):
    """
    获取单个代币的元数据
    """
    try:
        token = Token.objects.get(id=token_id)
        logger.info(f"开始获取代币 {token.symbol} ({token.address}) 的元数据")

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
                        logger.error(f"设置 total_supply 时出错: {e}")
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
                        logger.error(f"设置 fully_diluted_value 时出错: {e}")
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
                if 'logo' in metadata:
                    token.logo_url = metadata.get('logo', '')

                # 更新链接信息
                links = metadata.get('links', {})
                if links:
                    if 'website' in links and links['website']:
                        token.website = links['website']
                    if 'twitter' in links and links['twitter']:
                        token.twitter = links['twitter']
                    if 'telegram' in links and links['telegram']:
                        token.telegram = links['telegram']
                    if 'discord' in links and links['discord']:
                        token.discord = links['discord']

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

                # 更新时间戳
                token.last_updated = timezone.now()
                token.save()
                logger.info(f"成功更新 SOL 链代币 {token.symbol} ({token.address}) 的元数据")

        # 判断是否是EVM兼容链（包括测试网）
        elif token.chain.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO'] or \
             token.chain.chain.startswith('ETH_') or token.chain.chain.startswith('BSC_') or token.chain.chain.startswith('MATIC_') or \
             token.chain.chain.startswith('ARB_') or token.chain.chain.startswith('OP_') or token.chain.chain.startswith('AVAX_') or \
             token.chain.chain.startswith('BASE_') or token.chain.chain.startswith('ZKSYNC_') or token.chain.chain.startswith('LINEA_') or \
             token.chain.chain.startswith('MANTA_') or token.chain.chain.startswith('FTM_') or token.chain.chain.startswith('CRO_'):
            from chains.evm.services.token import EVMTokenService
            token_service = EVMTokenService(token.chain.chain)
            metadata = token_service.get_token_metadata(token.address)

            if metadata:
                # 更新基本元数据
                if 'name' in metadata and metadata['name']:
                    token.name = metadata['name']
                if 'symbol' in metadata and metadata['symbol']:
                    token.symbol = metadata['symbol']
                if 'decimals' in metadata:
                    token.decimals = int(metadata['decimals'])

                # 更新时间戳
                token.last_updated = timezone.now()
                token.save()
                logger.info(f"成功更新 {token.chain.chain} 链代币 {token.symbol} ({token.address}) 的元数据")

        return True
    except Exception as e:
        logger.error(f"Error updating token metadata: {str(e)}")
        return False
