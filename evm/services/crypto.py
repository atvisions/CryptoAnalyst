from eth_account import Account
from eth_keys import keys
from eth_utils import decode_hex, encode_hex
from web3 import Web3
from common.crypto import WalletCryptoInterface
import os
from cryptography.fernet import Fernet
import base64

class EVMCrypto(WalletCryptoInterface):
    """EVM 链加密实现"""
    
    def __init__(self):
        # 使用环境变量中的密钥或生成新的密钥
        key = os.getenv('EVM_ENCRYPTION_KEY', Fernet.generate_key())
        self.cipher_suite = Fernet(key)
    
    def encrypt_private_key(self, private_key: str, password: str) -> str:
        """加密私钥
        
        使用 Fernet 对称加密算法加密私钥
        """
        # 将私钥和密码组合后进行加密
        data = f"{private_key}:{password}".encode()
        encrypted_data = self.cipher_suite.encrypt(data)
        return base64.b64encode(encrypted_data).decode()
    
    def decrypt_private_key(self, encrypted_key: str, password: str) -> str:
        """解密私钥"""
        try:
            encrypted_data = base64.b64decode(encrypted_key)
            decrypted_data = self.cipher_suite.decrypt(encrypted_data).decode()
            stored_private_key, stored_password = decrypted_data.split(':')
            if stored_password != password:
                raise ValueError("Invalid password")
            return stored_private_key
        except Exception as e:
            raise ValueError(f"Failed to decrypt private key: {str(e)}")
    
    def generate_mnemonic(self) -> str:
        """生成助记词"""
        return Account.create().mnemonic
    
    def mnemonic_to_private_key(self, mnemonic: str) -> str:
        """从助记词生成私钥"""
        account = Account.from_mnemonic(mnemonic)
        return account.key.hex()
    
    def private_key_to_address(self, private_key: str) -> str:
        """从私钥生成地址"""
        private_key_bytes = decode_hex(private_key)
        private_key_obj = keys.PrivateKey(private_key_bytes)
        return private_key_obj.public_key.to_checksum_address() 