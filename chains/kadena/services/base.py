from typing import Dict, Any, List
import logging
from common.config import Config
from kadena_sdk.kadena_sdk import KadenaSdk
from kadena_sdk.key_pair import KeyPair
import requests
import json

logger = logging.getLogger(__name__)

class KadenaBaseService:
    """Kadena 链基础服务"""

    def __init__(self):
        self.config = Config()

    def _get_sdk(self, chain: str) -> KadenaSdk:
        """获取 Kadena SDK"""
        config = self.config.get_kadena_config(chain)
        return KadenaSdk(
            config['rpc_url'],
            config['kadena_chain_id'],  # 使用 kadena_chain_id 替代 chain_id
            config['network_id'],
            config['api_version']
        )

    def get_balance(self, chain: str, address: str) -> Dict[str, Any]:
        """获取余额"""
        try:
            logger.info(f"获取 {chain} 链上地址 {address} 的余额")
            sdk = self._get_sdk(chain)
            balance = sdk.get_balance(address)
            logger.info(f"获取到余额: {balance}")
            return {
                'balance': str(balance),
                'chain': chain,
                'address': address
            }
        except Exception as e:
            logger.error(f"获取余额失败: {str(e)}")
            raise Exception(f"获取余额失败: {str(e)}")

    def get_transaction(self, chain: str, tx_hash: str) -> Dict[str, Any]:
        """获取交易详情"""
        try:
            logger.info(f"获取 {chain} 链上交易 {tx_hash} 的详情")
            sdk = self._get_sdk(chain)
            tx = sdk.get_transaction(tx_hash)
            logger.info(f"获取到交易详情: {tx}")
            return tx
        except Exception as e:
            logger.error(f"获取交易详情失败: {str(e)}")
            raise Exception(f"获取交易详情失败: {str(e)}")

    def get_token_balance(self, chain: str, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取代币余额"""
        try:
            logger.info(f"获取 {chain} 链上地址 {wallet_address} 的代币 {token_address} 余额")
            sdk = self._get_sdk(chain)
            balance = sdk.get_token_balance(token_address, wallet_address)
            logger.info(f"获取到代币余额: {balance}")
            return {
                'balance': str(balance),
                'chain': chain,
                'token_address': token_address,
                'wallet_address': wallet_address
            }
        except Exception as e:
            logger.error(f"获取代币余额失败: {str(e)}")
            # 如果出错，返回默认值
            return {
                'balance': '0',
                'chain': chain,
                'token_address': token_address,
                'wallet_address': wallet_address
            }

    def get_token_info(self, chain: str, token_address: str) -> Dict[str, Any]:
        """获取代币信息"""
        try:
            logger.info(f"获取 {chain} 链上代币 {token_address} 的信息")
            sdk = self._get_sdk(chain)
            info = sdk.get_token_info(token_address)
            logger.info(f"获取到代币信息: {info}")
            return {
                'name': info.get('name', 'Unknown'),
                'symbol': info.get('symbol', 'Unknown'),
                'decimals': info.get('decimals', 12),
                'total_supply': info.get('total_supply', '0'),
                'logo': info.get('logo', ''),
                'website': info.get('website', ''),
                'social': info.get('social', {}),
                'chain': chain,
                'address': token_address
            }
        except Exception as e:
            logger.error(f"获取代币信息失败: {str(e)}")
            # 如果出错，返回默认值
            return {
                'name': 'Unknown',
                'symbol': 'Unknown',
                'decimals': 12,
                'total_supply': '0',
                'logo': '',
                'website': '',
                'social': {},
                'chain': chain,
                'address': token_address
            }