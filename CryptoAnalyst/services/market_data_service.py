import logging
from .binance_api import BinanceAPI
from .coingecko_api import CoinGeckoAPI
from .coinmarketcap_api import CoinMarketCapAPI
import requests

class MarketDataService:
    def __init__(self):
        self.binance_api = BinanceAPI()
        self.coingecko_api = CoinGeckoAPI()
        self.coinmarketcap_api = CoinMarketCapAPI()
        self.logger = logging.getLogger(__name__)

    def calculate_nupl(self, symbol):
        """计算未实现盈亏(NUPL)
        
        Args:
            symbol: 交易对符号，如'BTCUSDT'
            
        Returns:
            float: NUPL值
        """
        try:
            # 获取200天历史K线数据
            klines = self.binance_api.get_historical_klines(symbol, "1d", "200 days ago UTC")
            if not klines or len(klines) < 200:
                self.logger.warning(f"无法获取{symbol}的足够历史K线数据来计算NUPL")
                return None
                
            # 计算平均成本价
            avg_cost = sum(float(k[4]) for k in klines) / len(klines)
            # 获取当前价格
            current_price = self.binance_api.get_current_price(symbol)
            if not current_price:
                self.logger.warning(f"无法获取{symbol}的当前价格")
                return None
                
            # 计算NUPL
            nupl = (current_price - avg_cost) / avg_cost
            return round(nupl, 4)
            
        except Exception as e:
            self.logger.error(f"计算{symbol}的NUPL时出错: {str(e)}")
            return None

    def calculate_exchange_netflow(self, symbol):
        """计算交易所净流入
        
        Args:
            symbol: 交易对符号，如'BTCUSDT'
            
        Returns:
            float: 净流入量
        """
        try:
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
            symbol: 交易对符号，如'BTCUSDT'
            
        Returns:
            float: 梅耶倍数
        """
        try:
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
            symbol: 交易对符号，如'BTCUSDT'
            
        Returns:
            dict: 包含市场数据的字典
        """
        try:
            # 只获取实时价格
            price = self.binance_api.get_realtime_price(symbol)
            
            if price is None:
                self.logger.warning(f"无法获取{symbol}的价格数据")
                return None
                
            return {'price': price}
            
        except Exception as e:
            self.logger.error(f"获取{symbol}的市场数据时出错: {str(e)}")
            return None 