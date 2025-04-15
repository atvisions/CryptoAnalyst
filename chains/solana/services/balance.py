from typing import Dict, List, Any
import requests
import logging
from decimal import Decimal
from common.config import Config
from moralis import sol_api
import asyncio
import aiohttp
from datetime import datetime, timedelta
from wallets.models import WalletToken, Wallet

logger = logging.getLogger(__name__)

class SolanaBalanceService:
    """Solana 余额服务"""

    def __init__(self):
        """初始化 Moralis API 客户端"""
        self.api_key = Config.MORALIS_API_KEY
        config = Config.get_solana_config("SOL")
        self.base_url = config["moralis_url"]

    async def _make_async_request(self, session: aiohttp.ClientSession, endpoint: str, params: Dict) -> Dict:
        """异步请求 Moralis API"""
        try:
            url = f"{self.base_url}{endpoint.format(**params)}"
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return {}
        except Exception as e:
            print(f"异步请求出错: {e}")
            return {}

    async def _get_token_prices(self, token_addresses: List[str]) -> Dict[str, Dict]:
        """批量获取代币价格和24小时变化，使用分批处理避免请求过大"""
        try:
            # 设置每批处理的代币数量，减小批次大小
            batch_size = 20  # 从50减小到20
            all_prices = {}
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": self.api_key
            }

            # 分批处理代币地址
            for i in range(0, len(token_addresses), batch_size):
                batch = token_addresses[i:i+batch_size]
                batch_num = i//batch_size + 1
                total_batches = (len(token_addresses) + batch_size - 1)//batch_size
                logger.info(f"处理代币价格批次 {batch_num}/{total_batches}，包含 {len(batch)} 个代币")

                # 准备请求数据
                payload = {
                    "addresses": batch
                }

                # 添加重试机制
                max_retries = 3
                retry_delay = 2  # 重试间隔时间（秒）
                success = False

                for retry in range(max_retries):
                    try:
                        # 发送批量请求
                        async with aiohttp.ClientSession() as session:
                            url = f"{self.base_url}/token/mainnet/prices"
                            # 增加超时设置
                            async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    logger.info(f"成功获取批次 {batch_num} 的价格数据，共 {len(data)} 条记录")

                                    for token_data in data:
                                        token_address = token_data["tokenAddress"]
                                        try:
                                            current_price = float(token_data["usdPrice"])
                                            price_change_24h = float(token_data["usdPrice24hrPercentChange"]) if token_data.get("usdPrice24hrPercentChange") is not None else 0.0

                                            all_prices[token_address] = {
                                                "current_price": current_price,
                                                "price_change_24h": price_change_24h
                                            }
                                            logger.debug(f"代币 {token_address} 当前价格: {current_price}, 24小时变化: {price_change_24h}%")
                                        except (ValueError, TypeError) as e:
                                            logger.error(f"处理代币 {token_address} 价格数据时出错: {e}")
                                            all_prices[token_address] = {
                                                "current_price": 0.0,
                                                "price_change_24h": 0.0
                                            }
                                    success = True
                                    break  # 成功获取数据，跳出重试循环
                                else:
                                    error_text = await response.text()
                                    logger.error(f"获取代币价格批次 {batch_num} 失败: {response.status}, 错误信息: {error_text}")
                                    if retry < max_retries - 1:  # 如果还有重试机会
                                        logger.info(f"将在 {retry_delay} 秒后重试（第 {retry+1} 次）")
                                        await asyncio.sleep(retry_delay)
                                        retry_delay *= 2  # 指数退避策略
                    except Exception as e:
                        logger.error(f"处理批次 {batch_num} 时发生异常: {str(e)}")
                        if retry < max_retries - 1:  # 如果还有重试机会
                            logger.info(f"将在 {retry_delay} 秒后重试（第 {retry+1} 次）")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避策略

                if not success:
                    logger.warning(f"批次 {batch_num} 在多次重试后仍然失败，跳过该批次")

                # 增加批次间的等待时间，避免API限制
                await asyncio.sleep(1.5)  # 从0.5秒增加到1.5秒

            logger.info(f"完成所有代币价格获取，共处理 {len(all_prices)} 个代币")
            return all_prices

        except Exception as e:
            logger.error(f"获取代币价格时出错: {e}")
            return {}

    def _make_moralis_request(self, endpoint: str, params: Dict = None) -> Dict:
        """向 Moralis API 发送请求"""
        try:
            print(f"正在请求 Moralis API: {endpoint}")
            print(f"请求参数: {params}")

            if endpoint == "/account/mainnet/{address}/balance":
                address = params.get("address")
                result = sol_api.account.balance(
                    api_key=self.api_key,
                    params={
                        "network": "mainnet",
                        "address": address
                    }
                )
                print(f"获取 SOL 余额响应: {result}")
                return result
            elif endpoint == "/account/mainnet/{address}/tokens":
                address = params.get("address")
                result = sol_api.account.get_spl(
                    api_key=self.api_key,
                    params={
                        "network": "mainnet",
                        "address": address
                    }
                )
                print(f"获取代币列表响应: {result}")
                return result
            elif endpoint.startswith("/token/mainnet/"):
                token_address = endpoint.split("/")[-2]
                result = sol_api.token.get_token_price(
                    api_key=self.api_key,
                    params={
                        "network": "mainnet",
                        "address": token_address
                    }
                )
                print(f"获取代币价格响应: {result}")
                return result
            else:
                print(f"不支持的端点: {endpoint}")
                return {}

        except Exception as e:
            print(f"请求 Moralis API 时出错: {e}")
            return {}

    def get_native_balance(self, address: str, wallet_id: int = None) -> Dict[str, Any]:
        """获取原生 SOL 余额并更新数据库"""
        try:
            data = self._make_moralis_request("/account/mainnet/{address}/balance", {"address": address})
            if not data or 'lamports' not in data:
                logger.warning(f"No balance data found for address {address}")
                return {
                    "token_address": "native",
                    "symbol": "SOL",
                    "name": "Solana",
                    "balance": "0",
                    "decimals": 9,
                    "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png"
                }

            # 将 lamports 转换为 SOL
            lamports = Decimal(str(data['lamports']))
            sol_balance = lamports / Decimal('1000000000')
            logger.info(f"SOL balance for {address}: {sol_balance}")

            # 如果提供了 wallet_id，更新数据库
            if wallet_id:
                try:
                    from wallets.models import Chain, Token, Wallet, WalletToken
                    wallet = Wallet.objects.get(id=wallet_id)

                    # 获取或创建 SOL 代币的 Token 记录
                    chain_obj = Chain.objects.get(chain='SOL')
                    token_obj = Token.objects.filter(chain=chain_obj, address="So11111111111111111111111111111111111111112").first()

                    # 获取 SOL 价格
                    try:
                        # 尝试使用 CryptoCompare API 获取 SOL 价格
                        import requests
                        response = requests.get(f"{Config.CRYPTOCOMPARE_API_URL}?fsym=SOL&tsyms=USD")
                        if response.status_code == 200:
                            data = response.json()
                            current_price_usd = data.get('USD', 0)

                            # 获取 24 小时价格变化
                            response_24h = requests.get("https://min-api.cryptocompare.com/data/v2/histohour?fsym=SOL&tsym=USD&limit=24")
                            if response_24h.status_code == 200:
                                data_24h = response_24h.json()
                                if data_24h.get('Response') == 'Success' and data_24h.get('Data') and data_24h['Data'].get('Data'):
                                    price_24h_ago = data_24h['Data']['Data'][0]['close']
                                    if price_24h_ago > 0:
                                        price_change_24h = ((current_price_usd - price_24h_ago) / price_24h_ago) * 100
                                    else:
                                        price_change_24h = 0
                                else:
                                    price_change_24h = 0
                            else:
                                price_change_24h = 0
                        else:
                            # 如果 CryptoCompare 失败，尝试 CoinGecko
                            response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true")
                            if response.status_code == 200:
                                data = response.json()
                                sol_price = data.get('solana', {})
                                current_price_usd = sol_price.get('usd', 0)
                                price_change_24h = sol_price.get('usd_24h_change', 0)
                            else:
                                current_price_usd = 0
                                price_change_24h = 0
                    except Exception as e:
                        logger.error(f"Error getting SOL price: {e}")
                        current_price_usd = 0
                        price_change_24h = 0

                    logger.info(f"SOL price: {current_price_usd}, 24h change: {price_change_24h}%")

                    if not token_obj:
                        # 创建新的 Token 记录
                        token_obj = Token.objects.create(
                            chain=chain_obj,
                            address="So11111111111111111111111111111111111111112",  # SOL 的合约地址
                            symbol='SOL',
                            name='Solana',
                            decimals=9,
                            logo_url='https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png',
                            current_price_usd=current_price_usd,
                            price_change_24h=price_change_24h
                        )
                        logger.info("Created new Token record for SOL")

                        # 使用 token.py 中的方法获取 SOL 详细元数据
                        try:
                            from chains.solana.services.token import SolanaTokenService
                            token_service = SolanaTokenService()
                            metadata = token_service.get_token_metadata("So11111111111111111111111111111111111111112")

                            if metadata:
                                # 更新基本元数据
                                token_obj.description = metadata.get('description', '')
                                token_obj.website = metadata.get('website', '')
                                token_obj.twitter = metadata.get('twitter', '')
                                token_obj.telegram = metadata.get('telegram', '')
                                token_obj.discord = metadata.get('discord', '')

                                # 更新供应信息
                                if 'totalSupply' in metadata:
                                    try:
                                        token_obj.total_supply = metadata.get('totalSupply', 0)
                                    except Exception as e:
                                        logger.error(f"Error setting total_supply: {e}")
                                        # 尝试将字符串转换为数字
                                        try:
                                            token_obj.total_supply = float(metadata.get('totalSupply', 0))
                                        except:
                                            token_obj.total_supply = 0

                                if 'totalSupplyFormatted' in metadata:
                                    token_obj.total_supply_formatted = str(metadata.get('totalSupplyFormatted', ''))

                                if 'fullyDilutedValue' in metadata:
                                    try:
                                        token_obj.fully_diluted_value = metadata.get('fullyDilutedValue', 0)
                                    except Exception as e:
                                        logger.error(f"Error setting fully_diluted_value: {e}")
                                        # 尝试将字符串转换为数字
                                        try:
                                            token_obj.fully_diluted_value = float(metadata.get('fullyDilutedValue', 0))
                                        except:
                                            token_obj.fully_diluted_value = 0

                                # 更新标准信息
                                if 'standard' in metadata:
                                    token_obj.standard = metadata.get('standard', '')
                                if 'mint' in metadata:
                                    token_obj.mint = metadata.get('mint', '')

                                # 更新 Metaplex 元数据
                                metaplex = metadata.get('metaplex', {})
                                if metaplex:
                                    if 'metadataUri' in metaplex:
                                        token_obj.metadata_uri = metaplex.get('metadataUri', '')
                                    if 'masterEdition' in metaplex:
                                        token_obj.is_master_edition = metaplex.get('masterEdition', False)
                                    if 'isMutable' in metaplex:
                                        token_obj.is_mutable = metaplex.get('isMutable', True)
                                    if 'sellerFeeBasisPoints' in metaplex:
                                        token_obj.seller_fee_basis_points = metaplex.get('sellerFeeBasisPoints', 0)
                                    if 'updateAuthority' in metaplex:
                                        token_obj.update_authority = metaplex.get('updateAuthority', '')
                                    if 'primarySaleHappened' in metaplex:
                                        # primarySaleHappened 可能是数字或布尔值
                                        primary_sale = metaplex.get('primarySaleHappened', 0)
                                        if isinstance(primary_sale, bool):
                                            token_obj.primary_sale_happened = primary_sale
                                        else:
                                            token_obj.primary_sale_happened = bool(primary_sale)

                                token_obj.save()
                                logger.info("Updated SOL token metadata")
                        except Exception as e:
                            logger.error(f"Error getting SOL metadata: {e}")
                    else:
                        # 更新现有 Token 记录
                        token_obj.current_price_usd = current_price_usd
                        token_obj.price_change_24h = price_change_24h
                        token_obj.save()
                        logger.info("Updated Token record for SOL")

                        # 强制更新 SOL 代币的元数据
                        # 如果元数据为空或者强制更新
                        if True:  # 始终更新元数据
                            try:
                                from chains.solana.services.token import SolanaTokenService
                                token_service = SolanaTokenService()
                                metadata = token_service.get_token_metadata("So11111111111111111111111111111111111111112")

                                if metadata:
                                    # 更新基本元数据
                                    token_obj.description = metadata.get('description', '')
                                    token_obj.website = metadata.get('website', '')
                                    token_obj.twitter = metadata.get('twitter', '')
                                    token_obj.telegram = metadata.get('telegram', '')
                                    token_obj.discord = metadata.get('discord', '')

                                    # 更新供应信息
                                    if 'totalSupply' in metadata:
                                        token_obj.total_supply = metadata.get('totalSupply', 0)
                                    if 'totalSupplyFormatted' in metadata:
                                        token_obj.total_supply_formatted = metadata.get('totalSupplyFormatted', '')
                                    if 'fullyDilutedValue' in metadata:
                                        token_obj.fully_diluted_value = metadata.get('fullyDilutedValue', 0)

                                    # 更新标准信息
                                    if 'standard' in metadata:
                                        token_obj.standard = metadata.get('standard', '')
                                    if 'mint' in metadata:
                                        token_obj.mint = metadata.get('mint', '')

                                    token_obj.save()
                                    logger.info("Updated SOL token metadata")
                            except Exception as e:
                                logger.error(f"Error getting SOL metadata: {e}")

                    # 更新或创建 WalletToken 记录
                    wallet_token, created = WalletToken.objects.update_or_create(
                        wallet=wallet,
                        token_address="So11111111111111111111111111111111111111112",
                        defaults={
                            'token': token_obj,
                            'balance': str(lamports),
                            'balance_formatted': str(sol_balance),
                            'is_visible': True
                        }
                    )

                    if created:
                        logger.info(f"Created new WalletToken record for SOL")
                    else:
                        logger.info(f"Updated WalletToken record for SOL")

                except Exception as e:
                    logger.error(f"Error updating database for SOL: {e}")

            return {
                "token_address": "native",
                "symbol": "SOL",
                "name": "Solana",
                "balance": str(sol_balance),
                "balance_formatted": str(sol_balance),
                "decimals": 9,
                "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png",
                "current_price_usd": current_price_usd,
                "price_change_24h": price_change_24h
            }
        except Exception as e:
            logger.error(f"Error getting native balance: {e}")
            return {
                "token_address": "native",
                "symbol": "SOL",
                "name": "Solana",
                "balance": "0",
                "balance_formatted": "0",
                "decimals": 9,
                "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png",
                "current_price_usd": 0,
                "price_change_24h": 0
            }

    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """获取代币信息"""
        try:
            # 使用 Moralis API 获取代币信息
            data = self._make_moralis_request("/token/mainnet/{address}", {"address": token_address})
            if not data:
                logger.warning(f"No token info found for address {token_address}")
                return {}

            return {
                'symbol': data.get('symbol', ''),
                'name': data.get('name', ''),
                'logo': data.get('logo', ''),
                'decimals': data.get('decimals', 9)
            }
        except Exception as e:
            logger.error(f"Error getting token info: {e}")
            return {}

    def get_all_token_balances(self, address: str, wallet_id: int = None) -> List[Dict[str, Any]]:
        """获取所有代币余额并更新数据库"""
        try:
            logger.info(f"Getting all token balances for address {address}")
            data = self._make_moralis_request("/account/mainnet/{address}/tokens", {"address": address})
            if not data:
                logger.warning(f"No token data found for address {address}")
                return []

            token_balances = []
            token_addresses = []

            # 首先收集所有代币地址
            total_tokens = len(data)
            logger.info(f"Processing {total_tokens} tokens for address {address}")

            for index, token in enumerate(data):
                try:
                    # 跳过 NFT（decimals = 0）
                    if int(token.get("decimals", 9)) == 0:
                        continue

                    # 跳过零余额
                    if float(token.get("amount", 0)) == 0:
                        continue

                    token_addresses.append(token["mint"])

                except Exception as e:
                    logger.error(f"Error processing token {token.get('mint', 'unknown')}: {e}")
                    continue

            # 批量获取所有代币价格
            prices = asyncio.run(self._get_token_prices(token_addresses))

            # 处理代币余额
            logger.info(f"Starting to process token balances for {total_tokens} tokens")

            for index, token in enumerate(data):
                logger.info(f"Processing token balance {index+1}/{total_tokens}: {token.get('mint', 'unknown')}")
                try:
                    # 跳过 NFT（decimals = 0）
                    if int(token.get("decimals", 9)) == 0:
                        continue

                    # 跳过零余额
                    if float(token.get("amount", 0)) == 0:
                        continue

                    decimals = int(token.get("decimals", 9))
                    raw_amount = token.get("amount", "0")

                    # 计算格式化后的余额
                    if isinstance(raw_amount, str) and '.' in raw_amount:
                        balance_formatted = raw_amount
                    else:
                        balance = Decimal(str(raw_amount))
                        balance_formatted = str(balance / Decimal(str(10 ** decimals)))

                    if float(balance_formatted) <= 0:
                        continue

                    token_info = {
                        "token_address": token["mint"],
                        "symbol": token.get("symbol", "UNKNOWN"),
                        "name": token.get("name", "Unknown Token"),
                        "logo": token.get("logo", ""),
                        "balance": str(raw_amount),
                        "balance_formatted": balance_formatted,
                        "decimals": decimals
                    }

                    # 使用批量获取的价格数据
                    if token["mint"] in prices:
                        price_data = prices[token["mint"]]
                        token_info["price_usd"] = str(price_data["current_price"])
                        token_info["price_change_24h"] = str(price_data["price_change_24h"])
                        token_info["value_usd"] = str(float(balance_formatted) * price_data["current_price"])
                    else:
                        token_info["price_usd"] = "0"
                        token_info["price_change_24h"] = "0"
                        token_info["value_usd"] = "0"

                    token_balances.append(token_info)
                    logger.info(f"Added token {token_info['symbol']} with balance {balance_formatted}")

                    # 如果提供了 wallet_id，更新数据库
                    if wallet_id:
                        try:
                            wallet = Wallet.objects.get(id=wallet_id)

                            # 尝试获取或创建 Token 对象
                            token_obj = None
                            try:
                                from wallets.models import Chain, Token
                                chain_obj = Chain.objects.get(chain='SOL')
                                token_obj = Token.objects.filter(chain=chain_obj, address=token["mint"]).first()

                                # 如果 Token 对象不存在，创建它
                                if not token_obj:
                                    # 获取代币价格信息
                                    price_data = prices.get(token["mint"], {})
                                    current_price_usd = price_data.get("current_price", 0)
                                    price_change_24h = price_data.get("price_change_24h", 0)

                                    # 清理代币数据中的特殊字符
                                    from wallets.utils import sanitize_token_data
                                    cleaned_token = sanitize_token_data(token)

                                    # 创建新的 Token 对象
                                    token_obj = Token.objects.create(
                                        chain=chain_obj,
                                        address=cleaned_token["mint"],
                                        symbol=cleaned_token.get("symbol", ""),
                                        name=cleaned_token.get("name", ""),
                                        decimals=cleaned_token.get("decimals", 9),
                                        logo_url=cleaned_token.get("logo", ""),
                                        current_price_usd=current_price_usd,
                                        price_change_24h=price_change_24h
                                    )
                                    logger.info(f"Created new Token record for {token.get('symbol', '')}: {token['mint']}")

                                    # 使用 token.py 中的方法获取代币详细元数据
                                    try:
                                        from chains.solana.services.token import SolanaTokenService
                                        token_service = SolanaTokenService()

                                        # 如果是 Bonk 代币，打印详细日志
                                        if token["mint"] == "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263":
                                            logger.info(f"Processing Bonk token: {token}")
                                            logger.info(f"Bonk token details: name={token.get('name', 'N/A')}, symbol={token.get('symbol', 'N/A')}, decimals={token.get('decimals', 'N/A')}")

                                            # 检查数据库中是否已存在 Bonk 代币
                                            existing_bonk = Token.objects.filter(address="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263").first()
                                            if existing_bonk:
                                                logger.info(f"Existing Bonk token in database: {existing_bonk.__dict__}")
                                            else:
                                                logger.info("Bonk token not found in database")

                                        metadata = token_service.get_token_metadata(token["mint"])

                                        # 如果是 Bonk 代币，打印获取到的元数据
                                        if token["mint"] == "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263":
                                            logger.info(f"Bonk metadata from Moralis: {metadata}")

                                        if metadata:
                                            # 更新基本元数据
                                            token_obj.description = metadata.get('description', '')
                                            token_obj.website = metadata.get('website', '')
                                            token_obj.twitter = metadata.get('twitter', '')
                                            token_obj.telegram = metadata.get('telegram', '')
                                            token_obj.discord = metadata.get('discord', '')

                                            # 更新供应信息
                                            if 'totalSupply' in metadata:
                                                token_obj.total_supply = metadata.get('totalSupply', 0)
                                            if 'totalSupplyFormatted' in metadata:
                                                token_obj.total_supply_formatted = metadata.get('totalSupplyFormatted', '')
                                            if 'fullyDilutedValue' in metadata:
                                                token_obj.fully_diluted_value = metadata.get('fullyDilutedValue', 0)

                                            # 更新标准信息
                                            if 'standard' in metadata:
                                                token_obj.standard = metadata.get('standard', '')
                                            if 'mint' in metadata:
                                                token_obj.mint = metadata.get('mint', '')

                                            # 更新 Metaplex 元数据
                                            metaplex = metadata.get('metaplex', {})
                                            if metaplex:
                                                if 'metadataUri' in metaplex:
                                                    token_obj.metadata_uri = metaplex.get('metadataUri', '')
                                                if 'masterEdition' in metaplex:
                                                    token_obj.is_master_edition = metaplex.get('masterEdition', False)
                                                if 'isMutable' in metaplex:
                                                    token_obj.is_mutable = metaplex.get('isMutable', True)
                                                if 'sellerFeeBasisPoints' in metaplex:
                                                    token_obj.seller_fee_basis_points = metaplex.get('sellerFeeBasisPoints', 0)
                                                if 'updateAuthority' in metaplex:
                                                    token_obj.update_authority = metaplex.get('updateAuthority', '')
                                                if 'primarySaleHappened' in metaplex:
                                                    token_obj.primary_sale_happened = metaplex.get('primarySaleHappened', False)

                                            token_obj.save()
                                            logger.info(f"Updated Token metadata for {token.get('symbol', '')}: {token['mint']} using Moralis")
                                    except Exception as e:
                                        logger.error(f"Error getting token metadata: {e}")
                                else:
                                    # 更新现有 Token 对象的信息
                                    price_data = prices.get(token["mint"], {})
                                    if price_data:
                                        token_obj.current_price_usd = price_data.get("current_price", token_obj.current_price_usd)
                                        token_obj.price_change_24h = price_data.get("price_change_24h", token_obj.price_change_24h)
                                        token_obj.save()
                                        logger.info(f"Updated Token price for {token.get('symbol', '')}: {token['mint']}")

                                    # 强制更新所有代币的元数据
                                    # 如果元数据为空或者强制更新
                                    if True:  # 始终更新元数据
                                        try:
                                            from chains.solana.services.token import SolanaTokenService
                                            token_service = SolanaTokenService()
                                            metadata = token_service.get_token_metadata(token["mint"])

                                            if metadata:
                                                # 更新基本元数据
                                                token_obj.description = metadata.get('description', '')
                                                token_obj.website = metadata.get('website', '')
                                                token_obj.twitter = metadata.get('twitter', '')
                                                token_obj.telegram = metadata.get('telegram', '')
                                                token_obj.discord = metadata.get('discord', '')

                                                # 更新供应信息
                                                if 'totalSupply' in metadata:
                                                    try:
                                                        token_obj.total_supply = metadata.get('totalSupply', 0)
                                                    except Exception as e:
                                                        logger.error(f"Error setting total_supply: {e}")
                                                        # 尝试将字符串转换为数字
                                                        try:
                                                            token_obj.total_supply = float(metadata.get('totalSupply', 0))
                                                        except:
                                                            token_obj.total_supply = 0

                                                if 'totalSupplyFormatted' in metadata:
                                                    token_obj.total_supply_formatted = str(metadata.get('totalSupplyFormatted', ''))

                                                if 'fullyDilutedValue' in metadata:
                                                    try:
                                                        token_obj.fully_diluted_value = metadata.get('fullyDilutedValue', 0)
                                                    except Exception as e:
                                                        logger.error(f"Error setting fully_diluted_value: {e}")
                                                        # 尝试将字符串转换为数字
                                                        try:
                                                            token_obj.fully_diluted_value = float(metadata.get('fullyDilutedValue', 0))
                                                        except:
                                                            token_obj.fully_diluted_value = 0

                                                # 更新标准信息
                                                if 'standard' in metadata:
                                                    token_obj.standard = metadata.get('standard', '')
                                                if 'mint' in metadata:
                                                    token_obj.mint = metadata.get('mint', '')

                                                # 更新 Metaplex 元数据
                                                metaplex = metadata.get('metaplex', {})
                                                if metaplex:
                                                    if 'metadataUri' in metaplex:
                                                        token_obj.metadata_uri = metaplex.get('metadataUri', '')
                                                    if 'masterEdition' in metaplex:
                                                        token_obj.is_master_edition = metaplex.get('masterEdition', False)
                                                    if 'isMutable' in metaplex:
                                                        token_obj.is_mutable = metaplex.get('isMutable', True)
                                                    if 'sellerFeeBasisPoints' in metaplex:
                                                        token_obj.seller_fee_basis_points = metaplex.get('sellerFeeBasisPoints', 0)
                                                    if 'updateAuthority' in metaplex:
                                                        token_obj.update_authority = metaplex.get('updateAuthority', '')
                                                    if 'primarySaleHappened' in metaplex:
                                                        # primarySaleHappened 可能是数字或布尔值
                                                        primary_sale = metaplex.get('primarySaleHappened', 0)
                                                        if isinstance(primary_sale, bool):
                                                            token_obj.primary_sale_happened = primary_sale
                                                        else:
                                                            token_obj.primary_sale_happened = bool(primary_sale)

                                                token_obj.save()
                                                logger.info(f"Updated Token metadata for {token.get('symbol', '')}: {token['mint']} using Moralis")
                                        except Exception as e:
                                            logger.error(f"Error getting token metadata: {e}")
                            except Exception as e:
                                logger.error(f"Error getting or creating token object: {e}")

                            # 更新或创建 WalletToken 记录
                            wallet_token, created = WalletToken.objects.update_or_create(
                                wallet=wallet,
                                token_address=token["mint"],
                                defaults={
                                    'token': token_obj,
                                    'balance': raw_amount,
                                    'balance_formatted': balance_formatted,
                                    'is_visible': True
                                }
                            )

                            if created:
                                logger.info(f"Created new WalletToken record for {token_info['symbol']}")
                            else:
                                logger.info(f"Updated WalletToken record for {token_info['symbol']}")

                        except Exception as e:
                            logger.error(f"Error updating database for token {token_info['symbol']}: {e}")

                except Exception as e:
                    logger.error(f"Error processing token {token.get('mint', 'unknown')}: {e}")
                    continue

            # 按价值排序
            token_balances.sort(key=lambda x: float(x.get("value_usd", 0)), reverse=True)
            logger.info(f"Found {len(token_balances)} tokens with non-zero balance")

            # 添加刷新完成的标志
            logger.info(f"Refresh completed for address {address}")

            return token_balances

        except Exception as e:
            logger.error(f"Error getting token balances: {e}")
            return []

    def get_all_balances(self, address: str) -> dict:
        """获取所有代币余额"""
        try:
            # 获取原生 SOL 余额
            native_balance = self.get_native_balance(address)

            # 获取所有代币余额
            token_balances = self.get_all_token_balances(address)

            # 获取隐藏的代币列表
            hidden_tokens = WalletToken.objects.filter(
                wallet__address=address,
                is_visible=False
            ).values_list('token_address', flat=True)

            # 过滤掉隐藏的代币
            visible_tokens = [
                token for token in token_balances
                if token['token_address'] not in hidden_tokens
            ]

            # 计算总价值（USD）
            total_value_usd = Decimal('0')
            total_value_change_24h = Decimal('0')

            # 添加原生代币
            if native_balance:
                # 获取 SOL 价格和24小时变化
                sol_price_data = asyncio.run(self._get_token_prices(["So11111111111111111111111111111111111111112"]))
                if sol_price_data and "So11111111111111111111111111111111111111112" in sol_price_data:
                    price_data = sol_price_data["So11111111111111111111111111111111111111112"]
                    price = price_data["current_price"]
                    price_change_24h = price_data["price_change_24h"]
                    native_balance["price_usd"] = str(price)
                    native_balance["price_change_24h"] = str(price_change_24h)
                    native_balance["value_usd"] = str(float(native_balance["balance"]) * price)
                    total_value_usd += Decimal(str(native_balance["value_usd"]))
                    total_value_change_24h += Decimal(str(native_balance["value_usd"])) * Decimal(str(price_change_24h)) / 100
                visible_tokens.append(native_balance)

            # 计算代币总价值
            for token in visible_tokens:
                if token.get('value_usd'):
                    value_usd = Decimal(str(token['value_usd']))
                    price_change = Decimal(str(token.get('price_change_24h', 0)))
                    total_value_usd += value_usd
                    total_value_change_24h += value_usd * price_change / 100

            return {
                'total_value_usd': str(total_value_usd),
                'total_value_change_24h': str(total_value_change_24h),
                'tokens': visible_tokens
            }

        except Exception as e:
            logger.error(f"Error getting all balances: {str(e)}")
            return {
                'total_value_usd': '0',
                'total_value_change_24h': '0',
                'tokens': []
            }