from typing import Dict, Any, List
from solana.rpc.api import Client
from solana.publickey import PublicKey
from solana.rpc.types import TokenAccountOpts
from decimal import Decimal
from common.config import Config
import logging
import requests
import time

class SolanaTokenService:
    """Solana 代币服务"""

    def __init__(self):
        """初始化 Solana RPC 客户端"""
        config = Config.get_solana_config("SOL")
        self.client = Client(config["rpc_url"])

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

    def get_token_metadata(self, token_address_or_symbol: str) -> Dict[str, Any]:
        """获取代币元数据

        参数:
            token_address_or_symbol: 代币地址或符号

        返回:
            代币元数据字典，包含名称、符号、小数位数、logo、描述、网站、社交媒体链接等
        """
        try:
            import logging
            import requests
            from common.config import Config

            logger = logging.getLogger(__name__)

            # 处理特殊符号到地址的映射
            token_address_map = {
                'USDT': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
                'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                'SOL': 'So11111111111111111111111111111111111111112'
            }

            # 如果输入的是符号，尝试将其转换为地址
            token_address = token_address_map.get(token_address_or_symbol, token_address_or_symbol)

            # 如果是 SOL 原生代币或 Bonk 代币，使用预定义的元数据
            if token_address == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
                return {
                    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "standard": "spl",
                    "name": "USD Coin",
                    "symbol": "USDC",
                    "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v/logo.png",
                    "decimals": "6",
                    "links": {
                        "website": "https://www.circle.com/usdc",
                        "twitter": "https://twitter.com/circle"
                    },
                    "description": "USDC is a fully collateralized US dollar stablecoin developed by CENTRE, the open source project with Circle and Coinbase as founding members."
                }
            # SOL 原生代币
            elif token_address == "So11111111111111111111111111111111111111112" or token_address.lower() == "native":
                return {
                    'mint': 'So11111111111111111111111111111111111111112',
                    'standard': 'native',
                    'name': 'Solana',
                    'symbol': 'SOL',
                    'decimals': '9',
                    'logo': 'https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png',
                    'description': 'Solana is a high-performance blockchain supporting builders around the world creating crypto apps that scale today.',
                    'website': 'https://solana.com',
                    'twitter': 'https://twitter.com/solana',
                    'telegram': 'https://t.me/solana',
                    'discord': 'https://discord.com/invite/solana',
                    'links': {
                        'website': 'https://solana.com',
                        'twitter': 'https://twitter.com/solana',
                        'telegram': 'https://t.me/solana',
                        'discord': 'https://discord.com/invite/solana'
                    },
                    'totalSupply': '1000000000000000000',
                    'totalSupplyFormatted': '1000000000',
                    'fullyDilutedValue': '0'
                }

            # 获取 Moralis API 密钥
            moralis_api_key = Config.MORALIS_API_KEY
            logger.info(f"Using Moralis API key: {moralis_api_key[:5]}...{moralis_api_key[-5:] if moralis_api_key else ''}")

            if not moralis_api_key:
                logger.error("Moralis API key is not configured")
                # 如果没有 Moralis API 密钥，尝试使用 RPC 获取基本元数据
                try:
                    token_pubkey = PublicKey(token_address)
                    response = self.client.get_token_supply(token_pubkey)
                    if response['result']['value'] is not None:
                        return {
                            'name': response['result']['value'].get('name', 'Unknown'),
                            'symbol': response['result']['value'].get('symbol', 'Unknown'),
                            'decimals': response['result']['value'].get('decimals', 9)
                        }
                    return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}
                except Exception as e:
                    logger.error(f"Failed to get token metadata from RPC: {e}")
                    return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}

            # 使用 Moralis API 获取代币元数据
            headers = {
                "accept": "application/json",
                "X-API-Key": moralis_api_key
            }

            # 获取代币元数据
            url = f"https://solana-gateway.moralis.io/token/mainnet/{token_address}/metadata"
            logger.info(f"Calling Moralis API: {url}")

            # 添加重试机制
            max_retries = 3
            retry_delay = 2  # 初始重试延迟（秒）
            success = False
            response = None
            logger = logging.getLogger(__name__)

            for retry in range(max_retries):
                try:
                    # 设置超时时间，避免请求无限等待
                    response = requests.get(url, headers=headers, timeout=30)
                    logger.info(f"Moralis API response status: {response.status_code}")

                    if response.status_code == 200:
                        success = True
                        break
                    elif response.status_code == 500:
                        logger.warning(f"Moralis API returned 500 error on attempt {retry+1}/{max_retries}")
                        if retry < max_retries - 1:
                            wait_time = retry_delay * (2 ** retry)  # 指数退避
                            logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                    else:
                        logger.warning(f"Failed to get token metadata from Moralis: {response.status_code}")
                        # 非500错误不重试
                        break
                except requests.exceptions.Timeout:
                    logger.warning(f"Moralis API request timed out on attempt {retry+1}/{max_retries}")
                    if retry < max_retries - 1:
                        wait_time = retry_delay * (2 ** retry)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Error calling Moralis API: {e}")
                    if retry < max_retries - 1:
                        wait_time = retry_delay * (2 ** retry)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}

            # 如果所有重试都失败，或者响应状态码不是200
            if not success or not response or response.status_code != 200:
                logger.warning(f"All attempts to get token metadata from Moralis failed")
                # 尝试使用 RPC 获取基本元数据
                try:
                    token_pubkey = PublicKey(token_address)
                    rpc_response = self.client.get_token_supply(token_pubkey)
                    if rpc_response['result']['value'] is not None:
                        return {
                            'name': rpc_response['result']['value'].get('name', 'Unknown'),
                            'symbol': rpc_response['result']['value'].get('symbol', 'Unknown'),
                            'decimals': rpc_response['result']['value'].get('decimals', 9)
                        }
                    return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}
                except Exception as e:
                    logger.error(f"Failed to get token metadata from RPC: {e}")
                    return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}

            try:
                # 尝试解析 JSON 响应
                try:
                    data = response.json()
                except Exception as json_error:
                    logger.error(f"Error parsing JSON response for token {token_address}: {json_error}")
                    logger.error(f"Response content: {response.content}")
                    return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}

                # 检查响应数据
                if data is None:
                    logger.error(f"Moralis returned None for token {token_address}")
                    return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}

                # 打印响应数据
                logger.info(f"Moralis metadata response for {token_address}: {data}")

                # 直接返回 Moralis API 的原始数据，保留所有字段
                metadata = data

                # 检查元数据是否包含必要的字段
                if 'name' not in metadata or 'symbol' not in metadata or 'decimals' not in metadata:
                    logger.warning(f"Moralis response for token {token_address} is missing required fields")
                    logger.warning(f"Response data: {data}")

                    # 如果缺少必要字段，返回默认值
                    if 'name' not in metadata:
                        metadata['name'] = 'Unknown'
                    if 'symbol' not in metadata:
                        metadata['symbol'] = 'Unknown'
                    if 'decimals' not in metadata:
                        metadata['decimals'] = 9
            except Exception as e:
                logger.error(f"Error processing Moralis response for token {token_address}: {e}")
                return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}

            # 确保元数据中包含基本字段
            if 'name' not in metadata:
                metadata['name'] = ''
            if 'symbol' not in metadata:
                metadata['symbol'] = ''
            if 'decimals' not in metadata:
                metadata['decimals'] = 9
            if 'logo' not in metadata:
                metadata['logo'] = ''
            if 'description' not in metadata:
                metadata['description'] = ''

            # 处理社交媒体链接
            if 'website' not in metadata:
                metadata['website'] = ''
            if 'twitter' not in metadata:
                metadata['twitter'] = ''
            if 'telegram' not in metadata:
                metadata['telegram'] = ''
            if 'discord' not in metadata:
                metadata['discord'] = ''

            # 如果有 links 字段，使用它的值更新社交媒体链接
            if 'links' in data and data['links'] is not None:
                links = data.get('links', {})
                if links:
                    if 'website' in links and links['website']:
                        metadata['website'] = links['website']
                    if 'twitter' in links and links['twitter']:
                        metadata['twitter'] = links['twitter']
                    if 'telegram' in links and links['telegram']:
                        metadata['telegram'] = links['telegram']
                    if 'discord' in links and links['discord']:
                        metadata['discord'] = links['discord']

            # 如果没有 links 字段或者 links 字段中没有某些社交媒体链接，尝试其他方式获取
            # 尝试获取社交媒体链接
            external_url = data.get('external_url', '')
            if external_url and not metadata.get('website'):
                metadata['website'] = external_url

            # 如果有其他外部链接，尝试提取社交媒体链接
            if 'external_link' in data and data['external_link'] and not metadata.get('website'):
                metadata['website'] = data['external_link']

            # 如果有社交媒体链接，尝试提取
            if 'twitter_url' in data and data['twitter_url'] and not metadata.get('twitter'):
                metadata['twitter'] = data['twitter_url']
            elif 'twitter' in data and data['twitter'] and not metadata.get('twitter'):
                metadata['twitter'] = f"https://twitter.com/{data['twitter']}"

            if 'telegram_url' in data and data['telegram_url'] and not metadata.get('telegram'):
                metadata['telegram'] = data['telegram_url']
            elif 'telegram' in data and data['telegram'] and not metadata.get('telegram'):
                metadata['telegram'] = f"https://t.me/{data['telegram']}"

            if 'discord_url' in data and data['discord_url'] and not metadata.get('discord'):
                metadata['discord'] = data['discord_url']
            elif 'discord' in data and data['discord'] and not metadata.get('discord'):
                metadata['discord'] = f"https://discord.com/invite/{data['discord']}"

            # 清理元数据中的特殊字符
            from wallets.utils import sanitize_token_data
            cleaned_metadata = sanitize_token_data(metadata)

            # 打印日志，查看元数据
            logger.info(f"Final metadata for {token_address}: {cleaned_metadata}")

            # 检查元数据中的关键字段
            logger.info(f"Metadata fields for {token_address}:")
            logger.info(f"  name: {cleaned_metadata.get('name', 'N/A')}")
            logger.info(f"  symbol: {cleaned_metadata.get('symbol', 'N/A')}")
            logger.info(f"  decimals: {cleaned_metadata.get('decimals', 'N/A')}")
            logger.info(f"  standard: {cleaned_metadata.get('standard', 'N/A')}")
            logger.info(f"  mint: {cleaned_metadata.get('mint', 'N/A')}")
            logger.info(f"  description: {cleaned_metadata.get('description', 'N/A')[:50] if cleaned_metadata.get('description') else 'N/A'}")
            logger.info(f"  totalSupply: {cleaned_metadata.get('totalSupply', 'N/A')}")
            logger.info(f"  totalSupplyFormatted: {cleaned_metadata.get('totalSupplyFormatted', 'N/A')}")
            logger.info(f"  fullyDilutedValue: {cleaned_metadata.get('fullyDilutedValue', 'N/A')}")

            # 检查 metaplex 字段
            metaplex = cleaned_metadata.get('metaplex', {})
            if metaplex:
                logger.info(f"  metaplex.metadataUri: {metaplex.get('metadataUri', 'N/A')}")
                logger.info(f"  metaplex.masterEdition: {metaplex.get('masterEdition', 'N/A')}")
                logger.info(f"  metaplex.isMutable: {metaplex.get('isMutable', 'N/A')}")
                logger.info(f"  metaplex.sellerFeeBasisPoints: {metaplex.get('sellerFeeBasisPoints', 'N/A')}")
                logger.info(f"  metaplex.updateAuthority: {metaplex.get('updateAuthority', 'N/A')}")
                logger.info(f"  metaplex.primarySaleHappened: {metaplex.get('primarySaleHappened', 'N/A')}")

            # 检查 links 字段
            links = cleaned_metadata.get('links', {})
            if links:
                logger.info(f"  links.website: {links.get('website', 'N/A')}")
                logger.info(f"  links.twitter: {links.get('twitter', 'N/A')}")
                logger.info(f"  links.telegram: {links.get('telegram', 'N/A')}")
                logger.info(f"  links.discord: {links.get('discord', 'N/A')}")

            # 打印元数据类型
            logger.info(f"Metadata type: {type(cleaned_metadata)}")

            # 打印元数据的所有键
            logger.info(f"Metadata keys: {cleaned_metadata.keys() if hasattr(cleaned_metadata, 'keys') else 'Not a dict'}")

            logger.info(f"Successfully retrieved metadata for token {token_address} from Moralis")
            return cleaned_metadata
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token metadata for {token_address_or_symbol}: {e}")
            return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9}

    def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取特定代币余额"""
        try:
            # 注意：这里需要使用钱包地址和代币地址来获取关联的代币账户
            # 然后查询该账户的余额
            logger = logging.getLogger(__name__)

            # 如果是SOL原生代币，使用不同的方法获取余额
            if token_address == "So11111111111111111111111111111111111111112" or token_address.lower() == "native":
                try:
                    wallet_pubkey = PublicKey(wallet_address)
                    response = self.client.get_balance(wallet_pubkey)
                    if response['result']['value'] is not None:
                        balance = response['result']['value']
                        # SOL的小数位是9
                        return {
                            'balance': str(Decimal(balance) / Decimal(10**9)),
                            'decimals': 9,
                            'chain': 'SOL',
                            'token_address': token_address,
                            'wallet_address': wallet_address
                        }
                except Exception as e:
                    logger.error(f"获取SOL原生代币余额失败: {str(e)}")

            # 对于其他代币，需要先找到关联的代币账户
            try:
                wallet_pubkey = PublicKey(wallet_address)
                # 注意：这里不需要使用token_pubkey变量

                # 获取钱包的所有代币账户
                response = self.client.get_token_accounts_by_owner(
                    wallet_pubkey,
                    TokenAccountOpts(program_id=PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
                )

                # 查找匹配的代币账户
                for account in response['result']['value']:
                    account_data = account['account']['data']['parsed']['info']
                    if account_data['mint'] == token_address:
                        token_amount = account_data['tokenAmount']
                        return {
                            'balance': str(Decimal(token_amount['amount']) / Decimal(10**token_amount['decimals'])),
                            'decimals': token_amount['decimals'],
                            'chain': 'SOL',
                            'token_address': token_address,
                            'wallet_address': wallet_address
                        }
            except Exception as e:
                logger.error(f"获取代币账户余额失败: {str(e)}")

            # 如果没有找到匹配的代币账户或发生错误，返回零余额
            return {
                'balance': '0',
                'chain': 'SOL',
                'token_address': token_address,
                'wallet_address': wallet_address
            }
        except Exception as e:
            raise Exception(f"获取代币余额失败: {str(e)}")

    # 删除 get_token_metadata_from_moralis 方法，已将其功能整合到 get_token_metadata 方法中