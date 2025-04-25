import logging
import os
import requests
from typing import Dict, Optional
from dotenv import load_dotenv
import pandas as pd
from binance.client import Client

logger = logging.getLogger(__name__)

class ChainDataService:
    """链上数据服务类，用于获取链上指标"""
    
    def __init__(self):
        """初始化链上数据服务"""
        load_dotenv()
        self.cryptoquant_api_key = os.getenv('CRYPTOQUANT_API_KEY')
        self.glassnode_api_key = os.getenv('GLASSNODE_API_KEY')
        self.santiment_api_key = os.getenv('SANTIMENT_API_KEY')
        
        # API基础URL
        self.cryptoquant_base_url = 'https://api.cryptoquant.com/v1'
        self.glassnode_base_url = 'https://api.glassnode.com/v1'
        self.santiment_base_url = 'https://api.santiment.net/graphql'
        
        logger.info("链上数据服务初始化完成")
    
    def get_exchange_netflow(self, symbol: str) -> float:
        """获取交易所净流入流出
        
        Args:
            symbol: 交易对符号，例如 'BTC'
            
        Returns:
            float: 交易所净流入流出，如果获取失败则返回0.0
        """
        try:
            # 优先使用CryptoQuant API
            if self.cryptoquant_api_key:
                url = f"{self.cryptoquant_base_url}/btc/exchange-flows"
                headers = {'Authorization': f'Bearer {self.cryptoquant_api_key}'}
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and 'netflow' in data['data']:
                        return float(data['data']['netflow'])
            
            # 如果CryptoQuant失败，尝试Glassnode
            if self.glassnode_api_key:
                url = f"{self.glassnode_base_url}/metrics/market/exchange_net_position_change"
                params = {
                    'a': symbol,
                    'api_key': self.glassnode_api_key
                }
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        return float(data[-1]['v'])  # 返回最新值
            
            # 如果Glassnode失败，尝试Santiment
            if self.santiment_api_key:
                query = """
                {
                    getMetric(metric: "exchange_flow_balance") {
                        timeseriesData(
                            slug: "%s"
                            from: "utc_now-1d"
                            to: "utc_now"
                            interval: "1d"
                        ) {
                            datetime
                            value
                        }
                    }
                }
                """ % symbol.lower()
                
                headers = {
                    'Authorization': f'Apikey {self.santiment_api_key}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(
                    self.santiment_base_url,
                    json={'query': query},
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and 'getMetric' in data['data']:
                        timeseries = data['data']['getMetric']['timeseriesData']
                        if timeseries and len(timeseries) > 0:
                            return float(timeseries[-1]['value'])
            
            logger.warning("无法获取交易所净流入流出数据")
            return 0.0
            
        except Exception as e:
            logger.error(f"获取交易所净流入流出失败: {str(e)}")
            return 0.0
    
    def get_nupl(self, symbol: str) -> float:
        """获取未实现盈亏比率
        
        Args:
            symbol: 交易对符号，例如 'BTC'
            
        Returns:
            float: 未实现盈亏比率，如果获取失败则返回0.0
        """
        try:
            # 获取最近200天的K线数据
            klines = self.binance_client.get_historical_klines(
                symbol=f"{symbol}USDT",
                interval=Client.KLINE_INTERVAL_1DAY,
                limit=200
            )
            
            if not klines or len(klines) < 200:
                self.logger.warning(f"获取{symbol}的K线数据失败或数据不足")
                return 0.0
                
            # 转换为DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'buy_base_volume',
                'buy_quote_volume', 'ignore'
            ])
            
            # 转换数据类型
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
                
            # 计算已实现价格
            df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
            df['volume_price'] = df['typical_price'] * df['volume']
            realized_price = df['volume_price'].sum() / df['volume'].sum()
            
            # 计算当前价格与已实现价格的比率
            current_price = float(df['close'].iloc[-1])
            
            if realized_price == 0:
                self.logger.warning(f"{symbol}的已实现价格为0，无法计算NUPL")
                return 0.0
                
            nupl = (current_price - realized_price) / realized_price * 100
            
            # 限制数值范围在 -100% 到 100% 之间
            nupl = max(min(nupl, 100.0), -100.0)
            
            return round(float(nupl), 2)
            
        except Exception as e:
            self.logger.error(f"计算{symbol}的未实现盈亏比率时发生错误: {str(e)}")
            return 0.0