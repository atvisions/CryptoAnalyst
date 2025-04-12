from typing import Dict, Any, List
from common.config import Config
from kadena_sdk.kadena_sdk import KadenaSdk
from kadena_sdk.key_pair import KeyPair
import requests
import json

class KadenaBaseService:
    """Kadena 链基础服务"""
    
    def __init__(self):
        self.config = Config()
        
    def _get_sdk(self, chain: str) -> KadenaSdk:
        """获取 Kadena SDK"""
        config = self.config.get_kadena_config(chain)
        return KadenaSdk(
            config['rpc_url'],
            config['chain_id'],
            config['network_id'],
            config['api_version']
        )
        
    def get_balance(self, chain: str, address: str) -> Dict[str, Any]:
        """获取余额"""
        try:
            sdk = self._get_sdk(chain)
            balance = sdk.get_balance(address)
            return {
                'balance': str(balance),
                'chain': chain,
                'address': address
            }
        except Exception as e:
            raise Exception(f"Failed to get balance: {str(e)}")
            
    def get_transaction(self, chain: str, tx_hash: str) -> Dict[str, Any]:
        """获取交易详情"""
        try:
            sdk = self._get_sdk(chain)
            tx = sdk.get_transaction(tx_hash)
            return tx
        except Exception as e:
            raise Exception(f"Failed to get transaction: {str(e)}")
            
    def get_token_balance(self, chain: str, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取代币余额"""
        try:
            sdk = self._get_sdk(chain)
            balance = sdk.get_token_balance(token_address, wallet_address)
            return {
                'balance': str(balance),
                'chain': chain,
                'token_address': token_address,
                'wallet_address': wallet_address
            }
        except Exception as e:
            raise Exception(f"Failed to get token balance: {str(e)}")
            
    def get_token_info(self, chain: str, token_address: str) -> Dict[str, Any]:
        """获取代币信息"""
        try:
            sdk = self._get_sdk(chain)
            info = sdk.get_token_info(token_address)
            return {
                'name': info['name'],
                'symbol': info['symbol'],
                'decimals': info['decimals'],
                'chain': chain,
                'address': token_address
            }
        except Exception as e:
            raise Exception(f"Failed to get token info: {str(e)}") 