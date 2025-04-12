from typing import Dict, Any, List
from common.config import Config
from web3 import Web3
from wallets.utils.chain_utils import ChainUtils

class EVMRPCService:
    """EVM RPC 服务"""
    
    def __init__(self):
        self.config = Config()
        self.web3 = Web3()
        # 设置警告过滤
        ChainUtils.setup_chain_warnings()
        # 注册额外的区块链网络
        ChainUtils.register_additional_chains(self.web3)
        
    async def get_balance(self, chain_type: str, address: str) -> Dict[str, Any]:
        """获取余额"""
        try:
            web3 = self.web3
            web3.eth.default_account = address
            
            # 获取链配置
            chain_config = self.config.get_chain_config(chain_type)
            if not chain_config:
                raise ValueError(f"Unsupported chain type: {chain_type}")
                
            # 连接节点
            web3.provider = Web3.HTTPProvider(chain_config['rpc_url'])
            
            # 获取余额
            balance = web3.eth.get_balance(address)
            return {
                'balance': str(balance),
                'chain': chain_type,
                'address': address
            }
            
        except Exception as e:
            raise Exception(f"Failed to get balance: {str(e)}")
            
    async def get_transaction(self, chain_type: str, tx_hash: str) -> Dict[str, Any]:
        """获取交易详情"""
        try:
            web3 = self.web3
            
            # 获取链配置
            chain_config = self.config.get_chain_config(chain_type)
            if not chain_config:
                raise ValueError(f"Unsupported chain type: {chain_type}")
                
            # 连接节点
            web3.provider = Web3.HTTPProvider(chain_config['rpc_url'])
            
            # 获取交易
            tx = web3.eth.get_transaction(tx_hash)
            return dict(tx)
            
        except Exception as e:
            raise Exception(f"Failed to get transaction: {str(e)}") 