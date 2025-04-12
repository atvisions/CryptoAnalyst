from typing import Dict, Any, List
from solana.rpc.api import Client
from solana.rpc.commitment import Commitment
from solana.publickey import PublicKey
from solana.rpc.types import TokenAccountOpts
from decimal import Decimal
from common.config import Config

class SolanaTokenService:
    """Solana 代币服务"""
    
    def __init__(self):
        """初始化 Solana RPC 客户端"""
        config = Config.get_solana_config("SOL")
        self.client = Client(config["rpc_url"])
        
    def get_token_list(self, wallet_address: str) -> List[Dict[str, Any]]:
        """获取钱包持有的代币列表"""
        try:
            wallet_pubkey = PublicKey(wallet_address)
            response = self.client.get_token_accounts_by_owner(
                wallet_pubkey,
                TokenAccountOpts(program_id=PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
            )
            
            tokens = []
            for account in response['result']['value']:
                token_info = account['account']['data']['parsed']['info']
                token_mint = token_info['mint']
                token_amount = token_info['tokenAmount']
                
                # 获取代币元数据
                token_metadata = self.get_token_metadata(token_mint)
                
                tokens.append({
                    'address': token_mint,
                    'name': token_metadata.get('name', 'Unknown'),
                    'symbol': token_metadata.get('symbol', 'Unknown'),
                    'decimals': token_amount['decimals'],
                    'balance': str(Decimal(token_amount['amount']) / Decimal(10**token_amount['decimals'])),
                    'chain': 'SOL'
                })
            return tokens
        except Exception as e:
            raise Exception(f"获取代币列表失败: {str(e)}")
            
    def get_token_metadata(self, token_address: str) -> Dict[str, Any]:
        """获取代币元数据"""
        try:
            token_pubkey = PublicKey(token_address)
            response = self.client.get_token_supply(token_pubkey)
            if response['result']['value'] is not None:
                return {
                    'name': response['result']['value'].get('name', 'Unknown'),
                    'symbol': response['result']['value'].get('symbol', 'Unknown'),
                    'decimals': response['result']['value'].get('decimals', 9)
                }
            return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}
        except Exception as e:
            raise Exception(f"获取代币元数据失败: {str(e)}")
            
    def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取特定代币余额"""
        try:
            token_pubkey = PublicKey(token_address)
            wallet_pubkey = PublicKey(wallet_address)
            response = self.client.get_token_account_balance(token_pubkey)
            if response['result']['value'] is not None:
                token_amount = response['result']['value']
                return {
                    'balance': str(Decimal(token_amount['amount']) / Decimal(10**token_amount['decimals'])),
                    'decimals': token_amount['decimals'],
                    'chain': 'SOL',
                    'token_address': token_address,
                    'wallet_address': wallet_address
                }
            return {
                'balance': '0',
                'chain': 'SOL',
                'token_address': token_address,
                'wallet_address': wallet_address
            }
        except Exception as e:
            raise Exception(f"获取代币余额失败: {str(e)}") 