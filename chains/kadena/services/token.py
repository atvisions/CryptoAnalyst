from typing import Dict, Any, List
from decimal import Decimal
import logging
from common.config import Config
from kadena_sdk.kadena_sdk import KadenaSdk

logger = logging.getLogger(__name__)

class KadenaTokenService:
    """Kadena 代币服务"""

    def __init__(self):
        """初始化 Kadena 客户端"""
        self.config = Config()

    def _get_sdk(self, chain: str, kadena_chain_id: str = None) -> KadenaSdk:
        """获取 Kadena SDK"""
        config = self.config.get_kadena_config(chain)

        # 如果提供了特定的kadena_chain_id，使用它；否则使用配置中的默认值
        chain_id = kadena_chain_id if kadena_chain_id is not None else config['kadena_chain_id']

        # 根据链类型和kadena_chain_id构建API版本
        if chain == "KDA":
            api_version = f"chainweb/0.0/mainnet01/chain/{chain_id}"
        else:  # KDA_TESTNET
            api_version = f"chainweb/0.0/testnet04/chain/{chain_id}"

        logger.debug(f"创建Kadena SDK实例，链类型: {chain}, 平行链ID: {chain_id}, API版本: {api_version}")

        return KadenaSdk(
            config['rpc_url'],
            chain_id,
            config['network_id'],
            api_version
        )

    def get_token_list(self, wallet_address: str, chain: str = "KDA") -> List[Dict[str, Any]]:
        """获取钱包持有的代币列表"""
        try:
            logger.info(f"获取钱包 {wallet_address} 的代币列表")
            sdk = self._get_sdk(chain)
            tokens = sdk.get_token_list(wallet_address)
            logger.info(f"获取到 {len(tokens)} 个代币")
            return tokens
        except Exception as e:
            logger.error(f"获取代币列表失败: {str(e)}")
            # 如果出错，返回空列表
            return []

    def get_token_metadata(self, token_address: str, chain: str = "KDA") -> Dict[str, Any]:
        """获取代币元数据"""
        try:
            # 使用缓存键来检查是否有缓存
            cache_key = f"{chain}:{token_address}:metadata"
            cache_timeout = 3600  # 缓存 1 小时，元数据变化不频繁

            # 尝试从缓存中获取元数据
            from django.core.cache import cache
            cached_metadata = cache.get(cache_key)
            if cached_metadata is not None:
                logger.debug(f"从缓存中获取代币 {token_address} 的元数据")
                return cached_metadata

            # 如果没有缓存，查询元数据
            logger.info(f"获取代币 {token_address} 的元数据")
            sdk = self._get_sdk(chain)
            metadata = sdk.get_token_info(token_address)
            logger.info(f"获取到代币元数据: {metadata}")

            # 将结果存入缓存
            cache.set(cache_key, metadata, cache_timeout)

            return metadata
        except Exception as e:
            logger.error(f"获取代币元数据失败: {str(e)}")
            # 如果出错，返回默认值
            default_metadata = {
                'name': 'Unknown',
                'symbol': 'Unknown',
                'decimals': 12,  # Kadena 默认精度
                'logo': '',
                'website': '',
                'social': {}
            }

            # 将默认值存入缓存，避免重复查询失败
            from django.core.cache import cache
            cache.set(cache_key, default_metadata, 300)  # 缓存 5 分钟，失败的查询缓存时间短一些

            return default_metadata

    def get_token_balance(self, token_address: str, wallet_address: str, chain: str = "KDA") -> Dict[str, Any]:
        """获取特定代币余额"""
        try:
            # 使用缓存键来检查是否有缓存
            cache_key = f"{chain}:{wallet_address}:{token_address}:balance"
            cache_timeout = 60  # 缓存 60 秒

            # 尝试从缓存中获取余额
            from django.core.cache import cache
            cached_balance = cache.get(cache_key)
            if cached_balance is not None:
                logger.debug(f"从缓存中获取钱包 {wallet_address} 的代币 {token_address} 余额: {cached_balance}")
                return cached_balance

            logger.info(f"获取钱包 {wallet_address} 的代币 {token_address} 余额")

            # 获取链配置
            kadena_config = self.config.get_kadena_config(chain)

            # 检查是否是多链架构
            if kadena_config.get('multi_chain', False) and (token_address == "" or token_address == "coin"):
                # 如果是原生 KDA 代币并且是多链架构，查询所有链上的余额
                from chains.kadena.services.balance import KadenaBalanceService
                balance_service = KadenaBalanceService()
                balance_data = balance_service.get_balance(chain, wallet_address)

                logger.info(f"使用 KadenaBalanceService 查询所有平行链上的原生 KDA 余额: {balance_data['balance']}")

                result = {
                    'balance': balance_data["balance"],
                    'chain': chain,
                    'token_address': token_address,
                    'wallet_address': wallet_address
                }

                # 将结果存入缓存
                cache.set(cache_key, result, cache_timeout)

                return result
            else:
                # 如果不是原生 KDA 代币或者不是多链架构
                total_balance = Decimal('0')

                # 如果是多链架构，查询所有链
                if kadena_config.get('multi_chain', False):
                    logger.info(f"开始查询所有平行链上的代币 {token_address} 余额")

                    # 对每个平行链进行查询
                    for kadena_chain_id in kadena_config['kadena_chain_ids']:
                        try:
                            # 使用特定的平行链ID创建SDK
                            sdk = self._get_sdk(chain, str(kadena_chain_id))
                            chain_balance = sdk.get_token_balance(token_address, wallet_address)

                            if chain_balance > 0:
                                logger.info(f"Kadena 平行链 {kadena_chain_id} 上的代币 {token_address} 余额: {chain_balance}")
                                total_balance += chain_balance
                        except Exception as e:
                            logger.error(f"获取 Kadena 平行链 {kadena_chain_id} 上的代币 {token_address} 余额失败: {str(e)}")

                    logger.info(f"所有平行链上的代币 {token_address} 总余额: {total_balance}")
                else:
                    # 如果不是多链架构，只查询指定链上的余额
                    sdk = self._get_sdk(chain)
                    total_balance = sdk.get_token_balance(token_address, wallet_address)
                    logger.info(f"获取到代币余额: {total_balance}")

                result = {
                    'balance': str(total_balance),
                    'chain': chain,
                    'token_address': token_address,
                    'wallet_address': wallet_address
                }

                # 将结果存入缓存
                cache.set(cache_key, result, cache_timeout)

                return result
        except Exception as e:
            logger.error(f"获取代币余额失败: {str(e)}")
            # 如果出错，返回默认值
            default_result = {
                'balance': '0',
                'chain': chain,
                'token_address': token_address,
                'wallet_address': wallet_address
            }

            # 将默认值存入缓存，避免重复查询失败
            from django.core.cache import cache
            cache.set(cache_key, default_result, 30)  # 缓存 30 秒，失败的查询缓存时间短一些

            return default_result