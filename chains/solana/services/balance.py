from typing import Dict, List, Any
import requests
import logging
from decimal import Decimal
from common.config import Config
from moralis import sol_api
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

class SolanaBalanceService:
    """Solana 余额服务"""
    
    def __init__(self):
        """初始化 Moralis API 客户端"""
        self.api_key = Config.MORALIS_API_KEY
        self.base_url = "https://solana-gateway.moralis.io"
        
    async def _make_async_request(self, session: aiohttp.ClientSession, endpoint: str, params: Dict) -> Dict:
        """异步请求 Moralis API"""
        try:
            url = f"{self.base_url}{endpoint.format(**params)}"
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return {}
        except Exception as e:
            print(f"异步请求出错: {e}")
            return {}
            
    async def _get_token_prices(self, token_addresses: List[str]) -> Dict[str, float]:
        """并发获取代币价格"""
        prices = {}
        async with aiohttp.ClientSession() as session:
            tasks = []
            for token_address in token_addresses:
                endpoint = f"/token/mainnet/{token_address}/price"
                params = {"address": token_address}
                tasks.append(self._make_async_request(session, endpoint, params))
            
            results = await asyncio.gather(*tasks)
            for token_address, result in zip(token_addresses, results):
                if result and "usdPrice" in result:
                    prices[token_address] = float(result["usdPrice"])
                else:
                    prices[token_address] = 0.0
        return prices
        
    def _make_moralis_request(self, endpoint: str, params: Dict = None) -> Dict:
        """向 Moralis API 发送请求"""
        try:
            print(f"正在请求 Moralis API: {endpoint}")
            print(f"请求参数: {params}")
            
            if endpoint == "/account/mainnet/{address}/balance":
                address = params.get("address")
                result = sol_api.account.balance(
                    api_key=self.api_key,
                    params={
                        "network": "mainnet",
                        "address": address
                    }
                )
                print(f"获取 SOL 余额响应: {result}")
                return result
            elif endpoint == "/account/mainnet/{address}/tokens":
                address = params.get("address")
                result = sol_api.account.get_spl(
                    api_key=self.api_key,
                    params={
                        "network": "mainnet",
                        "address": address
                    }
                )
                print(f"获取代币列表响应: {result}")
                return result
            elif endpoint.startswith("/token/mainnet/"):
                token_address = endpoint.split("/")[-2]
                result = sol_api.token.get_token_price(
                    api_key=self.api_key,
                    params={
                        "network": "mainnet",
                        "address": token_address
                    }
                )
                print(f"获取代币价格响应: {result}")
                return result
            else:
                print(f"不支持的端点: {endpoint}")
                return {}
                
        except Exception as e:
            print(f"请求 Moralis API 时出错: {e}")
            return {}

    def get_native_balance(self, address: str) -> Dict[str, Any]:
        """获取原生 SOL 余额"""
        try:
            data = self._make_moralis_request("/account/mainnet/{address}/balance", {"address": address})
            if not data or 'lamports' not in data:
                logger.warning(f"No balance data found for address {address}")
                return {
                    "token_address": "native",
                    "symbol": "SOL",
                    "name": "Solana",
                    "balance": "0",
                    "decimals": 9
                }
                
            # 将 lamports 转换为 SOL
            lamports = Decimal(str(data['lamports']))
            sol_balance = lamports / Decimal('1000000000')
            logger.info(f"SOL balance for {address}: {sol_balance}")
            
            return {
                "token_address": "native",
                "symbol": "SOL",
                "name": "Solana",
                "balance": str(sol_balance),
                "decimals": 9
            }
        except Exception as e:
            logger.error(f"Error getting native balance: {e}")
            return {
                "token_address": "native",
                "symbol": "SOL",
                "name": "Solana",
                "balance": "0",
                "decimals": 9
            }

    def get_all_token_balances(self, address: str) -> List[Dict[str, Any]]:
        """获取所有代币余额"""
        try:
            data = self._make_moralis_request("/account/mainnet/{address}/tokens", {"address": address})
            if not data:
                logger.warning(f"No token data found for address {address}")
                return []
                
            token_balances = []
            
            for token in data:
                try:
                    # 跳过 NFT（decimals = 0）
                    if int(token.get("decimals", 9)) == 0:
                        continue
                        
                    # 跳过零余额
                    if float(token.get("amount", 0)) == 0:
                        continue
                        
                    decimals = int(token.get("decimals", 9))
                    raw_amount = token.get("amount", "0")
                    
                    # 计算格式化后的余额
                    if isinstance(raw_amount, str) and '.' in raw_amount:
                        balance_formatted = raw_amount
                    else:
                        balance = Decimal(str(raw_amount))
                        balance_formatted = str(balance / Decimal(str(10 ** decimals)))
                    
                    if float(balance_formatted) <= 0:
                        continue
                        
                    token_info = {
                        "token_address": token["mint"],
                        "symbol": token.get("symbol", "UNKNOWN"),
                        "name": token.get("name", "Unknown Token"),
                        "logo": token.get("logo", ""),
                        "balance": str(raw_amount),
                        "balance_formatted": balance_formatted,
                        "decimals": decimals
                    }
                    
                    # 获取代币价格
                    price_data = self._make_moralis_request(f"/token/mainnet/{token_info['token_address']}/price", {"address": token_info['token_address']})
                    if price_data and "usdPrice" in price_data:
                        price = float(price_data["usdPrice"])
                        token_info["price_usd"] = str(price)
                        token_info["value_usd"] = str(float(balance_formatted) * price)
                    else:
                        # 如果无法获取价格，设置默认值
                        token_info["price_usd"] = "0"
                        token_info["value_usd"] = "0"
                        
                    token_balances.append(token_info)
                    logger.info(f"Added token {token_info['symbol']} with balance {balance_formatted}")
                    
                except Exception as e:
                    logger.error(f"Error processing token {token.get('mint', 'unknown')}: {e}")
                    continue
                    
            # 按价值排序
            token_balances.sort(key=lambda x: float(x.get("value_usd", 0)), reverse=True)
            logger.info(f"Found {len(token_balances)} tokens with non-zero balance")
            
            return token_balances
            
        except Exception as e:
            logger.error(f"Error getting token balances: {e}")
            return []

    def get_all_balances(self, address: str) -> Dict:
        """获取所有代币余额（包括 SOL）"""
        try:
            print(f"开始获取地址 {address} 的所有代币余额")
            
            # 获取 SOL 余额
            print("正在获取 SOL 余额...")
            sol_data = self._make_moralis_request("/account/mainnet/{address}/balance", {"address": address})
            print(f"SOL 余额原始数据: {sol_data}")
            
            sol_balance = {
                "token_address": "native",
                "symbol": "SOL",
                "name": "Solana",
                "logo": "https://assets.coingecko.com/coins/images/4128/large/solana.png",
                "balance": "0",
                "balance_formatted": "0",
                "decimals": 9,
                "is_native": True
            }
            
            if sol_data and 'lamports' in sol_data:
                lamports = Decimal(str(sol_data['lamports']))
                sol_amount = lamports / Decimal('1000000000')
                sol_balance["balance"] = str(sol_amount)
                sol_balance["balance_formatted"] = str(sol_amount)
                print(f"获取到 SOL 余额: {sol_amount}")
            
            # 获取其他代币余额
            print("正在获取其他代币余额...")
            data = self._make_moralis_request("/account/mainnet/{address}/tokens", {"address": address})
            if not data:
                print(f"未找到地址 {address} 的代币数据")
                return {
                    "total_value_usd": sol_balance.get("value_usd", "0"),
                    "tokens": [sol_balance] if float(sol_balance["balance"]) > 0 else []
                }
                
            token_balances = []
            total_value = 0.0
            
            # 收集所有需要获取价格的代币地址
            token_addresses = []
            if float(sol_balance.get("balance", "0")) > 0:
                token_addresses.append("So11111111111111111111111111111111111111112")
                token_balances.append(sol_balance)
                print(f"添加 SOL 余额到列表: {sol_balance['balance']}")
            
            for token in data:
                try:
                    # 跳过 NFT（decimals = 0）
                    if int(token.get("decimals", 9)) == 0:
                        print(f"跳过 NFT 代币: {token.get('mint', 'unknown')}")
                        continue
                        
                    decimals = int(token.get("decimals", 9))
                    raw_amount = token.get("amount", "0")
                    
                    # 计算格式化后的余额
                    if isinstance(raw_amount, str) and '.' in raw_amount:
                        balance_formatted = raw_amount
                    else:
                        balance = Decimal(str(raw_amount))
                        balance_formatted = str(balance / Decimal(str(10 ** decimals)))
                    
                    print(f"处理代币 {token.get('symbol', 'UNKNOWN')}: 原始余额={raw_amount}, 格式化后={balance_formatted}")
                    
                    # 只要余额大于0就添加
                    if float(balance_formatted) > 0:
                        token_info = {
                            "token_address": token["mint"],
                            "symbol": token.get("symbol", "UNKNOWN"),
                            "name": token.get("name", "Unknown Token"),
                            "logo": token.get("logo", ""),
                            "balance": str(raw_amount),
                            "balance_formatted": balance_formatted,
                            "decimals": decimals,
                            "is_native": False
                        }
                        token_balances.append(token_info)
                        token_addresses.append(token["mint"])
                        print(f"添加代币 {token_info['symbol']} 到列表，余额: {balance_formatted}")
                    
                except Exception as e:
                    print(f"处理代币 {token.get('mint', 'unknown')} 时出错: {e}")
                    continue
            
            # 并发获取所有代币价格
            print("正在并发获取所有代币价格...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            prices = loop.run_until_complete(self._get_token_prices(token_addresses))
            loop.close()
            
            # 更新代币价格和总价值
            for token in token_balances:
                if token["token_address"] == "native":
                    price = prices.get("So11111111111111111111111111111111111111112", 0.0)
                else:
                    price = prices.get(token["token_address"], 0.0)
                
                token["price_usd"] = str(price)
                value = float(token["balance_formatted"]) * price
                token["value_usd"] = str(value)
                total_value += value
                print(f"代币 {token['symbol']} 价格: {price} USD, 总价值: {value} USD")
            
            # 按价值排序
            print("开始按价值排序代币列表")
            token_balances.sort(key=lambda x: float(x.get("value_usd", 0)), reverse=True)
            print(f"找到 {len(token_balances)} 个非零余额的代币")
            
            return {
                "total_value_usd": str(total_value),
                "tokens": token_balances
            }
            
        except Exception as e:
            print(f"获取所有余额时出错: {e}")
            return {
                "total_value_usd": "0",
                "tokens": []
            } 