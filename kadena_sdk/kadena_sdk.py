"""
Kadena SDK for Python
"""

import requests
import json
import time
import hashlib
import base64
from typing import Dict, Any, List, Optional, Union
from decimal import Decimal
from .key_pair import KeyPair


class KadenaSdk:
    """Kadena SDK"""

    def __init__(self, rpc_url: str, kadena_chain_id: str, network_id: str, api_version: str = 'v1', key_pair: Optional[KeyPair] = None):
        """
        初始化 Kadena SDK

        Args:
            rpc_url: RPC 服务器地址
            kadena_chain_id: Kadena 链 ID（这是 Kadena 平行链 ID，范围为 0-19）
                    注意: 这与钱包模型中的 "chain" 字段（如 "KDA", "KDA_TESTNET"）不同
            network_id: 网络 ID（如 "mainnet01", "testnet04"）
            api_version: API 版本（如 "chainweb/0.0/mainnet01/chain/0"）
            key_pair: 密钥对
        """
        self.rpc_url = rpc_url
        self.kadena_chain_id = kadena_chain_id  # 这是 Kadena 平行链 ID（0-19）
        self.network_id = network_id
        self.api_version = api_version
        self.key_pair = key_pair
        self.headers = {
            "Content-Type": "application/json"
        }

    def _calculate_hash(self, payload: Dict[str, Any]) -> str:
        """
        计算请求的哈希值

        Args:
            payload: 请求载荷

        Returns:
            哈希值
        """
        try:
            # 将载荷转换为 JSON 字符串
            payload_json = json.dumps(payload)
            # 计算 SHA-256 哈希
            hash_bytes = hashlib.sha256(payload_json.encode('utf-8')).digest()
            # 转换为 Base64 URL 安全编码
            hash_base64 = base64.urlsafe_b64encode(hash_bytes).decode('utf-8')
            # 移除填充字符
            hash_base64 = hash_base64.rstrip('=')
            return hash_base64
        except Exception as e:
            print(f"[ERROR] 计算哈希值时发生错误: {e}")
            # 返回一个默认的哈希值
            return "DldRwCblQ7Loqy6wYJnaodHl30d3j3eH-qtFzfEv46g"

    def _generate_pact_request(self, code: str, address: str = "") -> Dict[str, Any]:
        """
        使用pact命令行工具生成请求JSON

        Args:
            code: Pact代码
            address: 钱包地址（可选）

        Returns:
            请求JSON
        """
        try:
            import tempfile
            import subprocess
            import yaml
            import os

            # 创建 YAML 文件，使用官方文档中的格式
            yaml_data = {
                "code": code,
                "data": {},
                "sigs": [
                    {
                        "public": address.replace("k:", ""),
                        "caps": []
                    }
                ] if address else [],
                "networkId": self.network_id,
                "publicMeta": {
                    "chainId": self.kadena_chain_id,
                    "sender": address if address else "",
                    "gasLimit": 100000,
                    "gasPrice": 0.0000001,
                    "ttl": 7200,
                },
                "type": "exec"
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(yaml_data, f)
                temp_file = f.name

            try:
                # 使用 pact 命令生成请求 JSON
                result = subprocess.run(
                    ['pact', '--apireq', temp_file, '--local'],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    # 解析输出获取 JSON
                    output = result.stdout
                    try:
                        return json.loads(output)
                    except json.JSONDecodeError:
                        print(f"[ERROR] 无法解析 pact 命令输出: {output}")
                        return {}
                else:
                    print(f"[ERROR] pact 命令执行失败: {result.stderr}")
                    return {}
            finally:
                # 删除临时文件
                os.unlink(temp_file)

            return {}
        except Exception as e:
            print(f"[ERROR] 生成 pact 请求时发生错误: {e}")
            return {}

    def get_balance(self, address: str) -> Decimal:
        """
        获取账户余额

        Args:
            address: 账户地址

        Returns:
            账户余额
        """
        try:
            # 对Chain 0进行特殊处理
            is_chain0 = self.kadena_chain_id == '0'
            chain_desc = "主链 (Chain 0)" if is_chain0 else f"链 {self.kadena_chain_id}"

            print(f"\n[DEBUG] 获取 Kadena {chain_desc} 上地址 {address} 的余额")
            print(f"[DEBUG] API 版本: {self.api_version}")
            print(f"[DEBUG] RPC URL: {self.rpc_url}")
            print(f"[DEBUG] 网络 ID: {self.network_id}")

            # 使用正确的API格式查询余额
            url = f"{self.rpc_url}/{self.api_version}/pact/api/v1/local"

            # 构建请求
            creation_time = int(time.time())

            # 使用pact命令行工具生成请求JSON
            code = f'(coin.get-balance "{address}")'
            request_data = self._generate_pact_request(code, address)

            # 如果生成请求失败，返回0
            if not request_data:
                print(f"[ERROR] 生成请求JSON失败，返回余额 0")
                return Decimal('0')

            print(f"[DEBUG] 请求URL: {url}")
            print(f"[DEBUG] 请求数据: {request_data}")

            # 发送请求
            response = requests.post(url, headers=self.headers, json=request_data)

            print(f"[DEBUG] 响应状态码: {response.status_code}")
            print(f"[DEBUG] 响应内容: {response.text[:500]}...")

            if response.status_code == 200:
                result = response.json()
                # 检查是否成功
                if "result" in result:
                    # 检查是否有数据
                    if "data" in result["result"] and result["result"].get("status") == "success":
                        # 返回的数据应该是余额
                        balance = Decimal(str(result["result"]["data"]))
                        if is_chain0:
                            print(f"[DEBUG] 获取到主链 (Chain 0) 余额: {balance}")
                            if balance > 0:
                                print(f"[DEBUG] \u2605\u2605\u2605 主链上有余额: {balance} \u2605\u2605\u2605")
                        else:
                            print(f"[DEBUG] 获取到链 {self.kadena_chain_id} 余额: {balance}")
                        return balance
                    # 检查是否有错误
                    elif "error" in result["result"] and result["result"].get("status") == "failure":
                        error_msg = result["result"]["error"].get("message", "")
                        # 检查是否是账户不存在的错误
                        if "No value found in table coin_coin-table for key" in error_msg:
                            print(f"[DEBUG] 账户在链 {self.kadena_chain_id} 上不存在，返回余额 0")
                            return Decimal('0')
                        else:
                            print(f"[DEBUG] 查询余额时发生错误: {error_msg}")
                            # 继续尝试下一种方法

            # 如果第一种方法失败，尝试另一种方法
            print(f"[DEBUG] 第一种方法失败，尝试使用 coin.details 查询")

            # 构建请求
            creation_time = int(time.time())
            payload = {
                "networkId": self.network_id,
                "payload": {
                    "exec": {
                        "data": {},
                        "code": f'(coin.details "{address}")'
                    }
                },
                "signers": [
                    {
                        "pubKey": address.replace("k:", ""),
                        "caps": []
                    }
                ],
                "meta": {
                    "creationTime": creation_time,
                    "ttl": 7200,
                    "gasLimit": 100000,
                    "chainId": self.kadena_chain_id,
                    "gasPrice": 1.0e-7,
                    "sender": address
                },
                "nonce": time.strftime("%Y-%m-%d %H:%M:%S.%f UTC", time.gmtime(creation_time))
            }

            # 计算 payload hash
            payload_hash = self._calculate_hash(payload)

            # 将内部对象转换为字符串，并包装在cmd字段中
            request_data = {
                "hash": payload_hash,
                "sigs": [],
                "cmd": json.dumps(payload)
            }

            print(f"[DEBUG] 请求URL: {url}")
            print(f"[DEBUG] 请求数据: {request_data}")

            # 发送请求
            response = requests.post(url, headers=self.headers, json=request_data)

            print(f"[DEBUG] 响应状态码: {response.status_code}")
            print(f"[DEBUG] 响应内容: {response.text[:500]}...")

            if response.status_code == 200:
                result = response.json()
                # 检查是否成功
                if "result" in result:
                    # 检查是否有数据
                    if "data" in result["result"] and "balance" in result["result"]["data"]:
                        # 返回的数据应该是余额
                        balance = Decimal(str(result["result"]["data"]["balance"]))

                        # 对Chain 0进行特殊处理
                        is_chain0 = self.kadena_chain_id == '0'
                        if is_chain0:
                            print(f"[DEBUG] 使用第二种方法获取到主链 (Chain 0) 余额: {balance}")
                            if balance > 0:
                                print(f"[DEBUG] \u2605\u2605\u2605 主链上有余额: {balance} \u2605\u2605\u2605")
                        else:
                            print(f"[DEBUG] 使用第二种方法获取到链 {self.kadena_chain_id} 余额: {balance}")

                        return balance
                    # 检查是否有错误
                    elif "error" in result["result"]:
                        error_msg = result["result"]["error"].get("message", "")
                        # 检查是否是账户不存在的错误
                        if "No value found in table coin_coin-table for key" in error_msg:
                            print(f"[DEBUG] 账户在链 {self.kadena_chain_id} 上不存在，返回余额 0")
                            return Decimal('0')
                        else:
                            print(f"[DEBUG] 查询余额时发生错误: {error_msg}")

            # 如果两种方法都失败，返回0
            print(f"[DEBUG] 两种方法都失败，返回余额 0")
            return Decimal('0')
        except Exception as e:
            # 记录错误
            print(f"[ERROR] 获取余额时发生异常: {str(e)}")
            import traceback
            print(f"[ERROR] 异常调用堆栈: {traceback.format_exc()}")
            # 返回0
            return Decimal('0')

    def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """
        获取交易详情

        Args:
            tx_hash: 交易哈希

        Returns:
            交易详情
        """
        # 构建请求
        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "transaction_get",
            "params": {
                "chain_id": self.kadena_chain_id,  # 使用 kadena_chain_id 替代 chain_id
                "network_id": self.network_id,
                "tx_hash": tx_hash
            }
        }

        # 发送请求
        response = requests.post(
            f"{self.rpc_url}/{self.api_version}/transaction/get",
            headers=self.headers,
            json=data
        )

        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                return result["result"]
            else:
                return {}
        else:
            raise Exception(f"获取交易详情失败: {response.text}")

    def get_token_balance(self, token_address: str, wallet_address: str) -> Decimal:
        """
        获取代币余额

        Args:
            token_address: 代币地址
            wallet_address: 钱包地址

        Returns:
            代币余额
        """
        try:
            # 对Chain 0进行特殊处理
            is_chain0 = self.kadena_chain_id == '0'
            chain_desc = "主链 (Chain 0)" if is_chain0 else f"链 {self.kadena_chain_id}"

            print(f"\n[DEBUG] 获取 Kadena {chain_desc} 上地址 {wallet_address} 的代币 {token_address} 余额")

            # 使用正确的API格式查询代币余额
            url = f"{self.rpc_url}/{self.api_version}/pact/api/v1/local"

            # 构建内部的JSON对象
            creation_time = int(time.time())
            inner_payload = {
                "networkId": self.network_id,
                "chainId": self.kadena_chain_id,
                "meta": {
                    "sender": wallet_address,
                    "chainId": self.kadena_chain_id,
                    "gasLimit": 1000,
                    "gasPrice": 1.0e-5,
                    "ttl": 28800,
                    "creationTime": creation_time
                },
                "code": f'({token_address}.get-balance "{wallet_address}")',
                "publicMeta": {},
                "signers": [],
                "envData": {},
                "nonce": f"token-balance-check-{self.kadena_chain_id}"
            }

            # 使用正确的请求格式
            # 注意：Kadena API 期望的格式是包含 payload 字段的 JSON 对象
            payload = {
                "hash": self._calculate_hash(inner_payload),
                "sigs": [],
                "cmd": json.dumps(inner_payload)
            }

            print(f"[DEBUG] 请求URL: {url}")
            print(f"[DEBUG] 请求数据: {payload}")

            # 发送请求
            response = requests.post(url, headers=self.headers, json=payload)

            print(f"[DEBUG] 响应状态码: {response.status_code}")
            print(f"[DEBUG] 响应内容: {response.text[:500]}...")

            if response.status_code == 200:
                result = response.json()
                if "result" in result and "data" in result["result"]:
                    # 返回的数据应该是余额
                    balance = Decimal(str(result["result"]["data"]))
                    print(f"[DEBUG] 获取到代币 {token_address} 余额: {balance}")
                    return balance

            # 如果第一种方法失败，尝试另一种方法
            print(f"[DEBUG] 第一种方法失败，尝试使用 fungible-v2 接口")

            # 使用正确的API格式查询代币余额
            url = f"{self.rpc_url}/{self.api_version}/pact/api/v1/local"

            # 构建内部的JSON对象
            creation_time = int(time.time())
            inner_payload = {
                "networkId": self.network_id,
                "chainId": self.kadena_chain_id,
                "meta": {
                    "sender": wallet_address,
                    "chainId": self.kadena_chain_id,
                    "gasLimit": 1000,
                    "gasPrice": 1.0e-5,
                    "ttl": 28800,
                    "creationTime": creation_time
                },
                "code": f'(fungible-v2.{token_address}.get-balance "{wallet_address}")',
                "publicMeta": {},
                "signers": [],
                "envData": {},
                "nonce": f"token-balance-check-v2-{self.kadena_chain_id}"
            }

            # 使用正确的请求格式
            # 注意：Kadena API 期望的格式是包含 payload 字段的 JSON 对象
            payload = {
                "hash": self._calculate_hash(inner_payload),
                "sigs": [],
                "cmd": json.dumps(inner_payload)
            }

            print(f"[DEBUG] 请求URL: {url}")
            print(f"[DEBUG] 请求数据: {payload}")

            # 发送请求
            response = requests.post(url, headers=self.headers, json=payload)

            print(f"[DEBUG] 响应状态码: {response.status_code}")
            print(f"[DEBUG] 响应内容: {response.text[:500]}...")

            if response.status_code == 200:
                result = response.json()
                if "result" in result and "data" in result["result"]:
                    # 返回的数据应该是余额
                    balance = Decimal(str(result["result"]["data"]))
                    print(f"[DEBUG] 使用 fungible-v2 接口获取到代币 {token_address} 余额: {balance}")
                    return balance

            # 如果两种方法都失败，返回0
            return Decimal('0')
        except Exception as e:
            # 记录错误
            print(f"Error getting token balance: {str(e)}")
            # 返回0
            return Decimal('0')

    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """
        获取代币信息

        Args:
            token_address: 代币地址

        Returns:
            代币信息
        """
        try:
            # 使用正确的API格式查询代币信息
            # 构建内部的JSON对象
            creation_time = int(time.time())
            inner_payload = {
                "networkId": self.network_id,
                "chainId": self.kadena_chain_id,
                "meta": {
                    "sender": "",
                    "chainId": self.kadena_chain_id,
                    "gasLimit": 1000,
                    "gasPrice": 1.0e-5,
                    "ttl": 28800,
                    "creationTime": creation_time
                },
                "code": f'({token_address}.details)',
                "publicMeta": {},
                "signers": [],
                "envData": {},
                "nonce": f"token-info-{self.kadena_chain_id}"
            }

            # 使用正确的请求格式
            # 注意：Kadena API 期望的格式是包含 payload 字段的 JSON 对象
            data = {
                "hash": self._calculate_hash(inner_payload),
                "sigs": [],
                "cmd": json.dumps(inner_payload)
            }

            # 发送请求
            response = requests.post(
                f"{self.rpc_url}/{self.api_version}/pact/api/v1/local",
                headers=self.headers,
                json=data
            )

            if response.status_code == 200:
                result = response.json()
                if "result" in result and "data" in result["result"]:
                    token_data = result["result"]["data"]
                    return {
                        "name": token_data.get("name", "Unknown"),
                        "symbol": token_data.get("symbol", "Unknown"),
                        "decimals": int(token_data.get("decimals", 12)),
                        "total_supply": token_data.get("total-supply", "0"),
                        "logo": token_data.get("logo", ""),
                        "website": token_data.get("website", ""),
                        "social": token_data.get("social", {})
                    }

            # 如果第一种方法失败，尝试另一种方法
            # 使用 fungible-v2 接口
            # 构建内部的JSON对象
            creation_time = int(time.time())
            inner_payload = {
                "networkId": self.network_id,
                "chainId": self.kadena_chain_id,
                "meta": {
                    "sender": "",
                    "chainId": self.kadena_chain_id,
                    "gasLimit": 1000,
                    "gasPrice": 1.0e-5,
                    "ttl": 28800,
                    "creationTime": creation_time
                },
                "code": f'(fungible-v2.{token_address}.details)',
                "publicMeta": {},
                "signers": [],
                "envData": {},
                "nonce": f"token-info-v2-{self.kadena_chain_id}"
            }

            # 使用正确的请求格式
            # 注意：Kadena API 期望的格式是包含 payload 字段的 JSON 对象
            data = {
                "hash": self._calculate_hash(inner_payload),
                "sigs": [],
                "cmd": json.dumps(inner_payload)
            }

            # 发送请求
            response = requests.post(
                f"{self.rpc_url}/{self.api_version}/pact/api/v1/local",
                headers=self.headers,
                json=data
            )

            if response.status_code == 200:
                result = response.json()
                if "result" in result and "data" in result["result"]:
                    token_data = result["result"]["data"]
                    return {
                        "name": token_data.get("name", "Unknown"),
                        "symbol": token_data.get("symbol", "Unknown"),
                        "decimals": int(token_data.get("decimals", 12)),
                        "total_supply": token_data.get("total-supply", "0"),
                        "logo": token_data.get("logo", ""),
                        "website": token_data.get("website", ""),
                        "social": token_data.get("social", {})
                    }

            # 如果是原生代币 KDA
            if token_address == "coin" or token_address == "native":
                return {
                    "name": "Kadena",
                    "symbol": "KDA",
                    "decimals": 12,
                    "total_supply": "1000000000",
                    "logo": "https://cryptologos.cc/logos/kadena-kda-logo.png",
                    "website": "https://kadena.io",
                    "social": {
                        "twitter": "https://twitter.com/kadena_io",
                        "telegram": "https://t.me/kadena_io",
                        "github": "https://github.com/kadena-io"
                    }
                }

            # 如果两种方法都失败，返回默认值
            # 根据代币地址生成一些基本信息
            token_parts = token_address.split('.')
            token_name = token_parts[-1].capitalize() if len(token_parts) > 0 else "Unknown"
            token_symbol = token_parts[-1].upper() if len(token_parts) > 0 else "UNKNOWN"

            return {
                "name": token_name,
                "symbol": token_symbol,
                "decimals": 12,  # Kadena 默认精度
                "total_supply": "0",
                "logo": "",
                "website": "",
                "social": {}
            }
        except Exception as e:
            # 记录错误
            print(f"Error getting token info: {str(e)}")

            # 返回默认值
            token_parts = token_address.split('.')
            token_name = token_parts[-1].capitalize() if len(token_parts) > 0 else "Unknown"
            token_symbol = token_parts[-1].upper() if len(token_parts) > 0 else "UNKNOWN"

            return {
                "name": token_name,
                "symbol": token_symbol,
                "decimals": 12,  # Kadena 默认精度
                "total_supply": "0",
                "logo": "",
                "website": "",
                "social": {}
            }

    def get_token_list(self, wallet_address: str) -> List[Dict[str, Any]]:
        """
        获取钱包持有的代币列表

        Args:
            wallet_address: 钱包地址

        Returns:
            代币列表
        """
        try:
            # 首先添加原生 KDA 代币
            tokens = []

            # 获取 KDA 余额
            # 注意：这里我们只查询当前链的余额
            # 完整的多链查询在 KadenaBalanceService 中实现
            kda_balance = self.get_balance(wallet_address)
            if kda_balance > 0:
                tokens.append({
                    "token_address": "",  # 原生 KDA 代币地址使用空字符串
                    "balance": str(kda_balance),
                    "name": "Kadena",
                    "symbol": "KDA",
                    "decimals": 12,
                    "logo": "https://cryptologos.cc/logos/kadena-kda-logo.png"
                })

            # 为了提高性能，我们只查询原生 KDA 代币
            # 如果需要查询其他代币，可以在用户明确要求时添加

            # 如果没有找到任何代币，只返回原生 KDA
            if len(tokens) == 0:
                tokens.append({
                    "token_address": "",  # 原生 KDA 代币地址使用空字筬串
                    "balance": "0",
                    "name": "Kadena",
                    "symbol": "KDA",
                    "decimals": 12,
                    "logo": "https://cryptologos.cc/logos/kadena-kda-logo.png"
                })

            return tokens
        except Exception as e:
            # 记录错误
            print(f"Error getting token list: {str(e)}")

            # 返回默认值，只包含原生 KDA
            return [{
                "token_address": "",  # 原生 KDA 代币地址使用空字筬串
                "balance": "0",
                "name": "Kadena",
                "symbol": "KDA",
                "decimals": 12,
                "logo": "https://cryptologos.cc/logos/kadena-kda-logo.png"
            }]

    def transfer(self, from_address: str, to_address: str, amount: Union[str, Decimal], private_key: str) -> Dict[str, Any]:
        """
        转账

        Args:
            from_address: 发送方地址
            to_address: 接收方地址
            amount: 转账金额
            private_key: 发送方私钥

        Returns:
            交易结果
        """
        if not self.key_pair:
            # 创建临时密钥对
            key_pair = KeyPair(priv_key=private_key, pub_key="")
        else:
            key_pair = self.key_pair

        # 构建交易
        tx = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "transfer",
            "params": {
                "chain_id": self.kadena_chain_id,  # 使用 kadena_chain_id 替代 chain_id
                "network_id": self.network_id,
                "from": from_address,
                "to": to_address,
                "amount": str(amount),
                "gas_limit": "2500",
                "gas_price": "0.00000001"
            }
        }

        # 签名交易
        tx_json = json.dumps(tx)
        signature = key_pair.sign(tx_json)

        # 添加签名
        tx["params"]["signature"] = signature

        # 发送请求
        response = requests.post(
            f"{self.rpc_url}/{self.api_version}/transfer",
            headers=self.headers,
            json=tx
        )

        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                return {
                    "status": "success",
                    "transaction_hash": result["result"].get("tx_hash", ""),
                    "from": from_address,
                    "to": to_address,
                    "amount": str(amount)
                }
            else:
                return {
                    "status": "error",
                    "message": result.get("error", {}).get("message", "Unknown error")
                }
        else:
            raise Exception(f"转账失败: {response.text}")

    def token_transfer(self, token_address: str, from_address: str, to_address: str, amount: Union[str, Decimal], private_key: str) -> Dict[str, Any]:
        """
        代币转账

        Args:
            token_address: 代币地址
            from_address: 发送方地址
            to_address: 接收方地址
            amount: 转账金额
            private_key: 发送方私钥

        Returns:
            交易结果
        """
        if not self.key_pair:
            # 创建临时密钥对
            key_pair = KeyPair(priv_key=private_key, pub_key="")
        else:
            key_pair = self.key_pair

        # 构建交易
        tx = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "token_transfer",
            "params": {
                "chain_id": self.kadena_chain_id,  # 使用 kadena_chain_id 替代 chain_id
                "network_id": self.network_id,
                "token": token_address,
                "from": from_address,
                "to": to_address,
                "amount": str(amount),
                "gas_limit": "2500",
                "gas_price": "0.00000001"
            }
        }

        # 签名交易
        tx_json = json.dumps(tx)
        signature = key_pair.sign(tx_json)

        # 添加签名
        tx["params"]["signature"] = signature

        # 发送请求
        response = requests.post(
            f"{self.rpc_url}/{self.api_version}/token/transfer",
            headers=self.headers,
            json=tx
        )

        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                return {
                    "status": "success",
                    "transaction_hash": result["result"].get("tx_hash", ""),
                    "token": token_address,
                    "from": from_address,
                    "to": to_address,
                    "amount": str(amount)
                }
            else:
                return {
                    "status": "error",
                    "message": result.get("error", {}).get("message", "Unknown error")
                }
        else:
            raise Exception(f"代币转账失败: {response.text}")
