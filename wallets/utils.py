from mnemonic import Mnemonic
from eth_account import Account
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import hashlib
from cryptography.fernet import Fernet
import base64
import base58
from kadena_sdk.kadena_sdk import KadenaSdk
from kadena_sdk.key_pair import KeyPair
import nacl.signing
from typing import Tuple, Dict, Any
from web3 import Web3
import warnings
import re
import logging

logger = logging.getLogger(__name__)

class ChainUtils:
    """链工具类"""

    @staticmethod
    def setup_chain_warnings():
        """设置警告过滤"""
        warnings.filterwarnings('ignore', category=UserWarning)

    @staticmethod
    def register_additional_chains(web3: Web3):
        """注册额外的区块链网络"""
        from common.config import Config

        # 注册 BSC 主网
        bsc_config = Config.get_evm_config("BSC")
        web3.eth.account.enable_unaudited_hdwallet_features()
        web3.eth.account.register_network(
            "BSC",
            chain_id=56,
            slip44=714,
            hrp="bnb",
            symbol="BNB",
            explorer="https://bscscan.com",
            rpc_url=bsc_config["rpc_url"]
        )

        # 注册 Polygon 主网
        matic_config = Config.get_evm_config("MATIC")
        web3.eth.account.register_network(
            "MATIC",
            chain_id=137,
            slip44=966,
            hrp="matic",
            symbol="MATIC",
            explorer="https://polygonscan.com",
            rpc_url=matic_config["rpc_url"]
        )

        # 注册 Arbitrum 主网
        arb_config = Config.get_evm_config("ARB")
        web3.eth.account.register_network(
            "ARB",
            chain_id=42161,
            slip44=9001,
            hrp="arb",
            symbol="ETH",
            explorer="https://arbiscan.io",
            rpc_url=arb_config["rpc_url"]
        )

def generate_mnemonic() -> str:
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

def generate_wallet_from_mnemonic(mnemonic: str, chain: str) -> Tuple[str, str]:
    """从助记词生成钱包"""
    if not validate_mnemonic(mnemonic):
        raise ValueError("无效的助记词")

    if chain in ["ETH", "BSC", "MATIC", "ARB", "OP", "AVAX", "BASE"]:
        # 生成 EVM 钱包
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(mnemonic)
        account = Account.create()
        return account.address, account.key.hex()
    elif chain == "SOL":
        # 生成 Solana 钱包
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(mnemonic)
        keypair = Keypair.from_seed(seed[:32])  # 使用前32字节作为种子
        return str(keypair.pubkey()), str(keypair)
    elif chain == "KDA":
        # 生成 Kadena 钱包
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(mnemonic)
        signing_key = nacl.signing.SigningKey(seed[:32])  # 使用前32字节作为种子
        verify_key = signing_key.verify_key
        private_key = signing_key.encode().hex()
        public_key = verify_key.encode().hex()
        address = f"k:{public_key}"
        return address, private_key
    else:
        raise ValueError(f"不支持的链类型: {chain}")

def encrypt_private_key(private_key: str, payment_password: str) -> str:
    """加密私钥"""
    # 使用支付密码生成密钥
    key = hashlib.sha256(payment_password.encode()).digest()
    f = Fernet(base64.urlsafe_b64encode(key))
    encrypted = f.encrypt(private_key.encode())
    return encrypted.decode()

def decrypt_private_key(encrypted_key: str, payment_password: str) -> str:
    """解密私钥"""
    try:
        # 使用支付密码生成密钥
        key = hashlib.sha256(payment_password.encode()).digest()
        f = Fernet(base64.urlsafe_b64encode(key))
        decrypted = f.decrypt(encrypted_key.encode())
        return decrypted.decode()
    except:
        raise ValueError("解密失败，请检查支付密码是否正确")

def sanitize_token_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    清理代币数据，移除或替换不兼容的字符

    参数:
        data: 代币元数据字典

    返回:
        清理后的代币元数据字典
    """
    if not data:
        return data

    # 创建一个新的字典来存储清理后的数据
    cleaned_data = {}

    for key, value in data.items():
        # 如果值是字符串，清理它
        if isinstance(value, str):
            # 移除表情符号和其他特殊Unicode字符
            # 这里使用一个简单的正则表达式来保留基本的ASCII字符和一些常见的Unicode字符
            cleaned_value = re.sub(r'[^\x00-\x7F\u00A0-\u00FF\u0100-\u017F\u0180-\u024F]', '', value)
            cleaned_data[key] = cleaned_value
        elif isinstance(value, dict):
            # 如果值是字典，递归清理
            cleaned_data[key] = sanitize_token_data(value)
        elif isinstance(value, list):
            # 如果值是列表，递归清理每个元素
            cleaned_data[key] = [sanitize_token_data(item) if isinstance(item, dict) else item for item in value]
        else:
            # 其他类型的值直接复制
            cleaned_data[key] = value

    return cleaned_data