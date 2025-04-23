import logging
import os
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import List, Optional, Dict, Union
from dotenv import load_dotenv
from datetime import datetime, timedelta
import requests
from binance.client import AsyncClient
from binance.streams import BinanceSocketManager
import asyncio
import threading
import time
import json
import traceback

logger = logging.getLogger(__name__)

class BinanceAPI:
    """币安API服务类"""
    
    def __init__(self):
        """初始化币安API客户端"""
        load_dotenv()
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            logger.warning("未找到币安API密钥，将使用公共API")
            self.client = Client()
        else:
            self.client = Client(api_key, api_secret)
            
        # 初始化价格缓存
        self.price_cache = {}
        self.price_cache_lock = threading.Lock()
        
        # 启动WebSocket连接
        self.start_websocket()
        
        logger.info("币安API服务初始化完成")
    
    def start_websocket(self):
        """启动WebSocket连接"""
        def run_websocket():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def handle_socket_message(msg):
                try:
                    # 确保消息是字典类型
                    if isinstance(msg, str):
                        msg = json.loads(msg)
                    
                    # 检查消息格式
                    if not isinstance(msg, dict):
                        logger.warning(f"收到非字典类型的消息: {type(msg)}")
                        return
                        
                    if 'e' in msg and msg['e'] == 'error':
                        logger.error(f"WebSocket错误: {msg['m']}")
                        return
                        
                    # 检查必要的字段
                    if 's' not in msg or 'c' not in msg:
                        logger.warning(f"消息缺少必要字段: {msg}")
                        return
                        
                    symbol = msg['s']
                    price = float(msg['c'])
                    
                    with self.price_cache_lock:
                        self.price_cache[symbol] = {
                            'price': price,
                            'timestamp': time.time()
                        }
                        
                except Exception as e:
                    logger.error(f"处理WebSocket消息时出错: {str(e)}")
                    logger.error(f"消息内容: {msg}")
            
            async def main():
                client = await AsyncClient.create()
                bm = BinanceSocketManager(client)
                
                # 订阅所有USDT交易对的价格更新
                async with bm.ticker_socket() as stream:
                    while True:
                        try:
                            msg = await stream.recv()
                            if isinstance(msg, dict) and msg.get('s', '').endswith('USDT'):
                                await handle_socket_message(msg)
                        except Exception as e:
                            logger.error(f"WebSocket接收消息错误: {str(e)}")
                            await asyncio.sleep(5)  # 出错后等待5秒重试
            
            loop.run_until_complete(main())
        
        # 在新线程中运行WebSocket
        websocket_thread = threading.Thread(target=run_websocket, daemon=True)
        websocket_thread.start()
    
    def get_realtime_price(self, symbol: str) -> Optional[float]:
        """
        获取实时价格，优先使用WebSocket缓存
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            
        Returns:
            float: 实时价格，如果获取失败则返回None
        """
        try:
            # 首先检查缓存
            with self.price_cache_lock:
                cached_data = self.price_cache.get(symbol)
                if cached_data and time.time() - cached_data['timestamp'] < 5:  # 5秒内的缓存有效
                    logger.info(f"从缓存获取{symbol}价格: {cached_data['price']}")
                    return cached_data['price']
            
            # 如果缓存无效，使用REST API（带重试机制）
            max_retries = 3
            retry_delay = 1  # 秒
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        logger.info(f"第 {attempt + 1} 次尝试获取{symbol}价格...")
                        time.sleep(retry_delay)
                    
                    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                    response = requests.get(url, timeout=5)  # 增加超时时间到5秒
                    
                    if response.status_code == 200:
                        price = float(response.json()['price'])
                        logger.info(f"成功获取{symbol}价格: {price}")
                        
                        # 更新缓存
                        with self.price_cache_lock:
                            self.price_cache[symbol] = {
                                'price': price,
                                'timestamp': time.time()
                            }
                            
                        return price
                    else:
                        logger.warning(f"获取{symbol}价格失败，状态码: {response.status_code}")
                        logger.warning(f"响应内容: {response.text}")
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"获取{symbol}价格超时")
                    continue
                except requests.exceptions.RequestException as e:
                    logger.warning(f"获取{symbol}价格请求异常: {str(e)}")
                    continue
                except (ValueError, KeyError) as e:
                    logger.warning(f"解析{symbol}价格响应失败: {str(e)}")
                    continue
            
            logger.error(f"获取{symbol}价格失败，重试次数用尽")
            return None
            
        except Exception as e:
            logger.error(f"获取{symbol}实时价格失败: {str(e)}")
            logger.error(f"异常类型: {type(e)}")
            logger.error(f"堆栈跟踪: {traceback.format_exc()}")
            return None
            
    def get_klines(self, symbol: str, interval: str, limit: int = 1000) -> Optional[List]:
        """
        获取K线数据
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            interval: K线间隔，例如 '1d', '4h', '1h'
            limit: 获取的K线数量，默认为1000
            
        Returns:
            List: K线数据列表，如果获取失败则返回None
        """
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            return klines
            
        except BinanceAPIException as e:
            logger.error(f"获取K线数据失败: {str(e)}")
            return None
            
    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        获取永续合约资金费率
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            
        Returns:
            float: 资金费率，如果获取失败则返回None
        """
        try:
            funding_rate = self.client.futures_funding_rate(symbol=symbol)
            return float(funding_rate[0]['fundingRate'])
            
        except BinanceAPIException as e:
            logger.error(f"获取资金费率失败: {str(e)}")
            return None
            
    def get_historical_klines(self, symbol: str, interval: str, start_str: str) -> Optional[List]:
        """
        获取历史K线数据
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            interval: K线间隔，例如 '1d', '4h', '1h'
            start_str: 开始时间，例如 '200 days ago UTC'
            
        Returns:
            List: 历史K线数据列表，如果获取失败则返回None
        """
        try:
            klines = self.client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_str=start_str
            )
            return klines
            
        except BinanceAPIException as e:
            logger.error(f"获取历史K线数据失败: {str(e)}")
            return None
            
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        获取24小时交易数据
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            
        Returns:
            Dict: 24小时交易数据，如果获取失败则返回None
        """
        try:
            ticker = self.client.get_ticker(symbol=symbol)
            # 计算买入和卖出量
            volume = float(ticker['volume'])
            price = float(ticker['lastPrice'])
            buy_volume = volume * (1 + float(ticker['priceChangePercent']) / 100)
            sell_volume = volume - buy_volume
            
            ticker['buyVolume'] = str(buy_volume)
            ticker['sellVolume'] = str(sell_volume)
            return ticker
            
        except BinanceAPIException as e:
            logger.error(f"获取24小时交易数据失败: {str(e)}")
            return None
            
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        获取当前价格
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            
        Returns:
            float: 当前价格，如果获取失败则返回None
        """
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
            
        except BinanceAPIException as e:
            logger.error(f"获取当前价格失败: {str(e)}")
            return None
            
    def get_24h_volume(self, symbol: str) -> Optional[float]:
        """
        获取24小时交易量
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            
        Returns:
            float: 24小时交易量，如果获取失败则返回None
        """
        try:
            ticker = self.client.get_ticker(symbol=symbol)
            return float(ticker['volume'])
            
        except BinanceAPIException as e:
            logger.error(f"获取24小时交易量失败: {str(e)}")
            return None
            
    def get_24h_price_change(self, symbol: str) -> Optional[float]:
        """
        获取24小时价格变化百分比
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            
        Returns:
            float: 24小时价格变化百分比，如果获取失败则返回None
        """
        try:
            ticker = self.client.get_ticker(symbol=symbol)
            return float(ticker['priceChangePercent'])
            
        except BinanceAPIException as e:
            logger.error(f"获取24小时价格变化失败: {str(e)}")
            return None 