from web3 import Web3
from eth_account import Account
from kadena_python import Kadena
import os
from dotenv import load_dotenv

load_dotenv()

class WalletService:
    def __init__(self):
        # EVM 配置
        self.web3 = Web3(Web3.HTTPProvider(os.getenv('ETH_RPC_URL', 'https://mainnet.infura.io/v3/your-project-id')))
        
        # Kadena 配置
        self.kadena = Kadena(
            network_id=os.getenv('KADENA_NETWORK_ID', 'mainnet01'),
            host=os.getenv('KADENA_HOST', 'https://api.chainweb.com')
        )
    
    def create_evm_wallet(self):
        account = Account.create()
        return {
            'address': account.address,
            'private_key': account.key.hex(),
            'public_key': account.publickey.hex()
        }
    
    def create_kadena_wallet(self):
        account = self.kadena.create_account()
        return {
            'address': account['account'],
            'private_key': account['private_key'],
            'public_key': account['public_key']
        }
    
    def get_balance(self, chain, address):
        if chain == 'EVM':
            balance = self.web3.eth.get_balance(address)
            return self.web3.from_wei(balance, 'ether')
        elif chain == 'KADENA':
            balance = self.kadena.get_balance(address)
            return balance
        return None 