"""
Kadena KeyPair module
"""

import nacl.signing
import base64
from typing import Dict, Any, Optional


class KeyPair:
    """Kadena 密钥对"""

    def __init__(self, type: str = 'json', priv_key: Optional[str] = None, pub_key: Optional[str] = None):
        """
        初始化密钥对
        
        Args:
            type: 密钥类型，支持 'json' 和 'ed25519'
            priv_key: 私钥（十六进制字符串）
            pub_key: 公钥（十六进制字符串）
        """
        self.type = type
        
        if priv_key and pub_key:
            self.priv_key = priv_key
            self.pub_key = pub_key
        else:
            # 生成新的密钥对
            signing_key = nacl.signing.SigningKey.generate()
            verify_key = signing_key.verify_key
            
            # 转换为十六进制格式
            self.priv_key = signing_key.encode().hex()
            self.pub_key = verify_key.encode().hex()
    
    def get_pub_key(self) -> str:
        """获取公钥"""
        return self.pub_key
    
    def get_priv_key(self) -> str:
        """获取私钥"""
        return self.priv_key
    
    def get_address(self) -> str:
        """获取地址"""
        return f"k:{self.pub_key}"
    
    def sign(self, message: str) -> str:
        """
        签名消息
        
        Args:
            message: 要签名的消息
            
        Returns:
            签名结果（base64编码）
        """
        # 将私钥从十六进制转换为字节
        priv_key_bytes = bytes.fromhex(self.priv_key)
        
        # 创建签名密钥
        signing_key = nacl.signing.SigningKey(priv_key_bytes)
        
        # 签名消息
        signature = signing_key.sign(message.encode())
        
        # 返回base64编码的签名
        return base64.b64encode(signature.signature).decode()
    
    def verify(self, message: str, signature: str) -> bool:
        """
        验证签名
        
        Args:
            message: 原始消息
            signature: base64编码的签名
            
        Returns:
            验证结果
        """
        try:
            # 将公钥从十六进制转换为字节
            pub_key_bytes = bytes.fromhex(self.pub_key)
            
            # 创建验证密钥
            verify_key = nacl.signing.VerifyKey(pub_key_bytes)
            
            # 解码签名
            signature_bytes = base64.b64decode(signature)
            
            # 验证签名
            verify_key.verify(message.encode(), signature_bytes)
            return True
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'type': self.type,
            'publicKey': self.pub_key,
            'privateKey': self.priv_key,
            'address': self.get_address()
        }
