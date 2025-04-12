from kadena_sdk.kadena_sdk import KadenaSdk
from kadena_sdk.key_pair import KeyPair
import unittest
import nacl.signing
import base64

class TestKadenaSDK(unittest.TestCase):
    def setUp(self):
        # 生成新的密钥对
        signing_key = nacl.signing.SigningKey.generate()
        verify_key = signing_key.verify_key
        
        # 转换为十六进制格式
        private_key = signing_key.encode().hex()
        public_key = verify_key.encode().hex()
        
        # 创建 KeyPair 对象
        self.key_pair = KeyPair(type='json', priv_key=private_key, pub_key=public_key)
        self.client = KadenaSdk(base_url="https://api.testnet.chainweb.com", key_pair=self.key_pair)
    
    def test_key_pair(self):
        """测试密钥对"""
        self.assertIsNotNone(self.key_pair.get_pub_key())
        self.assertIsNotNone(self.key_pair.get_priv_key())
        
    def test_account_info(self):
        """测试账户信息查询"""
        account = f"k:{self.key_pair.get_pub_key()}"
        command = {
            "networkId": "testnet04",
            "payload": {
                "exec": {
                    "code": f"(coin.get-balance \"{account}\")",
                    "data": {}
                }
            },
            "meta": {
                "chainId": "0",
                "sender": account,
                "gasLimit": 2000,
                "gasPrice": 0.000001,
                "ttl": 28800
            }
        }
        response = self.client.local({"0": command})
        self.assertIsNotNone(response)

if __name__ == '__main__':
    unittest.main() 