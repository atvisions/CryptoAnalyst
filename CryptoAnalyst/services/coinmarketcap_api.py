import logging
import os
from typing import Optional, Dict
import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class CoinMarketCapAPI:
    """CoinMarketCap API服务类"""
    
    def __init__(self):
        """初始化CoinMarketCap API客户端"""
        load_dotenv()
        self.api_key = os.getenv('COINMARKETCAP_API_KEY')
        self.base_url = 'https://pro-api.coinmarketcap.com/v1'
        self.logger = logging.getLogger(__name__)
        
    def get_token_data(self, symbol: str) -> Optional[Dict]:
        """获取代币数据
        
        Args:
            symbol: 代币符号，例如 'BTC'
            
        Returns:
            Dict: 代币数据，如果获取失败则返回None
        """
        try:
            url = f"{self.base_url}/cryptocurrency/quotes/latest"
            headers = {'X-CMC_PRO_API_KEY': self.api_key} if self.api_key else {}
            params = {'symbol': symbol}
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.logger.error(f"获取代币数据失败: {str(e)}")
            return None 