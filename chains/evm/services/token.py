from typing import Dict, Any, List
from web3 import Web3
from decimal import Decimal
from common.config import Config
import logging
import time

logger = logging.getLogger(__name__)

class EVMTokenService:
    """EVM 代币服务"""

    def __init__(self, chain: str):
        """初始化 EVM RPC 客户端"""
        config = Config.get_evm_config(chain)
        self.web3 = Web3(Web3.HTTPProvider(config["rpc_url"]))
        self.chain = chain

    def get_token_list(self, wallet_address: str) -> List[Dict[str, Any]]:
        """获取钱包持有的代币列表"""
        try:
            # 这里需要集成 Moralis API 来获取代币列表
            # 这里只是一个示例实现
            logger.info(f"获取钱包 {wallet_address} 的代币列表（未实现）")
            return []
        except Exception as e:
            logger.error(f"获取钱包 {wallet_address} 的代币列表失败: {str(e)}")
            raise Exception(f"获取代币列表失败: {str(e)}")

    def get_token_metadata(self, token_address: str) -> Dict[str, Any]:
        """获取代币元数据"""
        # 检查缓存
        from django.core.cache import cache
        cache_key = f"{self.chain}:token:{token_address.lower()}:metadata"
        cached_metadata = cache.get(cache_key)
        if cached_metadata:
            logger.info(f"从缓存获取代币 {token_address} 的元数据")
            return cached_metadata

        # 检查数据库
        try:
            from wallets.models import Token, Chain
            chain = Chain.objects.get(chain=self.chain)
            token = Token.objects.filter(chain=chain, address=token_address).first()
            if token:
                # 如果数据库中有记录，使用数据库中的元数据
                metadata = {
                    'name': token.name,
                    'symbol': token.symbol,
                    'decimals': token.decimals,
                    'logo': token.logo_url
                }
                # 缓存元数据，有效期24小时
                cache.set(cache_key, metadata, 60 * 60 * 24)  # 24小时
                logger.info(f"从数据库获取代币 {token_address} 的元数据")
                return metadata
        except Exception as e:
            logger.warning(f"从数据库获取代币元数据失败: {e}")

        # ERC20 代币合约 ABI
        erc20_abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]

        # 添加重试机制
        max_retries = 3
        retry_delay = 2  # 初始重试延迟（秒）

        for retry in range(max_retries):
            try:
                logger.info(f"尝试获取代币元数据 {token_address} (尝试 {retry+1}/{max_retries})")
                contract = self.web3.eth.contract(address=token_address, abi=erc20_abi)

                # 分别获取每个属性，避免一个失败导致整个请求失败
                try:
                    name = contract.functions.name().call()
                except Exception as e:
                    logger.warning(f"获取代币名称失败: {str(e)}")
                    name = "Unknown"

                try:
                    symbol = contract.functions.symbol().call()
                except Exception as e:
                    logger.warning(f"获取代币符号失败: {str(e)}")
                    symbol = "Unknown"

                try:
                    decimals = contract.functions.decimals().call()
                except Exception as e:
                    logger.warning(f"获取代币小数位失败: {str(e)}")
                    decimals = 18  # 默认使用18位小数

                # 构造元数据对象
                metadata = {
                    'name': name,
                    'symbol': symbol,
                    'decimals': decimals
                }

                # 缓存元数据，有效期24小时
                cache.set(cache_key, metadata, 60 * 60 * 24)  # 24小时

                logger.info(f"成功从链上获取代币元数据: {name} ({symbol})，并缓存")
                return metadata
            except Exception as e:
                logger.error(f"获取代币元数据失败 (尝试 {retry+1}/{max_retries}): {str(e)}")
                if retry < max_retries - 1:
                    wait_time = retry_delay * (2 ** retry)  # 指数退避
                    logger.info(f"将在 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

        # 所有重试都失败后返回默认值
        logger.error(f"在 {max_retries} 次尝试后无法获取代币元数据，返回默认值")

        # 构造默认元数据
        default_metadata = {
            'name': 'Unknown',
            'symbol': 'Unknown',
            'decimals': 18
        }

        # 缓存默认元数据，但只缓存30分钟，因为这是失败的结果
        cache.set(cache_key, default_metadata, 60 * 30)  # 30分钟

        return default_metadata

    def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取特定代币余额"""
        # ERC20 代币合约 ABI
        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]

        # 添加重试机制
        max_retries = 3
        retry_delay = 2  # 初始重试延迟（秒）

        for retry in range(max_retries):
            try:
                logger.info(f"尝试获取代币余额 {token_address} 为钱包 {wallet_address} (尝试 {retry+1}/{max_retries})")
                contract = self.web3.eth.contract(address=token_address, abi=erc20_abi)

                # 分别获取余额和小数位，避免一个失败导致整个请求失败
                try:
                    balance = contract.functions.balanceOf(wallet_address).call()
                except Exception as e:
                    logger.warning(f"获取代币余额失败: {str(e)}")
                    balance = 0

                try:
                    decimals = contract.functions.decimals().call()
                except Exception as e:
                    logger.warning(f"获取代币小数位失败: {str(e)}")
                    decimals = 18  # 默认使用18位小数

                logger.info(f"成功获取代币余额: {balance} (小数位: {decimals})")
                return {
                    'balance': str(Decimal(balance) / Decimal(10**decimals)),
                    'decimals': decimals,
                    'chain': self.chain,
                    'token_address': token_address,
                    'wallet_address': wallet_address
                }
            except Exception as e:
                logger.error(f"获取代币余额失败 (尝试 {retry+1}/{max_retries}): {str(e)}")
                if retry < max_retries - 1:
                    wait_time = retry_delay * (2 ** retry)  # 指数退避
                    logger.info(f"将在 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

        # 所有重试都失败后返回默认值
        logger.error(f"在 {max_retries} 次尝试后无法获取代币余额，返回默认值")
        return {
            'balance': '0',
            'decimals': 18,
            'chain': self.chain,
            'token_address': token_address,
            'wallet_address': wallet_address
        }