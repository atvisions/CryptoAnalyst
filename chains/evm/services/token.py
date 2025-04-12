from typing import Dict, Any, List, Optional
from common.config import Config
from web3 import Web3
from wallets.utils.chain_utils import ChainUtils

class EVMTokenService:
    """EVM Token 服务"""
    
    def __init__(self):
        self.config = Config()
        self.web3 = Web3()
        # 设置警告过滤
        ChainUtils.setup_chain_warnings()
        # 注册额外的区块链网络
        ChainUtils.register_additional_chains(self.web3)
        
    async def get_token_balance(self, chain_type: str, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取代币余额"""
        try:
            web3 = self.web3
            
            # 获取链配置
            chain_config = self.config.get_chain_config(chain_type)
            if not chain_config:
                raise ValueError(f"Unsupported chain type: {chain_type}")
                
            # 连接节点
            web3.provider = Web3.HTTPProvider(chain_config['rpc_url'])
            
            # 获取代币合约
            token_contract = web3.eth.contract(
                address=token_address,
                abi=self.config.get_token_abi()
            )
            
            # 获取余额
            balance = token_contract.functions.balanceOf(wallet_address).call()
            return {
                'balance': str(balance),
                'chain': chain_type,
                'token_address': token_address,
                'wallet_address': wallet_address
            }
            
        except Exception as e:
            raise Exception(f"Failed to get token balance: {str(e)}")
            
    async def get_token_info(self, chain_type: str, token_address: str) -> Dict[str, Any]:
        """获取代币信息"""
        try:
            web3 = self.web3
            
            # 获取链配置
            chain_config = self.config.get_chain_config(chain_type)
            if not chain_config:
                raise ValueError(f"Unsupported chain type: {chain_type}")
                
            # 连接节点
            web3.provider = Web3.HTTPProvider(chain_config['rpc_url'])
            
            # 获取代币合约
            token_contract = web3.eth.contract(
                address=token_address,
                abi=self.config.get_token_abi()
            )
            
            # 获取代币信息
            name = token_contract.functions.name().call()
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            
            return {
                'name': name,
                'symbol': symbol,
                'decimals': decimals,
                'chain': chain_type,
                'address': token_address
            }
            
        except Exception as e:
            raise Exception(f"Failed to get token info: {str(e)}") 