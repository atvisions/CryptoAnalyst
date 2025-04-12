from typing import Dict, Any, List
from common.config import Config
from solana.rpc.api import Client
from solana.rpc.commitment import Commitment
from solana.rpc.types import TokenAccountOpts
from solana.publickey import PublicKey
import base58
from solders.pubkey import Pubkey
from decimal import Decimal

class SolanaBaseService:
    """Solana 链基础服务"""
    
    def __init__(self):
        self.config = Config()
        
    def _get_client(self, chain: str) -> Client:
        """获取 Solana 客户端"""
        config = self.config.get_solana_config(chain)
        return Client(config['rpc_url'], commitment=Commitment("confirmed"))
        
    def get_balance(self, chain: str, address: str) -> Dict[str, Any]:
        """获取余额"""
        try:
            client = self._get_client(chain)
            balance = client.get_balance(PublicKey(address))
            return {
                'balance': str(balance['result']['value']),
                'chain': chain,
                'address': address
            }
        except Exception as e:
            raise Exception(f"Failed to get balance: {str(e)}")
            
    def get_transaction(self, chain: str, tx_hash: str) -> Dict[str, Any]:
        """获取交易详情"""
        try:
            client = self._get_client(chain)
            tx = client.get_transaction(tx_hash)
            return tx['result']
        except Exception as e:
            raise Exception(f"Failed to get transaction: {str(e)}")
            
    def get_token_balance(self, chain: str, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取代币余额"""
        try:
            client = self._get_client(chain)
            token_accounts = client.get_token_accounts_by_owner(
                PublicKey(wallet_address),
                TokenAccountOpts(mint=PublicKey(token_address))
            )
            if not token_accounts['result']['value']:
                return {
                    'balance': '0',
                    'chain': chain,
                    'token_address': token_address,
                    'wallet_address': wallet_address
                }
            balance = token_accounts['result']['value'][0]['account']['data']['parsed']['info']['tokenAmount']['amount']
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
            client = self._get_client(chain)
            token_info = client.get_token_supply(PublicKey(token_address))
            return {
                'name': token_info['result']['value']['name'],
                'symbol': token_info['result']['value']['symbol'],
                'decimals': token_info['result']['value']['decimals'],
                'chain': chain,
                'address': token_address
            }
        except Exception as e:
            raise Exception(f"Failed to get token info: {str(e)}")

class SolanaRPCService:
    """Solana RPC 服务"""
    
    def __init__(self):
        """初始化 Solana RPC 客户端"""
        self.client = Client("https://api.mainnet-beta.solana.com")
        
    def get_balance(self, address: str) -> Dict[str, Any]:
        """获取账户余额"""
        try:
            pubkey = Pubkey.from_string(address)
            response = self.client.get_balance(pubkey, commitment=Commitment("confirmed"))
            if response.value is not None:
                # 将 lamports 转换为 SOL (1 SOL = 10^9 lamports)
                balance = Decimal(response.value) / Decimal(10**9)
                return {
                    'balance': str(balance),
                    'chain': 'SOL',
                    'address': address
                }
            raise Exception("获取余额失败")
        except Exception as e:
            raise Exception(f"获取余额失败: {str(e)}")
            
    def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取代币余额"""
        try:
            token_pubkey = Pubkey.from_string(token_address)
            wallet_pubkey = Pubkey.from_string(wallet_address)
            response = self.client.get_token_account_balance(token_pubkey)
            if response.value is not None:
                return {
                    'balance': str(response.value.amount),
                    'decimals': response.value.decimals,
                    'chain': 'SOL',
                    'token_address': token_address,
                    'wallet_address': wallet_address
                }
            raise Exception("获取代币余额失败")
        except Exception as e:
            raise Exception(f"获取代币余额失败: {str(e)}")
            
    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """获取代币信息"""
        try:
            token_pubkey = Pubkey.from_string(token_address)
            response = self.client.get_token_supply(token_pubkey)
            if response.value is not None:
                return {
                    'decimals': response.value.decimals,
                    'chain': 'SOL',
                    'address': token_address
                }
            raise Exception("获取代币信息失败")
        except Exception as e:
            raise Exception(f"获取代币信息失败: {str(e)}") 