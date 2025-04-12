from typing import Dict, Any, List
from web3 import Web3
from decimal import Decimal
from common.config import Config

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
            return []
        except Exception as e:
            raise Exception(f"获取代币列表失败: {str(e)}")
            
    def get_token_metadata(self, token_address: str) -> Dict[str, Any]:
        """获取代币元数据"""
        try:
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
            
            contract = self.web3.eth.contract(address=token_address, abi=erc20_abi)
            name = contract.functions.name().call()
            symbol = contract.functions.symbol().call()
            decimals = contract.functions.decimals().call()
            
            return {
                'name': name,
                'symbol': symbol,
                'decimals': decimals
            }
        except Exception as e:
            raise Exception(f"获取代币元数据失败: {str(e)}")
            
    def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取特定代币余额"""
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