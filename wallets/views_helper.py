"""
辅助函数，用于处理视图中的复杂逻辑
"""
import logging
import requests
from datetime import datetime
from rest_framework.response import Response
from rest_framework import status
from wallets.models import Token, WalletToken

logger = logging.getLogger(__name__)

def get_token_symbol(wallet, token_address):
    """获取代币符号的辅助方法"""
    try:
        token = Token.objects.get(chain__chain=wallet.chain, address=token_address)
        return token.symbol
    except Token.DoesNotExist:
        try:
            wallet_token = WalletToken.objects.get(wallet=wallet, token_address=token_address)
            return wallet_token.symbol
        except WalletToken.DoesNotExist:
            # 如果是 SOL 链，尝试从 API 获取
            if wallet.chain == 'SOL':
                try:
                    from chains.solana.services.token import SolanaTokenService
                    token_service = SolanaTokenService()
                    metadata = token_service.get_token_metadata(token_address)
                    if metadata and 'symbol' in metadata:
                        return metadata['symbol']
                except Exception as e:
                    logger.error(f"Error getting token metadata from API: {str(e)}")
                    raise ValueError(f"获取代币元数据失败: {str(e)}")
            # 如果是 KDA 链，尝试从 API 获取
            elif wallet.chain == 'KDA' or wallet.chain == 'KDA_TESTNET':
                try:
                    from chains.kadena.services.token import KadenaTokenService
                    token_service = KadenaTokenService()
                    metadata = token_service.get_token_metadata(token_address, wallet.chain)
                    if metadata and 'symbol' in metadata:
                        return metadata['symbol']
                except Exception as e:
                    logger.error(f"Error getting token metadata from API: {str(e)}")
                    raise ValueError(f"获取代币元数据失败: {str(e)}")
            # 如果是 EVM 链，尝试从 API 获取
            elif wallet.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO'] or \
                 wallet.chain.startswith('ETH_') or wallet.chain.startswith('BSC_') or wallet.chain.startswith('MATIC_') or \
                 wallet.chain.startswith('ARB_') or wallet.chain.startswith('OP_') or wallet.chain.startswith('AVAX_') or \
                 wallet.chain.startswith('BASE_') or wallet.chain.startswith('ZKSYNC_') or wallet.chain.startswith('LINEA_') or \
                 wallet.chain.startswith('MANTA_') or wallet.chain.startswith('FTM_') or wallet.chain.startswith('CRO_'):
                try:
                    from chains.evm.services.token import EVMTokenService
                    token_service = EVMTokenService(wallet.chain)
                    metadata = token_service.get_token_metadata(token_address)
                    if metadata and 'symbol' in metadata:
                        return metadata['symbol']
                except Exception as e:
                    logger.error(f"Error getting token metadata from API: {str(e)}")
                    raise ValueError(f"获取代币元数据失败: {str(e)}")

            raise ValueError('找不到代币信息')

def get_timeframe_params(timeframe, count_int):
    """根据时间单位获取 API 参数的辅助方法"""
    if timeframe in ['1m', '5m', '15m', '30m']:
        endpoint = 'histominute'
        if timeframe == '1m':
            aggregate = 1
        elif timeframe == '5m':
            aggregate = 5
        elif timeframe == '15m':
            aggregate = 15
        else:  # 30m
            aggregate = 30
    elif timeframe in ['1h', '2h', '4h', '6h', '12h']:
        endpoint = 'histohour'
        if timeframe == '1h':
            aggregate = 1
        elif timeframe == '2h':
            aggregate = 2
        elif timeframe == '4h':
            aggregate = 4
        elif timeframe == '6h':
            aggregate = 6
        else:  # 12h
            aggregate = 12
    else:  # 1d, 3d, 1w, 1M, all
        endpoint = 'histoday'
        if timeframe == '1d':
            aggregate = 1
        elif timeframe == '3d':
            aggregate = 3
        elif timeframe == '1w':
            aggregate = 7
        elif timeframe == '1M':
            aggregate = 30
        else:  # all
            aggregate = 1
            count_int = 2000  # 获取最大数量

    return endpoint, aggregate, count_int

def get_price_from_cryptocompare(symbol, api_key=None):
    """从 CryptoCompare API 获取当前价格的辅助方法"""
    url = f'https://min-api.cryptocompare.com/data/price?fsym={symbol}&tsyms=USD'
    if api_key:
        url += f'&api_key={api_key}'

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(f"获取 {symbol} 价格失败: HTTP 错误 {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"获取 {symbol} 价格失败: {str(e)}")
        return None

def get_price_history_from_cryptocompare(symbol, endpoint, aggregate, count_int, api_key=None):
    """从 CryptoCompare API 获取价格历史的辅助方法"""
    url = f'https://min-api.cryptocompare.com/data/v2/{endpoint}?fsym={symbol}&tsym=USD&limit={count_int}&aggregate={aggregate}'
    if api_key:
        url += f'&api_key={api_key}'

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data['Response'] == 'Success':
            # 处理数据
            price_data = data['Data']['Data']
            result = {
                'symbol': symbol,
                'timeframe': f"{aggregate}{endpoint.replace('histo', '')}",
                'count': len(price_data),
                'prices': []
            }

            for item in price_data:
                timestamp = item['time']
                dt = datetime.fromtimestamp(timestamp)
                result['prices'].append({
                    'timestamp': timestamp,
                    'datetime': dt.isoformat(),
                    'open': item['open'],
                    'high': item['high'],
                    'low': item['low'],
                    'close': item['close'],
                    'volume_from': item['volumefrom'],
                    'volume_to': item['volumeto']
                })
            return result
        else:
            raise ValueError(data.get('Message', '获取价格数据失败'))
    else:
        raise ValueError(f'调用价格 API 失败: {response.status_code}')
