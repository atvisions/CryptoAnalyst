import logging
from .binance_api import BinanceAPI
from .coingecko_api import CoinGeckoAPI
from .coinmarketcap_api import CoinMarketCapAPI
import requests
import pandas as pd
from binance.client import Client

class MarketDataService:
    def __init__(self):
        self.binance_api = BinanceAPI()
        self.coingecko_api = CoinGeckoAPI()
        self.coinmarketcap_api = CoinMarketCapAPI()
        self.logger = logging.getLogger(__name__)
        self.binance_client = Client()

    def calculate_nupl(self, symbol: str) -> float:
        """计算未实现盈亏比率
        
        Args:
            symbol: 交易对符号
            
        Returns:
            float: 未实现盈亏比率
        """
        try:
            # 获取最近200天的K线数据
            klines = self.binance_client.get_historical_klines(
                symbol=symbol,
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
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
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

    def calculate_exchange_netflow(self, symbol):
        """计算交易所净流入
        
        Args:
            symbol: 交易对符号，如'BTC'
            
        Returns:
            float: 净流入量
        """
        try:
            # 确保符号格式正确
            symbol = self._format_symbol(symbol)
            
            # 获取24小时交易数据
            ticker = self.binance_api.get_ticker(symbol)
            if not ticker:
                self.logger.warning(f"无法获取{symbol}的24小时交易数据")
                return None
                
            # 计算净流入
            buy_volume = float(ticker.get('buyVolume', 0))
            sell_volume = float(ticker.get('sellVolume', 0))
            netflow = buy_volume - sell_volume
            
            # 转换为BTC单位
            current_price = self.binance_api.get_current_price(symbol)
            if current_price:
                netflow_btc = netflow / current_price
                return round(netflow_btc, 4)
            return round(netflow, 4)
            
        except Exception as e:
            self.logger.error(f"计算{symbol}的交易所净流入时出错: {str(e)}")
            return None

    def calculate_mayer_multiple(self, symbol):
        """计算梅耶倍数
        
        Args:
            symbol: 交易对符号，如'BTC'
            
        Returns:
            float: 梅耶倍数
        """
        try:
            # 确保符号格式正确
            symbol = self._format_symbol(symbol)
            
            # 获取200天历史K线数据
            klines = self.binance_api.get_historical_klines(symbol, "1d", "200 days ago UTC")
            if not klines or len(klines) < 200:
                self.logger.warning(f"无法获取{symbol}的足够历史K线数据来计算梅耶倍数")
                return None
                
            # 计算200日移动平均线
            ma200 = sum(float(k[4]) for k in klines) / len(klines)
            # 获取当前价格
            current_price = self.binance_api.get_current_price(symbol)
            if not current_price:
                self.logger.warning(f"无法获取{symbol}的当前价格")
                return None
                
            # 计算梅耶倍数
            mayer_multiple = current_price / ma200
            return round(mayer_multiple, 4)
            
        except Exception as e:
            self.logger.error(f"计算{symbol}的梅耶倍数时出错: {str(e)}")
            return None

    def get_fear_greed_index(self) -> float:
        """获取恐慌贪婪指数
        
        Returns:
            float: 恐慌贪婪指数值
        """
        try:
            # 使用替代API获取恐慌贪婪指数
            url = "https://api.alternative.me/fng/"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data['data']:
                return float(data['data'][0]['value'])
            return 50.0  # 默认值
            
        except Exception as e:
            self.logger.error(f"获取恐慌贪婪指数失败: {str(e)}")
            return 50.0  # 默认值

    def get_market_data(self, symbol):
        """获取市场数据
        
        Args:
            symbol: 代币符号，如'BTC'
            
        Returns:
            dict: 包含市场数据的字典
        """
        try:
            # 确保符号格式正确
            symbol = self._format_symbol(symbol)
            
            # 获取24小时市场数据
            ticker = self.binance_api.get_ticker(symbol)
            if not ticker:
                self.logger.warning(f"无法获取{symbol}的24小时市场数据")
                return None

            # 计算其他市场指标
            nupl = self.calculate_nupl(symbol)
            exchange_netflow = self.calculate_exchange_netflow(symbol)
            mayer_multiple = self.calculate_mayer_multiple(symbol)
            fear_greed_index = self.get_fear_greed_index()
                
            return {
                'price': float(ticker['lastPrice']),
                'volume': float(ticker['volume']),
                'price_change_24h': float(ticker['priceChange']),
                'price_change_percent_24h': float(ticker['priceChangePercent']),
                'high_24h': float(ticker['highPrice']),
                'low_24h': float(ticker['lowPrice']),
                'nupl': nupl if nupl is not None else 0.0,
                'exchange_netflow': exchange_netflow if exchange_netflow is not None else 0.0,
                'mayer_multiple': mayer_multiple if mayer_multiple is not None else 0.0,
                'fear_greed_index': fear_greed_index if fear_greed_index is not None else 50.0,
                'buy_volume': float(ticker.get('buyVolume', 0)),
                'sell_volume': float(ticker.get('sellVolume', 0))
            }
            
        except Exception as e:
            self.logger.error(f"获取{symbol}的市场数据失败: {str(e)}")
            return None

    def _format_symbol(self, symbol):
        """格式化交易对符号
        
        Args:
            symbol: 原始符号，如'BTC'或'BTCUSDT'
            
        Returns:
            str: 格式化后的符号，如'BTCUSDT'
        """
        # 如果符号已经包含USDT，直接返回
        if symbol.endswith('USDT'):
            return symbol
        # 否则添加USDT后缀
        return f"{symbol}USDT" 