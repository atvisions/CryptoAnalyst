from typing import List, Dict, Any, Optional
from .interfaces import WalletInterface, PaymentPasswordInterface, ChainInterface
from .crypto import WalletCryptoInterface
from .database import Database
from web3 import Web3
from solana.keypair import Keypair
from kadena_sdk.kadena_sdk import KadenaSdk
from kadena_sdk.key_pair import KeyPair
import nacl.signing
import hashlib
import base64
from .config import Config
import requests
import json

class WalletService(WalletInterface):
    """钱包服务类"""

    def __init__(self, crypto_service: WalletCryptoInterface, db: Database):
        self.crypto_service = crypto_service
        self.db = db

    def create_wallet(self, device_id: str, payment_password: str, chain: str) -> Dict[str, Any]:
        """创建新钱包"""
        if chain == "ETH":
            # 创建以太坊钱包
            w3 = Web3()
            account = w3.eth.account.create()
            private_key = account.key.hex()
            address = account.address
            encrypted_private_key = self.crypto_service.encrypt_private_key(private_key, payment_password)

            wallet_data = {
                "device_id": device_id,
                "address": address,
                "private_key": encrypted_private_key,
                "chain": chain
            }

        elif chain == "SOL":
            # 创建 Solana 钱包
            keypair = Keypair()
            private_key = keypair.secret_key.hex()
            address = str(keypair.public_key)
            encrypted_private_key = self.crypto_service.encrypt_private_key(private_key, payment_password)

            wallet_data = {
                "device_id": device_id,
                "address": address,
                "private_key": encrypted_private_key,
                "chain": chain
            }

        elif chain == "KDA":
            # 创建 Kadena 钱包
            signing_key = nacl.signing.SigningKey.generate()
            verify_key = signing_key.verify_key
            private_key = signing_key.encode().hex()
            public_key = verify_key.encode().hex()
            address = f"k:{public_key}"
            encrypted_private_key = self.crypto_service.encrypt_private_key(private_key, payment_password)

            wallet_data = {
                "device_id": device_id,
                "address": address,
                "private_key": encrypted_private_key,
                "chain": chain
            }

        else:
            raise ValueError(f"不支持的链类型: {chain}")

        # 保存到数据库
        wallet = self.db.add_wallet(wallet_data)
        return {
            "wallet_id": wallet.id,
            "address": wallet.address,
            "chain": wallet.chain
        }

    def import_by_private_key(self, device_id: str, private_key: str, payment_password: str, chain: str) -> Dict[str, Any]:
        """通过私钥导入钱包"""
        if chain == "ETH":
            w3 = Web3()
            account = w3.eth.account.from_key(private_key)
            address = account.address

        elif chain == "SOL":
            keypair = Keypair.from_secret_key(bytes.fromhex(private_key))
            address = str(keypair.public_key)

        elif chain == "KDA":
            signing_key = nacl.signing.SigningKey(bytes.fromhex(private_key))
            verify_key = signing_key.verify_key
            public_key = verify_key.encode().hex()
            address = f"k:{public_key}"

        else:
            raise ValueError(f"不支持的链类型: {chain}")

        encrypted_private_key = self.crypto_service.encrypt_private_key(private_key, payment_password)

        wallet_data = {
            "device_id": device_id,
            "address": address,
            "private_key": encrypted_private_key,
            "chain": chain
        }

        wallet = self.db.add_wallet(wallet_data)
        return {
            "wallet_id": wallet.id,
            "address": wallet.address,
            "chain": wallet.chain
        }

    def import_by_mnemonic(self, device_id: str, mnemonic: str, payment_password: str, chain: str) -> Dict[str, Any]:
        """通过助记词导入钱包"""
        if chain == "ETH":
            w3 = Web3()
            account = w3.eth.account.from_mnemonic(mnemonic)
            private_key = account.key.hex()
            address = account.address

        elif chain == "SOL":
            # Solana 不支持助记词导入
            raise ValueError("Solana 不支持助记词导入")

        elif chain == "KDA":
            # Kadena 不支持助记词导入
            raise ValueError("Kadena 不支持助记词导入")

        else:
            raise ValueError(f"不支持的链类型: {chain}")

        encrypted_private_key = self.crypto_service.encrypt_private_key(private_key, payment_password)

        wallet_data = {
            "device_id": device_id,
            "address": address,
            "private_key": encrypted_private_key,
            "chain": chain,
            "mnemonic": self.crypto_service.encrypt_private_key(mnemonic, payment_password)
        }

        wallet = self.db.add_wallet(wallet_data)
        return {
            "wallet_id": wallet.id,
            "address": wallet.address,
            "chain": wallet.chain
        }

    def import_watch_only(self, device_id: str, address: str, name: str, chain: str) -> Dict[str, Any]:
        """导入观察者钱包"""
        wallet_data = {
            "device_id": device_id,
            "address": address,
            "name": name,
            "chain": chain,
            "is_watch_only": True
        }

        wallet = self.db.add_wallet(wallet_data)
        return {
            "wallet_id": wallet.id,
            "address": wallet.address,
            "chain": wallet.chain,
            "name": wallet.name
        }

    def get_wallet_list(self, device_id: str) -> List[Dict[str, Any]]:
        """获取钱包列表"""
        wallets = self.db.get_wallets_by_device(device_id)
        return [{
            "wallet_id": wallet.id,
            "address": wallet.address,
            "chain": wallet.chain,
            "name": wallet.name,
            "is_watch_only": wallet.is_watch_only
        } for wallet in wallets]

    def rename_wallet(self, wallet_id: int, new_name: str) -> Dict[str, Any]:
        """重命名钱包"""
        wallet = self.db.update_wallet(wallet_id, {"name": new_name})
        if wallet:
            return {
                "wallet_id": wallet.id,
                "address": wallet.address,
                "chain": wallet.chain,
                "name": wallet.name
            }
        return {}

    def delete_wallet(self, wallet_id: int, payment_password: str) -> bool:
        """软删除钱包，将其标记为未激活"""
        wallet = self.db.get_wallet(wallet_id)
        if wallet and not wallet.is_watch_only:
            # 验证支付密码
            password = self.db.get_payment_password(wallet.device_id)
            if not password or not self.crypto_service.verify_password(payment_password, password.password_hash):
                raise ValueError("支付密码错误")

        # 软删除钱包
        return self.db.delete_wallet(wallet_id)

    def show_private_key(self, wallet_id: int, payment_password: str) -> str:
        """显示私钥"""
        wallet = self.db.get_wallet(wallet_id)
        if not wallet or wallet.is_watch_only:
            raise ValueError("钱包不存在或是观察者钱包")

        # 验证支付密码
        password = self.db.get_payment_password(wallet.device_id)
        if not password or not self.crypto_service.verify_password(payment_password, password.password_hash):
            raise ValueError("支付密码错误")

        return self.crypto_service.decrypt_private_key(wallet.private_key, payment_password)

class PaymentPasswordService(PaymentPasswordInterface):
    """支付密码服务类"""

    def __init__(self, crypto_service: WalletCryptoInterface, db: Database):
        self.crypto_service = crypto_service
        self.db = db

    def set_password(self, device_id: str, payment_password: str, payment_password_confirm: str) -> bool:
        """设置支付密码"""
        if payment_password != payment_password_confirm:
            raise ValueError("两次输入的密码不一致")

        password_hash = self.crypto_service.hash_password(payment_password)
        self.db.set_payment_password(device_id, password_hash)
        return True

    def verify_password(self, device_id: str, payment_password: str) -> bool:
        """验证支付密码"""
        password = self.db.get_payment_password(device_id)
        if not password:
            raise ValueError("未设置支付密码")

        return self.crypto_service.verify_password(payment_password, password.password_hash)

    def change_password(self, device_id: str, old_password: str, new_password: str, confirm_password: str) -> bool:
        """修改支付密码"""
        if new_password != confirm_password:
            raise ValueError("两次输入的新密码不一致")

        # 验证旧密码
        if not self.verify_password(device_id, old_password):
            raise ValueError("旧密码错误")

        # 更新新密码
        new_password_hash = self.crypto_service.hash_password(new_password)
        self.db.update_payment_password(device_id, new_password_hash)
        return True

    def get_password_status(self, device_id: str) -> bool:
        """获取密码设置状态"""
        password = self.db.get_payment_password(device_id)
        return password is not None

class BaseChainService(ChainInterface):
    """基础链服务"""

    def __init__(self):
        self.config = Config()

    def get_supported_chains(self) -> List[Dict[str, Any]]:
        """获取支持的链列表"""
        chains = []
        for chain_code, config in self.config.RPC_CONFIGS.items():
            chain_info = {
                "name": chain_code,
                "code": chain_code,
                "rpc_url": config["rpc_url"]
            }
            if "moralis_url" in config:
                chain_info["moralis_url"] = config["moralis_url"]
            chains.append(chain_info)
        return chains

    def select_chain(self, device_id: str, chain: str) -> bool:
        """选择链"""
        if chain not in self.config.RPC_CONFIGS:
            raise ValueError(f"不支持的链类型: {chain}")

        # 这里需要将选择的链保存到数据库
        return True

    def verify_mnemonic(self, device_id: str, chain: str, mnemonic: str, payment_password: str) -> bool:
        """验证助记词"""
        if chain.startswith("ETH") or chain.startswith("BSC") or chain.startswith("MATIC") or \
           chain.startswith("ARB") or chain.startswith("OP") or chain.startswith("AVAX") or \
           chain.startswith("FTM") or chain.startswith("CRO"):
            # 使用 Moralis API 验证助记词
            try:
                moralis_url = self.config.get_moralis_url(chain)
                headers = {
                    "X-API-Key": self.config.MORALIS_API_KEY,
                    "Content-Type": "application/json"
                }
                data = {
                    "mnemonic": mnemonic
                }
                response = requests.post(
                    f"{moralis_url}/wallet/verify",
                    headers=headers,
                    json=data
                )
                return response.status_code == 200
            except:
                return False
        elif chain.startswith("SOL"):
            # Solana 不支持助记词
            return False
        elif chain.startswith("KDA"):
            # Kadena 不支持助记词
            return False
        else:
            raise ValueError(f"不支持的链类型: {chain}")

    def get_balance(self, device_id: str, chain: str, address: str) -> Dict[str, Any]:
        """获取账户余额"""
        if chain.startswith("ETH") or chain.startswith("BSC") or chain.startswith("MATIC") or \
           chain.startswith("ARB") or chain.startswith("OP") or chain.startswith("AVAX") or \
           chain.startswith("FTM") or chain.startswith("CRO"):
            # 使用 Moralis API 获取余额
            moralis_url = self.config.get_moralis_url(chain)
            headers = {
                "X-API-Key": self.config.MORALIS_API_KEY,
                "Content-Type": "application/json"
            }
            response = requests.get(
                f"{moralis_url}/{address}/balance",
                headers=headers
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise ValueError(f"获取余额失败: {response.text}")
        elif chain.startswith("SOL"):
            # 使用 Helius API 获取 Solana 余额
            rpc_url = self.config.get_rpc_url(chain)
            headers = {
                "Content-Type": "application/json"
            }
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }
            response = requests.post(rpc_url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                return {
                    "balance": result["result"]["value"] / 1e9,  # 转换为 SOL
                    "unit": "SOL"
                }
            else:
                raise ValueError(f"获取余额失败: {response.text}")
        elif chain.startswith("KDA"):
            # 使用 Kadena API 获取余额
            kadena_config = self.config.get_kadena_config(chain)
            headers = {
                "Content-Type": "application/json"
            }
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "account_balance",
                "params": {
                    "chain_id": kadena_config["chain_id"],
                    "network_id": kadena_config["network_id"],
                    "account": address
                }
            }
            response = requests.post(
                f"{kadena_config['rpc_url']}/{kadena_config['api_version']}/account/balance",
                headers=headers,
                json=data
            )
            if response.status_code == 200:
                result = response.json()
                return {
                    "balance": float(result["result"]["balance"]),
                    "unit": "KDA"
                }
            else:
                raise ValueError(f"获取余额失败: {response.text}")
        else:
            raise ValueError(f"不支持的链类型: {chain}")

    def get_transaction_history(self, device_id: str, chain: str, address: str, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        """获取交易历史"""
        if chain.startswith("ETH") or chain.startswith("BSC") or chain.startswith("MATIC") or \
           chain.startswith("ARB") or chain.startswith("OP") or chain.startswith("AVAX") or \
           chain.startswith("FTM") or chain.startswith("CRO"):
            # 使用 Moralis API 获取交易历史
            moralis_url = self.config.get_moralis_url(chain)
            headers = {
                "X-API-Key": self.config.MORALIS_API_KEY,
                "Content-Type": "application/json"
            }
            response = requests.get(
                f"{moralis_url}/{address}/transactions",
                headers=headers,
                params={"page": page, "limit": limit}
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise ValueError(f"获取交易历史失败: {response.text}")
        elif chain.startswith("SOL"):
            # 使用 Helius API 获取 Solana 交易历史
            rpc_url = self.config.get_rpc_url(chain)
            headers = {
                "Content-Type": "application/json"
            }
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [address, {"limit": limit}]
            }
            response = requests.post(rpc_url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                return {
                    "transactions": result["result"],
                    "page": page,
                    "limit": limit
                }
            else:
                raise ValueError(f"获取交易历史失败: {response.text}")
        elif chain.startswith("KDA"):
            # 使用 Kadena API 获取交易历史
            kadena_config = self.config.get_kadena_config(chain)
            headers = {
                "Content-Type": "application/json"
            }
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "account_transactions",
                "params": {
                    "chain_id": kadena_config["chain_id"],
                    "network_id": kadena_config["network_id"],
                    "account": address,
                    "page": page,
                    "limit": limit
                }
            }
            response = requests.post(
                f"{kadena_config['rpc_url']}/{kadena_config['api_version']}/account/transactions",
                headers=headers,
                json=data
            )
            if response.status_code == 200:
                result = response.json()
                return {
                    "transactions": result["result"],
                    "page": page,
                    "limit": limit
                }
            else:
                raise ValueError(f"获取交易历史失败: {response.text}")
        else:
            raise ValueError(f"不支持的链类型: {chain}")