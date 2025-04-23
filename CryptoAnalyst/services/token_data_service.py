import logging
import requests
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class TokenDataService:
    """代币数据服务类，用于获取代币的实时数据"""
    
    def __init__(self, api_key: str = None):
        """初始化代币数据服务
        
        Args:
            api_key: CoinGecko API密钥（可选）
        """
        self.api_key = api_key
        self.base_url = "https://api.coingecko.com/api/v3"
        self.headers = {"Accept": "application/json"}
        if api_key:
            self.base_url = "https://pro-api.coingecko.com/api/v3"
            self.headers["x-cg-pro-api-key"] = api_key
        logger.info("代币数据服务初始化完成")
    
    def get_token_data(self, token_id: str) -> Dict:
        """获取代币数据
        
        Args:
            token_id: 代币ID，例如 'bitcoin'
            
        Returns:
            包含代币数据的字典
        """
        try:
            # 获取代币详细信息
            token_info = self._get_token_info(token_id)
            
            # 获取代币市场数据
            market_data = token_info['market_data']
            
            # 获取代币社交媒体数据
            community_data = token_info.get('community_data', {})
            
            # 组合所有数据
            return {
                'symbol': token_info['symbol'].upper(),
                'name': token_info['name'],
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'market_data': {
                    'current_price_usd': market_data['current_price']['usd'],
                    'market_cap_usd': market_data['market_cap']['usd'],
                    'market_cap_rank': market_data['market_cap_rank'],
                    'total_volume_usd': market_data['total_volume']['usd'],
                    'price_change_24h': market_data['price_change_percentage_24h'],
                    'market_cap_change_24h': market_data['market_cap_change_percentage_24h'],
                    'circulating_supply': market_data['circulating_supply'],
                    'total_supply': market_data['total_supply'],
                    'max_supply': market_data['max_supply'],
                    'ath_usd': market_data['ath']['usd'],
                    'ath_date': market_data['ath_date']['usd'],
                    'atl_usd': market_data['atl']['usd'],
                    'atl_date': market_data['atl_date']['usd']
                },
                'social_data': {
                    'twitter_followers': community_data.get('twitter_followers', 0),
                    'reddit_subscribers': community_data.get('reddit_subscribers', 0),
                    'reddit_active_users': community_data.get('reddit_average_posts_48h', 0),
                    'telegram_channel_user_count': community_data.get('telegram_channel_user_count', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"获取代币数据失败: {str(e)}")
            raise
    
    def _get_token_info(self, token_id: str) -> Dict:
        """获取代币详细信息
        
        Args:
            token_id: 代币ID
            
        Returns:
            代币信息字典
        """
        url = f"{self.base_url}/coins/{token_id}"
        params = {
            'localization': 'false',
            'tickers': 'false',
            'market_data': 'true',
            'community_data': 'true',
            'developer_data': 'false',
            'sparkline': 'false'
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def _get_market_data(self, token_id: str) -> Dict:
        """获取代币市场数据
        
        Args:
            token_id: 代币ID
            
        Returns:
            市场数据字典
        """
        url = f"{self.base_url}/coins/{token_id}/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': '1'
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def _get_price_history(self, token_id: str) -> Dict:
        """获取代币价格历史
        
        Args:
            token_id: 代币ID
            
        Returns:
            价格历史字典
        """
        url = f"{self.base_url}/coins/{token_id}/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': '30'
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def _get_social_data(self, token_id: str) -> Dict:
        """获取代币社交媒体数据
        
        Args:
            token_id: 代币ID
            
        Returns:
            社交媒体数据字典
        """
        url = f"{self.base_url}/coins/{token_id}"
        params = {
            'localization': 'false',
            'tickers': 'false',
            'market_data': 'false',
            'community_data': 'true',
            'developer_data': 'false',
            'sparkline': 'false'
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()['community_data'] 