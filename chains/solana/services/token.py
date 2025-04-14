from typing import Dict, Any, List, Optional
from solana.rpc.api import Client
from solana.rpc.commitment import Commitment
from solana.publickey import PublicKey
from solana.rpc.types import TokenAccountOpts
from decimal import Decimal
from common.config import Config
import requests
import logging
import json
import math
from datetime import datetime, timedelta
from django.core.cache import cache

logger = logging.getLogger(__name__)

class SolanaTokenService:
    """Solana 代币服务"""

    def __init__(self):
        """初始化 Solana RPC 客户端和 Moralis API"""
        config = Config.get_solana_config("SOL")
        self.client = Client(config["rpc_url"])
        self.moralis_api_key = Config.MORALIS_API_KEY
        self.moralis_base_url = "https://solana-gateway.moralis.io"

    def get_token_list(self, wallet_address: str) -> List[Dict[str, Any]]:
        """获取钱包持有的代币列表"""
        try:
            wallet_pubkey = PublicKey(wallet_address)
            response = self.client.get_token_accounts_by_owner(
                wallet_pubkey,
                TokenAccountOpts(program_id=PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
            )

            tokens = []
            for account in response['result']['value']:
                token_info = account['account']['data']['parsed']['info']
                token_mint = token_info['mint']
                token_amount = token_info['tokenAmount']

                # 获取代币元数据
                token_metadata = self.get_token_metadata(token_mint)

                tokens.append({
                    'address': token_mint,
                    'name': token_metadata.get('name', 'Unknown'),
                    'symbol': token_metadata.get('symbol', 'Unknown'),
                    'decimals': token_amount['decimals'],
                    'balance': str(Decimal(token_amount['amount']) / Decimal(10**token_amount['decimals'])),
                    'chain': 'SOL'
                })
            return tokens
        except Exception as e:
            raise Exception(f"获取代币列表失败: {str(e)}")

    def get_token_metadata(self, token_address: str, force_refresh=False) -> Dict[str, Any]:
        """获取代币元数据（使用 Moralis API）"""
        # 检查缓存
        cache_key = f"token_metadata:{token_address}"
        cached_data = None if force_refresh else cache.get(cache_key)

        if cached_data:
            logger.info(f"使用缓存的代币元数据: {token_address}")
            return json.loads(cached_data)

        try:
            # 使用 Moralis API 获取代币元数据
            url = f"{self.moralis_base_url}/token/mainnet/{token_address}/metadata"
            headers = {
                "X-API-Key": self.moralis_api_key,
                "Content-Type": "application/json"
            }

            # 打印请求 URL 和头信息
            print(f"Moralis API 请求 URL: {url}")
            print(f"Moralis API 请求头: {headers}")

            response = requests.get(url, headers=headers)
            print(f"Moralis API 响应状态码: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                # 打印完整的 Moralis API 响应数据
                print(f"Moralis API 响应数据: {json.dumps(data, indent=2)}")

                # 根据官方 Moralis API 响应格式构建元数据
                metadata = {
                    'name': data.get('name', 'Unknown'),
                    'symbol': data.get('symbol', 'Unknown'),
                    'decimals': data.get('decimals', 9),
                    'logo': data.get('logo', None),
                    'description': data.get('description', None),
                    'token_address': token_address,
                    'mint': data.get('mint', token_address),
                    'standard': data.get('standard', None),

                    # 供应量相关
                    'total_supply': data.get('totalSupply', 0),
                    'total_supply_formatted': data.get('totalSupplyFormatted', 0),
                    'fully_diluted_value': data.get('fullyDilutedValue', 0),

                    # Metaplex 相关信息
                    'metaplex': data.get('metaplex', {}),

                    # 社交媒体链接
                    'website': None,
                    'twitter': None,
                    'telegram': None,
                    'discord': None,
                    'moralis': None
                }

                # 处理社交媒体链接
                if 'links' in data and isinstance(data['links'], dict):
                    links = data['links']
                    metadata['website'] = links.get('website', None)
                    metadata['twitter'] = links.get('twitter', None)
                    metadata['telegram'] = links.get('telegram', None)
                    metadata['discord'] = links.get('discord', None)
                    metadata['moralis'] = links.get('moralis', None)

                    # 打印社交媒体链接信息
                    print(f"社交媒体链接信息: {json.dumps(links, indent=2)}")

                # 缓存数据（24小时）
                cache.set(cache_key, json.dumps(metadata), 60 * 60 * 24)

                return metadata

            # 如果 Moralis API 失败，尝试使用 RPC 获取基本元数据
            token_pubkey = PublicKey(token_address)
            rpc_response = self.client.get_token_supply(token_pubkey)
            if rpc_response['result']['value'] is not None:
                metadata = {
                    'name': rpc_response['result']['value'].get('name', 'Unknown'),
                    'symbol': rpc_response['result']['value'].get('symbol', 'Unknown'),
                    'decimals': rpc_response['result']['value'].get('decimals', 9),
                    'token_address': token_address
                }

                # 缓存数据（24小时）
                cache.set(cache_key, json.dumps(metadata), 60 * 60 * 24)

                return metadata

            return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9, 'token_address': token_address}
        except Exception as e:
            logger.error(f"获取代币元数据失败: {str(e)}")
            return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9, 'token_address': token_address}

    def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取特定代币余额"""
        try:
            # 首先获取代币元数据，以获取小数位数
            token_metadata = self.get_token_metadata(token_address)
            decimals = int(token_metadata.get('decimals', 9))

            # 获取代币账户
            token_pubkey = PublicKey(token_address)
            response = self.client.get_token_accounts_by_owner(
                PublicKey(wallet_address),
                TokenAccountOpts(mint=token_pubkey)
            )

            # 打印完整的 RPC 响应数据
            print(f"Solana RPC 代币余额响应数据: {json.dumps(response, indent=2)}")

            # 如果有代币账户
            if response['result']['value'] and len(response['result']['value']) > 0:
                # 获取代币账户地址
                token_account = response['result']['value'][0]['pubkey']

                # 获取代币账户余额
                balance_response = self.client.get_token_account_balance(token_account)
                print(f"Solana RPC 代币账户余额响应数据: {json.dumps(balance_response, indent=2)}")

                if 'result' in balance_response and 'value' in balance_response['result']:
                    token_amount = balance_response['result']['value']
                    # 打印代币余额数据
                    print(f"代币余额数据: {json.dumps(token_amount, indent=2)}")

                    # 计算余额
                    amount = token_amount.get('amount', '0')
                    ui_amount = token_amount.get('uiAmount', 0)

                    # 如果有 uiAmount，直接使用
                    if ui_amount is not None:
                        balance = str(ui_amount)
                    else:
                        # 否则自己计算
                        balance = str(Decimal(amount) / Decimal(10**decimals))

                    return {
                        'balance': balance,
                        'decimals': decimals,
                        'chain': 'SOL',
                        'token_address': token_address,
                        'wallet_address': wallet_address
                    }

            # 如果没有代币账户或获取余额失败，返回 0
            return {
                'balance': '0',
                'decimals': decimals,
                'chain': 'SOL',
                'token_address': token_address,
                'wallet_address': wallet_address
            }
        except Exception as e:
            logger.error(f"获取代币余额失败: {str(e)}")
            return {
                'balance': '0',
                'decimals': 9,  # 默认值
                'chain': 'SOL',
                'token_address': token_address,
                'wallet_address': wallet_address
            }

    def get_token_price_history(self, token_address: str, timeframe: str = '1d', count: int = 7, force_refresh=False) -> Dict[str, Any]:
        """获取代币历史价格（使用 CryptoCompare API）

        参数:
            token_address: 代币地址
            timeframe: 时间间隔，支持 '1s', '10s', '30s', '1min', '5min', '10min', '30min',
                      '1h', '4h', '12h', '1d', '1w', '1M', '1Y'
            count: 返回结果的数量限制
            force_refresh: 是否强制刷新缓存
        """
        # 检查缓存
        cache_key = f"token_price_history:{token_address}:{timeframe}:{count}"
        cached_data = None if force_refresh else cache.get(cache_key)

        if cached_data:
            logger.info(f"使用缓存的代币历史价格数据: {token_address}, timeframe={timeframe}, count={count}")
            return json.loads(cached_data)

        # 将代币地址映射到 CryptoCompare 的交易符号
        token_symbol_map = {
            # SOL 相关
            'sol': 'SOL',
            'solana': 'SOL',
            'So11111111111111111111111111111111111111112': 'SOL',  # Wrapped SOL

            # 其他常见代币
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 'USDC',  # USDC
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 'USDT',  # USDT
            'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263': 'BONK',  # BONK
            'mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So': 'MSOL',  # Marinade Staked SOL
            'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm': 'WIF',   # $WIF (Dogwifhat)
        }

        # 尝试从映射表中获取交易符号
        symbol = token_symbol_map.get(token_address.lower() if token_address.lower() in token_symbol_map else token_address)

        # 如果没有找到映射，尝试获取代币元数据
        if not symbol:
            try:
                # 尝试获取代币元数据
                token_metadata = self.get_token_metadata(token_address)
                if token_metadata and 'symbol' in token_metadata:
                    # 使用代币符号
                    symbol = token_metadata['symbol']
                    logger.info(f"使用代币元数据获取的符号: {token_address} -> {symbol}")
                else:
                    # 如果没有找到代币元数据，使用默认符号
                    symbol = 'SOL'  # 默认使用 SOL
                    logger.warning(f"没有找到代币元数据，使用默认符号: {token_address} -> {symbol}")
            except Exception as e:
                # 如果获取代币元数据失败，使用默认符号
                symbol = 'SOL'  # 默认使用 SOL
                logger.error(f"获取代币元数据失败，使用默认符号: {token_address} -> {symbol}, 错误: {str(e)}")

        try:
            # 使用 CryptoCompare API 获取价格历史
            price_history = self.get_token_price_history_by_symbol(symbol, timeframe, count, force_refresh)

            # 更新代币地址
            price_history['token_address'] = token_address

            # 缓存数据（1小时）
            cache.set(cache_key, json.dumps(price_history), 60 * 60)

            return price_history
        except Exception as e:
            # 如果获取价格历史失败，返回错误信息
            error_message = str(e)
            logger.error(f"获取代币价格历史失败: {token_address} -> {symbol}, 错误: {error_message}")

            # 返回错误信息
            return {
                'token_address': token_address,
                'timeframe': timeframe,
                'count': count,
                'prices': [],
                'error': f"获取代币价格历史失败: {error_message}"
            }


    def get_token_price_history_by_symbol(self, symbol: str, timeframe: str = '1d', count: int = 7, force_refresh=False) -> Dict[str, Any]:
        """使用 CryptoCompare API 获取代币的价格历史

        参数:
            symbol: 代币符号，如 'SOL', 'BTC' 等
            timeframe: 时间间隔，支持 '1s', '10s', '30s', '1min', '5min', '10min', '30min',
                      '1h', '4h', '12h', '1d', '1w', '1M', '1Y'
            count: 返回结果的数量限制
            force_refresh: 是否强制刷新缓存
        """
        # 检查缓存
        cache_key = f"token_price_history_by_symbol:{symbol}:{timeframe}:{count}"
        cached_data = None if force_refresh else cache.get(cache_key)

        if cached_data:
            logger.info(f"使用缓存的代币价格历史数据: symbol={symbol}, timeframe={timeframe}, count={count}")
            return json.loads(cached_data)

        try:
            # 计算时间范围
            end_date = datetime.now()

            # 提取代币符号（去除 -USD 后缀）
            fsym = symbol.split('-')[0] if '-' in symbol else symbol

            # 打印调试信息
            print(f"Getting price history for symbol={symbol}, fsym={fsym}, timeframe={timeframe}, count={count}")

            # 根据不同的时间间隔设置 CryptoCompare API 的参数
            if timeframe in ['1s', '10s', '30s', '1min', '5min', '10min', '30min']:
                # 分钟级数据
                url = "https://min-api.cryptocompare.com/data/v2/histominute"
                limit = min(count, 2000)  # CryptoCompare 的限制是 2000
                date_format = "%Y-%m-%d %H:%M:%S"
            elif timeframe in ['1h', '4h', '12h']:
                # 小时级数据
                url = "https://min-api.cryptocompare.com/data/v2/histohour"
                limit = min(count, 2000)  # CryptoCompare 的限制是 2000
                date_format = "%Y-%m-%d %H:%M:%S"
            else:
                # 天级数据
                url = "https://min-api.cryptocompare.com/data/v2/histoday"
                limit = min(count, 2000)  # CryptoCompare 的限制是 2000
                date_format = "%Y-%m-%d"

            # 设置请求参数
            params = {
                "fsym": fsym,  # 从哪个货币兑换，如 SOL
                "tsym": "USD",  # 兑换成哪个货币，如 USD
                "limit": limit,  # 数据点数量
                "aggregate": 1  # 聚合级别，1 表示不聚合
            }

            # 根据 timeframe 调整 aggregate 参数
            if timeframe == '5min':
                params["aggregate"] = 5
            elif timeframe == '10min':
                params["aggregate"] = 10
            elif timeframe == '30min':
                params["aggregate"] = 30
            elif timeframe == '4h':
                params["aggregate"] = 4
            elif timeframe == '12h':
                params["aggregate"] = 12
            elif timeframe == '1w':
                params["aggregate"] = 7
            elif timeframe == '1M':
                params["aggregate"] = 30

            # 打印请求信息
            print(f"CryptoCompare API 请求 URL: {url}")
            print(f"CryptoCompare API 请求参数: {params}")

            # 发送请求
            response = requests.get(url, params=params)
            print(f"CryptoCompare API 响应状态码: {response.status_code}")

            # 初始化结果对象
            price_history = {
                'symbol': symbol,
                'timeframe': timeframe,
                'count': count,
                'start_date': "",  # 将在处理数据时设置
                'end_date': end_date.strftime(date_format),
                'prices': []
            }

            if response.status_code == 200:
                data = response.json()

                # 打印响应数据结构
                print(f"CryptoCompare API 响应数据结构: {data.get('Response')}")

                if data.get('Response') == 'Success' and 'Data' in data and 'Data' in data['Data']:
                    ohlcv_data = data['Data']['Data']

                    # 如果有数据，设置开始日期
                    if ohlcv_data and len(ohlcv_data) > 0:
                        first_timestamp = ohlcv_data[0]['time']
                        start_date = datetime.fromtimestamp(first_timestamp)
                        price_history['start_date'] = start_date.strftime(date_format)

                    # 处理每个数据点
                    for item in ohlcv_data:
                        timestamp = item['time']
                        date_obj = datetime.fromtimestamp(timestamp)

                        # 根据 timeframe 格式化日期
                        if timeframe in ['1s', '10s', '30s', '1min', '5min', '10min', '30min', '1h', '4h', '12h']:
                            date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            date_str = date_obj.strftime("%Y-%m-%d")

                        # 提取价格数据
                        open_price = item['open']
                        high_price = item['high']
                        low_price = item['low']
                        close_price = item['close']
                        # 交易量数据
                        # volume_from = item['volumefrom']  # 交易量（从货币）
                        volume_to = item['volumeto']  # 交易量（兑换成货币）

                        # 使用收盘价作为价格
                        price = close_price

                        # 计算市值（我们没有市值数据，所以设置为 0）
                        market_cap = 0

                        price_history['prices'].append({
                            'date': date_str,
                            'price_usd': price,
                            'volume_usd': volume_to,  # 使用 volumeto 作为交易量（美元）
                            'market_cap_usd': market_cap,
                            'open_price': open_price,
                            'high_price': high_price,
                            'low_price': low_price
                        })
                else:
                    # 如果没有数据或响应错误
                    error_message = data.get('Message', 'Unknown error')
                    price_history['error'] = f"CryptoCompare API 响应错误: {error_message}"
                    print(f"CryptoCompare API 响应错误: {error_message}")
            else:
                # 如果 API 返回错误，添加错误信息
                price_history['error'] = f"CryptoCompare API 返回状态码: {response.status_code}"
                print(f"CryptoCompare API 请求失败: {response.text}")

            # 缓存数据（1小时）
            cache.set(cache_key, json.dumps(price_history), 60 * 60)

            return price_history
        except Exception as e:
            # 如果发生异常，添加错误信息
            error_message = str(e)
            price_history = {
                'symbol': symbol,
                'timeframe': timeframe,
                'count': count,
                'prices': [],
                'error': f"CryptoCompare API 请求失败: {error_message}"
            }
            print(f"CryptoCompare API 请求失败: {error_message}")

            # 缓存错误数据（10分钟）
            cache.set(cache_key, json.dumps(price_history), 60 * 10)

            return price_history

