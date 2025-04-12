from typing import Dict, Any, List
from common.config import Config
from web3 import Web3
from wallets.utils import ChainUtils

class EVMRPCService:
    """EVM 链基础服务"""
    
    def __init__(self, chain: str):
        self.config = Config()
        self.chain = chain
        self.web3 = self._get_web3(chain)
        # 设置警告过滤
        ChainUtils.setup_chain_warnings()
        # 注册额外的区块链网络
        ChainUtils.register_additional_chains(self.web3)
        
    def _get_web3(self, chain: str) -> Web3:
        """获取 Web3 实例"""
        config = self.config.get_evm_config(chain)
        web3 = Web3(Web3.HTTPProvider(config['rpc_url']))
        return web3
        
    def get_balance(self, address: str) -> Dict[str, Any]:
        """获取余额"""
        try:
            balance = self.web3.eth.get_balance(address)
            return {
                'balance': str(balance),
                'chain': self.chain,
                'address': address
            }
        except Exception as e:
            raise Exception(f"获取余额失败: {str(e)}")
            
    def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """获取交易详情"""
        try:
            tx = self.web3.eth.get_transaction(tx_hash)
            return dict(tx)
        except Exception as e:
            raise Exception(f"获取交易详情失败: {str(e)}")
            
    def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取代币余额"""
        try:
            token_contract = self.web3.eth.contract(
                address=token_address,
                abi=self.config.get_token_abi()
            )
            balance = token_contract.functions.balanceOf(wallet_address).call()
            return {
                'balance': str(balance),
                'chain': self.chain,
                'token_address': token_address,
                'wallet_address': wallet_address
            }
        except Exception as e:
            raise Exception(f"获取代币余额失败: {str(e)}")
            
    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """获取代币信息"""
        try:
            token_contract = self.web3.eth.contract(
                address=token_address,
                abi=self.config.get_token_abi()
            )
            name = token_contract.functions.name().call()
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            return {
                'name': name,
                'symbol': symbol,
                'decimals': decimals,
                'chain': self.chain,
                'address': token_address
            }
        except Exception as e:
            raise Exception(f"获取代币信息失败: {str(e)}") 