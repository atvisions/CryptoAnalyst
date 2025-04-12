from typing import Dict, Any
from web3 import Web3
from decimal import Decimal
from common.config import Config

class EVMBalanceService:
    """EVM 余额服务"""
    
    def __init__(self, chain: str):
        """初始化 EVM RPC 客户端"""
        config = Config.get_evm_config(chain)
        self.web3 = Web3(Web3.HTTPProvider(config["rpc_url"]))
        self.chain = chain
        
    def get_balance(self, address: str) -> Dict[str, Any]:
        """获取账户余额"""
        try:
            balance = self.web3.eth.get_balance(address)
            return {
                'balance': str(Decimal(balance) / Decimal(10**18)),  # 转换为 ETH
                'chain': self.chain,
                'address': address
            }
        except Exception as e:
            raise Exception(f"获取余额失败: {str(e)}")
            
    def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取代币余额"""
        try:
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
            
            contract = self.web3.eth.contract(address=token_address, abi=erc20_abi)
            balance = contract.functions.balanceOf(wallet_address).call()
            decimals = contract.functions.decimals().call()
            
            return {
                'balance': str(Decimal(balance) / Decimal(10**decimals)),
                'decimals': decimals,
                'chain': self.chain,
                'token_address': token_address,
                'wallet_address': wallet_address
            }
        except Exception as e:
            raise Exception(f"获取代币余额失败: {str(e)}") 