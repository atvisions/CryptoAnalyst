from typing import Dict, List, Any
import requests
import logging
from decimal import Decimal
from common.config import Config
from moralis import sol_api
import asyncio
import aiohttp
from datetime import datetime, timedelta
from wallets.models import TokenVisibility, Wallet

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

    async def _get_token_prices(self, token_addresses: List[str]) -> Dict[str, Dict]:
        """批量获取代币价格和24小时变化，使用缓存"""
        from django.core.cache import cache
        import json

        prices = {}
        uncached_tokens = []

        # 检查缓存中是否有数据
        for token_address in token_addresses:
            cache_key = f"token_price:{token_address}"
            cached_data = cache.get(cache_key)

            if cached_data:
                # 使用缓存数据
                prices[token_address] = json.loads(cached_data)
                print(f"使用缓存的代币价格数据: {token_address}")
            else:
                # 记录未缓存的代币
                uncached_tokens.append(token_address)

        # 如果有未缓存的代币，从API获取
        if uncached_tokens:
            print(f"从API获取未缓存的代币价格: {uncached_tokens}")
            api_prices = await self._fetch_token_prices_from_api(uncached_tokens)

            # 更新缓存
            for token_address, price_data in api_prices.items():
                cache_key = f"token_price:{token_address}"
                # 缓存15分钟
                cache.set(cache_key, json.dumps(price_data), 60 * 15)
                prices[token_address] = price_data

        return prices

    async def _fetch_token_prices_from_api(self, token_addresses: List[str]) -> Dict[str, Dict]:
        """从API获取代币价格（原来的_get_token_prices逻辑）"""
        try:
            # 准备请求数据
            payload = {
                "addresses": token_addresses
            }
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": self.api_key
            }

            # 发送批量请求
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/token/mainnet/prices"
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"获取到的价格数据: {data}")  # 添加日志

                        prices = {}
                        for token_data in data:
                            token_address = token_data["tokenAddress"]
                            try:
                                current_price = float(token_data["usdPrice"])
                                price_change_24h = float(token_data["usdPrice24hrPercentChange"]) if token_data.get("usdPrice24hrPercentChange") is not None else 0.0

                                prices[token_address] = {
                                    "current_price": current_price,
                                    "price_change_24h": price_change_24h
                                }
                                print(f"代币 {token_address} 当前价格: {current_price}, 24小时变化: {price_change_24h}%")
                            except (ValueError, TypeError) as e:
                                print(f"处理代币 {token_address} 价格数据时出错: {e}")
                                prices[token_address] = {
                                    "current_price": 0.0,
                                    "price_change_24h": 0.0
                                }
                        return prices
                    else:
                        print(f"获取代币价格失败: {response.status}")
                        return {}

        except Exception as e:
            print(f"获取代币价格时出错: {e}")
            return {}

    def _get_cached_token_price(self, token_address: str) -> Dict:
        """从缓存获取代币价格，如果缓存不存在则从API获取"""
        from django.core.cache import cache
        import json

        cache_key = f"token_price:{token_address}"
        cached_data = cache.get(cache_key)

        if cached_data:
            # 使用缓存数据
            return json.loads(cached_data)
        else:
            # 从API获取并缓存
            price_data = asyncio.run(self._fetch_token_prices_from_api([token_address]))
            if token_address in price_data:
                # 缓存15分钟
                cache.set(cache_key, json.dumps(price_data[token_address]), 60 * 15)
                return price_data[token_address]

        return None

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
        """获取原生 SOL 余额，使用缓存"""
        from django.core.cache import cache
        import json

        cache_key = f"native_balance:{address}"
        cached_data = cache.get(cache_key)

        if cached_data:
            # 使用缓存数据
            print(f"使用缓存的原生代币余额数据: {address}")
            return json.loads(cached_data)

        # 从 API 获取数据
        try:
            data = self._make_moralis_request("/account/mainnet/{address}/balance", {"address": address})
            if not data or 'lamports' not in data:
                logger.warning(f"No balance data found for address {address}")
                balance_data = {
                    "token_address": "native",
                    "symbol": "SOL",
                    "name": "Solana",
                    "balance": "0",
                    "decimals": 9,
                    "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png"
                }
            else:
                # 将 lamports 转换为 SOL
                lamports = Decimal(str(data['lamports']))
                sol_balance = lamports / Decimal('1000000000')
                logger.info(f"SOL balance for {address}: {sol_balance}")

                balance_data = {
                    "token_address": "native",
                    "symbol": "SOL",
                    "name": "Solana",
                    "balance": str(sol_balance),
                    "decimals": 9,
                    "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png"
                }

            # 缓存数据（30秒）
            cache.set(cache_key, json.dumps(balance_data), 30)

            return balance_data
        except Exception as e:
            logger.error(f"Error getting native balance: {e}")
            balance_data = {
                "token_address": "native",
                "symbol": "SOL",
                "name": "Solana",
                "balance": "0",
                "decimals": 9,
                "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png"
            }

            # 缓存错误数据（30秒）
            cache.set(cache_key, json.dumps(balance_data), 30)

            return balance_data

    def get_all_token_balances(self, address: str) -> List[Dict[str, Any]]:
        """获取所有代币余额，使用缓存"""
        from django.core.cache import cache
        import json

        cache_key = f"token_balances:{address}"
        cached_data = cache.get(cache_key)

        if cached_data:
            # 使用缓存数据
            print(f"使用缓存的代币列表数据: {address}")
            return json.loads(cached_data)

        # 从 API 获取数据
        try:
            data = self._make_moralis_request("/account/mainnet/{address}/tokens", {"address": address})
            if not data:
                logger.warning(f"No token data found for address {address}")
                return []

            token_balances = []
            token_addresses = []

            # 首先收集所有代币地址
            for token in data:
                try:
                    # 跳过 NFT（decimals = 0）
                    if int(token.get("decimals", 9)) == 0:
                        continue

                    # 跳过零余额
                    if float(token.get("amount", 0)) == 0:
                        continue

                    token_addresses.append(token["mint"])

                except Exception as e:
                    logger.error(f"Error processing token {token.get('mint', 'unknown')}: {e}")
                    continue

            # 批量获取所有代币价格
            prices = asyncio.run(self._get_token_prices(token_addresses))

            # 处理代币余额
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

                    # 使用批量获取的价格数据
                    if token["mint"] in prices:
                        price_data = prices[token["mint"]]
                        token_info["price_usd"] = str(price_data["current_price"])
                        token_info["price_change_24h"] = str(price_data["price_change_24h"])
                        token_info["value_usd"] = str(float(balance_formatted) * price_data["current_price"])
                    else:
                        token_info["price_usd"] = "0"
                        token_info["price_change_24h"] = "0"
                        token_info["value_usd"] = "0"

                    token_balances.append(token_info)
                    logger.info(f"Added token {token_info['symbol']} with balance {balance_formatted}")

                except Exception as e:
                    logger.error(f"Error processing token {token.get('mint', 'unknown')}: {e}")
                    continue

            # 按价值排序
            token_balances.sort(key=lambda x: float(x.get("value_usd", 0)), reverse=True)
            logger.info(f"Found {len(token_balances)} tokens with non-zero balance")

            # 缓存数据（30秒）
            cache.set(cache_key, json.dumps(token_balances), 30)

            return token_balances

        except Exception as e:
            logger.error(f"Error getting token balances: {e}")
            return []

    def get_all_balances(self, address: str, wallet_id: int = None) -> dict:
        """获取所有代币余额，支持缓存"""
        try:
            # 获取原生 SOL 余额
            native_balance = self.get_native_balance(address)

            # 获取所有代币余额
            token_balances = self.get_all_token_balances(address)

            # 获取隐藏的代币列表（使用缓存）
            hidden_tokens = []

            # 如果提供了钱包ID，尝试使用缓存
            if wallet_id:
                from django.core.cache import cache
                import json

                cache_key = f"token_visibility:{wallet_id}"
                cached_visibility = cache.get(cache_key)

                if cached_visibility:
                    # 使用缓存数据
                    hidden_tokens = json.loads(cached_visibility)
                    print(f"使用缓存的代币可见性数据: {wallet_id}")
                else:
                    # 从数据库获取并缓存
                    hidden_tokens_queryset = TokenVisibility.objects.filter(
                        wallet_id=wallet_id,
                        is_visible=False
                    ).values_list('token_address', flat=True)

                    hidden_tokens = list(hidden_tokens_queryset)
                    # 缓存1小时
                    cache.set(cache_key, json.dumps(hidden_tokens), 60 * 60)
                    print(f"缓存代币可见性数据: {wallet_id}, {hidden_tokens}")
            else:
                # 如果没有钱包ID，直接从数据库获取
                hidden_tokens = list(TokenVisibility.objects.filter(
                    wallet__address=address,
                    is_visible=False
                ).values_list('token_address', flat=True))

            # 过滤掉隐藏的代币
            visible_tokens = [
                token for token in token_balances
                if token['token_address'] not in hidden_tokens
            ]

            # 计算总价值（USD）
            total_value_usd = Decimal('0')
            total_value_change_24h = Decimal('0')

            # 添加原生代币（如果不在隐藏列表中）
            if native_balance and native_balance['token_address'] not in hidden_tokens:
                # 获取 SOL 价格（使用缓存）
                sol_price_data = self._get_cached_token_price("So11111111111111111111111111111111111111112")

                if sol_price_data:
                    price = sol_price_data["current_price"]
                    price_change_24h = sol_price_data["price_change_24h"]
                    native_balance["price_usd"] = str(price)
                    native_balance["price_change_24h"] = str(price_change_24h)
                    native_balance["value_usd"] = str(float(native_balance["balance"]) * price)
                    total_value_usd += Decimal(str(native_balance["value_usd"]))
                    total_value_change_24h += Decimal(str(native_balance["value_usd"])) * Decimal(str(price_change_24h)) / 100
                visible_tokens.append(native_balance)

            # 计算代币总价值
            for token in visible_tokens:
                if token.get('value_usd'):
                    value_usd = Decimal(str(token['value_usd']))
                    price_change = Decimal(str(token.get('price_change_24h', 0)))
                    total_value_usd += value_usd
                    total_value_change_24h += value_usd * price_change / 100

            return {
                'total_value_usd': str(total_value_usd),
                'total_value_change_24h': str(total_value_change_24h),
                'tokens': visible_tokens
            }

        except Exception as e:
            logger.error(f"Error getting all balances: {str(e)}")
            return {
                'total_value_usd': '0',
                'total_value_change_24h': '0',
                'tokens': []
            }