import logging
import os
from typing import Optional, Dict
import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class CoinGeckoAPI:
    """CoinGecko API服务类"""
    
    def __init__(self):
        """初始化CoinGecko API客户端"""
        load_dotenv()
        self.api_key = os.getenv('COINGECKO_API_KEY')
        self.base_url = 'https://api.coingecko.com/api/v3'
        self.logger = logging.getLogger(__name__)
        
    def get_token_data(self, token_id: str) -> Optional[Dict]:
        """获取代币数据
        
        Args:
            token_id: 代币ID，例如 'bitcoin'
            
        Returns:
            Dict: 代币数据，如果获取失败则返回None
        """
        try:
            url = f"{self.base_url}/coins/{token_id}"
            params = {'x_cg_demo_api_key': self.api_key} if self.api_key else {}
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.logger.error(f"获取代币数据失败: {str(e)}")
            return None 