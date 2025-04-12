from solana.keypair import Keypair
from solana.publickey import PublicKey
from common.crypto import WalletCryptoInterface
import os
from cryptography.fernet import Fernet
import base64

class SolanaCrypto(WalletCryptoInterface):
    """Solana 链加密实现"""
    
    def __init__(self):
        # 使用环境变量中的密钥或生成新的密钥
        key = os.getenv('SOLANA_ENCRYPTION_KEY', Fernet.generate_key())
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
        keypair = Keypair()
        return keypair.secret_key.hex()
    
    def mnemonic_to_private_key(self, mnemonic: str) -> str:
        """从助记词生成私钥"""
        # Solana 的助记词实际上就是私钥
        return mnemonic
    
    def private_key_to_address(self, private_key: str) -> str:
        """从私钥生成地址"""
        keypair = Keypair.from_secret_key(bytes.fromhex(private_key))
        return str(keypair.public_key) 