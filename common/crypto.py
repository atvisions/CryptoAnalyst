from abc import ABC, abstractmethod
from typing import Optional
import hashlib
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base58
import base64

class WalletCryptoInterface(ABC):
    """钱包加密接口"""
    
    @abstractmethod
    def generate_mnemonic(self) -> str:
        """生成助记词"""
        pass
    
    @abstractmethod
    def mnemonic_to_private_key(self, mnemonic: str) -> str:
        """从助记词生成私钥"""
        pass
    
    @abstractmethod
    def private_key_to_address(self, private_key: str) -> str:
        """从私钥生成地址"""
        pass
    
    @abstractmethod
    def encrypt_private_key(self, private_key: str, password: str) -> str:
        """加密私钥"""
        pass
    
    @abstractmethod
    def decrypt_private_key(self, encrypted_private_key: str, password: str) -> str:
        """解密私钥"""
        pass

class BaseWalletCrypto(WalletCryptoInterface):
    """基础钱包加密服务"""
    
    def __init__(self, salt: Optional[bytes] = None):
        self.salt = salt or os.urandom(16)
    
    def _derive_key(self, password: str) -> bytes:
        """从密码派生密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def generate_mnemonic(self) -> str:
        """生成助记词"""
        # 这里使用随机字节生成助记词
        entropy = os.urandom(32)
        return base58.b58encode(entropy).decode()
    
    def mnemonic_to_private_key(self, mnemonic: str) -> str:
        """从助记词生成私钥"""
        # 这里使用助记词的哈希作为私钥
        return hashlib.sha256(mnemonic.encode()).hexdigest()
    
    def private_key_to_address(self, private_key: str) -> str:
        """从私钥生成地址"""
        # 这里使用私钥的哈希作为地址
        return "0x" + hashlib.sha256(private_key.encode()).hexdigest()[:40]
    
    def encrypt_private_key(self, private_key: str, password: str) -> str:
        """加密私钥"""
        key = self._derive_key(password)
        f = Fernet(key)
        return f.encrypt(private_key.encode()).decode()
    
    def decrypt_private_key(self, encrypted_private_key: str, password: str) -> str:
        """解密私钥"""
        key = self._derive_key(password)
        f = Fernet(key)
        return f.decrypt(encrypted_private_key.encode()).decode() 