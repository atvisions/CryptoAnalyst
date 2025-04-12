from mnemonic import Mnemonic
from eth_account import Account
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import hashlib
from cryptography.fernet import Fernet
import base64
import base58

def generate_mnemonic():
    """生成助记词"""
    mnemo = Mnemonic("english")
    return mnemo.generate()

def validate_mnemonic(mnemonic: str) -> bool:
    """验证助记词是否有效"""
    try:
        mnemo = Mnemonic("english")
        return mnemo.check(mnemonic)
    except Exception:
        return False

def generate_wallet_from_mnemonic(mnemonic: str, chain: str) -> dict:
    """从助记词生成钱包"""
    try:
        if chain in ['ETH', 'Ethereum']:
            # 生成以太坊钱包
            account = Account.create()
            return {
                'address': account.address,
                'private_key': account.key.hex()
            }
            
        elif chain in ['SOL', 'Solana']:
            # 生成 Solana 钱包
            mnemo = Mnemonic("english")
            seed = mnemo.to_seed(mnemonic)
            keypair = Keypair.from_seed(seed[:32])  # 使用前32字节作为种子
            # 将私钥和公钥组合成64字节数组
            private_key_bytes = keypair.secret()
            public_key_bytes = bytes(keypair.pubkey())
            full_keypair = private_key_bytes + public_key_bytes
            # 使用 base58 编码
            private_key = base58.b58encode(full_keypair).decode()
            return {
                'address': str(keypair.pubkey()),
                'private_key': private_key
            }
            
        else:
            raise ValueError(f"Unsupported chain: {chain}")
            
    except Exception as e:
        raise Exception(f"Failed to generate wallet: {str(e)}")

def encrypt_private_key(private_key: str, password: str) -> str:
    """加密私钥"""
    # 使用支付密码生成密钥
    key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
    f = Fernet(key)
    
    # 加密私钥
    encrypted_private_key = f.encrypt(private_key.encode()).decode()
    return encrypted_private_key

def decrypt_private_key(encrypted_private_key, payment_password):
    """解密私钥"""
    # 使用支付密码生成密钥
    key = base64.urlsafe_b64encode(hashlib.sha256(payment_password.encode()).digest())
    f = Fernet(key)
    
    # 解密私钥
    decrypted_private_key = f.decrypt(encrypted_private_key.encode()).decode()
    return decrypted_private_key 