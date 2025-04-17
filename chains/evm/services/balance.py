from typing import Dict, Any, List
from web3 import Web3
from decimal import Decimal
import asyncio
import aiohttp
import logging
import time
from django.utils import timezone
from common.config import Config

logger = logging.getLogger(__name__)

class EVMBalanceService:
    """EVM 余额服务"""

    def __init__(self, chain: str):
        """初始化 EVM RPC 客户端"""
        config = Config.get_evm_config(chain)
        self.web3 = Web3(Web3.HTTPProvider(config["rpc_url"]))
        self.chain = chain

    def get_balance(self, address: str) -> Dict[str, Any]:
        """获取账户余额"""
        try:
            balance = self.web3.eth.get_balance(address)
            return {
                'balance': str(Decimal(balance) / Decimal(10**18)),  # 转换为 ETH
                'chain': self.chain,
                'address': address
            }
        except Exception as e:
            raise Exception(f"获取余额失败: {str(e)}")

    def get_token_balance(self, token_address: str, wallet_address: str) -> Decimal:
        """获取代币余额

        Args:
            token_address: 代币地址
            wallet_address: 钱包地址

        Returns:
            代币余额（Decimal类型）
        """
        try:
            # ERC20 代币合约 ABI
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                }
            ]

            # 检查链接状态
            connected = self.web3.is_connected()
            logger.info(f"Web3连接状态: {connected}")

            if not connected:
                logger.error(f"Web3无法连接到RPC节点: {self.web3.provider.endpoint_uri}")
                # 即使无法连接，也返回真实数据（即零），不使用模拟数据
                logger.warning(f"无法连接到RPC节点，返回零余额")
                return Decimal("0")

            # 创建合约实例
            contract = self.web3.eth.contract(address=token_address, abi=erc20_abi)

            # 获取余额和精度
            balance = contract.functions.balanceOf(wallet_address).call()
            decimals = contract.functions.decimals().call()

            # 计算带精度的余额
            balance_decimal = Decimal(balance) / Decimal(10**decimals)
            logger.info(f"成功获取代币 {token_address} 的余额: {balance_decimal}")

            return balance_decimal
        except Exception as e:
            logger.error(f"获取代币 {token_address} 余额失败: {str(e)}")
            return Decimal("0")

    def get_native_balance(self, wallet_address: str, wallet_id: int = None) -> Dict[str, Any]:
        """获取原生代币余额并更新数据库"""
        try:
            # 打印链信息
            logger.info(f"开始获取 {self.chain} 链上地址 {wallet_address} 的原生代币余额")
            logger.info(f"RPC URL: {self.web3.provider.endpoint_uri}")

            # 检查链接状态
            connected = self.web3.is_connected()
            logger.info(f"Web3连接状态: {connected}")

            # 尝试获取原生代币余额
            try:
                if not connected:
                    logger.error(f"Web3无法连接到RPC节点: {self.web3.provider.endpoint_uri}")
                    # 即使无法连接，也返回真实数据（即零），不使用模拟数据
                    logger.warning(f"无法连接到RPC节点，返回零余额")
                    balance_decimal = Decimal("0")
                else:
                    balance = self.web3.eth.get_balance(wallet_address)
                    balance_decimal = Decimal(balance) / Decimal(10**18)  # 转换为 ETH
                    logger.info(f"成功获取原生代币余额: {balance_decimal}")
            except Exception as e:
                logger.error(f"获取原生代币余额失败: {e}")
                # 即使是测试链，也返回真实数据（即零），不使用模拟数据
                logger.warning(f"获取原生代币余额失败，返回零余额")
                balance_decimal = Decimal("0")

            # 获取原生代币符号和名称
            symbol = "ETH"
            name = "Ethereum"
            logo = "https://cryptologos.cc/logos/ethereum-eth-logo.png"

            if self.chain == "BSC" or self.chain.startswith("BSC_"):
                symbol = "BNB"
                name = "BNB"
                logo = "https://cryptologos.cc/logos/bnb-bnb-logo.png"
            elif self.chain == "MATIC" or self.chain.startswith("MATIC_"):
                symbol = "MATIC"
                name = "Polygon"
                logo = "https://cryptologos.cc/logos/polygon-matic-logo.png"
            elif self.chain == "ARB" or self.chain.startswith("ARB_"):
                symbol = "ARB"
                name = "Arbitrum"
                logo = "https://cryptologos.cc/logos/arbitrum-arb-logo.png"
            elif self.chain == "OP" or self.chain.startswith("OP_"):
                symbol = "OP"
                name = "Optimism"
                logo = "https://cryptologos.cc/logos/optimism-ethereum-op-logo.png"
            elif self.chain == "AVAX" or self.chain.startswith("AVAX_"):
                symbol = "AVAX"
                name = "Avalanche"
                logo = "https://cryptologos.cc/logos/avalanche-avax-logo.png"
            elif self.chain == "BASE" or self.chain.startswith("BASE_"):
                symbol = "ETH"
                name = "Base Ethereum"
                logo = "https://cryptologos.cc/logos/ethereum-eth-logo.png"
            elif self.chain == "ZKSYNC" or self.chain.startswith("ZKSYNC_"):
                symbol = "ETH"
                name = "zkSync Ethereum"
                logo = "https://cryptologos.cc/logos/ethereum-eth-logo.png"
            elif self.chain == "LINEA" or self.chain.startswith("LINEA_"):
                symbol = "ETH"
                name = "Linea Ethereum"
                logo = "https://cryptologos.cc/logos/ethereum-eth-logo.png"
            elif self.chain == "MANTA" or self.chain.startswith("MANTA_"):
                symbol = "ETH"
                name = "Manta Ethereum"
                logo = "https://cryptologos.cc/logos/ethereum-eth-logo.png"
            elif self.chain == "FTM" or self.chain.startswith("FTM_"):
                symbol = "FTM"
                name = "Fantom"
                logo = "https://cryptologos.cc/logos/fantom-ftm-logo.png"
            elif self.chain == "CRO" or self.chain.startswith("CRO_"):
                symbol = "CRO"
                name = "Cronos"
                logo = "https://cryptologos.cc/logos/cronos-cro-logo.png"

            # 如果提供了钱包ID，则更新数据库
            if wallet_id:
                from wallets.models import Wallet, Chain, Token, WalletToken

                # 获取钱包和链对象
                wallet = Wallet.objects.get(id=wallet_id)
                chain = Chain.objects.get(chain=self.chain)

                # 检查原生代币是否已存在
                # 使用空字符串作为地址，与 WalletToken 中的 token_address 保持一致
                token, created = Token.objects.get_or_create(
                    chain=chain,
                    address="",  # 使用空字符串，而不是 "native"
                    defaults={
                        "symbol": symbol,
                        "name": name,
                        "decimals": 18,
                        "logo_url": logo
                    }
                )

                # 更新或创建钱包代币记录
                wallet_token, created = WalletToken.objects.update_or_create(
                    wallet=wallet,
                    token_address="",  # 原生代币使用空字符串作为 token_address
                    defaults={
                        "token": token,
                        "balance": str(balance_decimal),
                        "balance_formatted": str(balance_decimal),  # 确保 balance_formatted 不为 null
                        "is_visible": True
                    }
                )

                # 确保余额已更新
                if not created:
                    wallet_token.balance = str(balance_decimal)
                    wallet_token.balance_formatted = str(balance_decimal)  # 确保 balance_formatted 不为 null
                    wallet_token.save()

            # 获取原生代币的价格和24小时变化
            current_price_usd = 0
            price_change_24h = 0

            # 直接从 API 获取原生代币价格，不使用缓存
            # 尝试使用 CryptoCompare API 获取价格
            import requests
            symbol_map = {
                "ETH": "ETH",
                "BSC": "BNB",
                "MATIC": "MATIC",
                "ARB": "ARB",
                "OP": "OP",
                "AVAX": "AVAX",
                "BASE": "ETH",
                "ZKSYNC": "ETH",
                "LINEA": "ETH",
                "MANTA": "ETH",
                "FTM": "FTM",
                "CRO": "CRO"
            }

            # 获取当前链的原生代币符号
            chain_symbol = self.chain.split('_')[0]  # 去除可能的 _TESTNET 后缀
            crypto_symbol = symbol_map.get(chain_symbol, chain_symbol)

            try:
                response = requests.get(f"https://min-api.cryptocompare.com/data/price?fsym={crypto_symbol}&tsyms=USD")
                if response.status_code == 200:
                    data = response.json()
                    current_price_usd = data.get('USD', 0)

                    # 获取 24 小时价格变化
                    response_24h = requests.get(f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={crypto_symbol}&tsym=USD&limit=24")
                    if response_24h.status_code == 200:
                        data_24h = response_24h.json()
                        if data_24h.get('Response') == 'Success' and data_24h.get('Data') and data_24h['Data'].get('Data'):
                            price_24h_ago = data_24h['Data']['Data'][0]['close']
                            if price_24h_ago > 0:
                                price_change_24h = ((current_price_usd - price_24h_ago) / price_24h_ago) * 100
                            else:
                                price_change_24h = 0
            except Exception as e:
                logger.error(f"获取原生代币价格失败: {e}")

            # 返回原生代币信息
            return {
                "token_address": "",  # 使用空字符串表示原生代币
                "symbol": symbol,
                "name": name,
                "balance": str(balance_decimal),
                "balance_formatted": str(balance_decimal),
                "decimals": 18,
                "logo": logo,
                "current_price_usd": current_price_usd,
                "price_change_24h": price_change_24h
            }
        except Exception as e:
            logger.error(f"获取原生代币余额失败: {e}")
            # 即使是测试链，也返回实际余额，不使用硬编码的测试余额
            logger.warning(f"获取原生代币余额失败，返回空值")
            return None

    def get_all_balances(self, wallet_address: str, force_refresh: bool = False) -> dict:
        """获取所有代币余额"""
        try:
            # 获取原生代币余额
            native_balance = self.get_native_balance(wallet_address)

            # 获取所有代币余额
            token_balances = self.get_all_token_balances(wallet_address, force_refresh=force_refresh)

            # 获取隐藏的代币列表
            from wallets.models import WalletToken
            hidden_tokens = WalletToken.objects.filter(
                wallet__address=wallet_address,
                is_visible=False
            ).values_list('token_address', flat=True)

            # 过滤掉隐藏的代币和余额为0的代币
            visible_tokens = [
                token for token in token_balances
                if token['token_address'] not in hidden_tokens and
                   float(token.get('balance_formatted', '0')) > 0
            ]

            # 计算总价值（USD）
            from decimal import Decimal
            total_value_usd = Decimal('0')
            total_value_change_24h = Decimal('0')

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

    async def _get_token_prices(self, token_addresses: List[str]) -> Dict[str, Dict]:
        """批量获取代币价格和24小时变化"""
        try:
            import time
            prices_start_time = time.time()
            logger.info(f"开始获取代币价格，共 {len(token_addresses)} 个代币")

            # 如果没有代币地址，直接返回空字典
            if not token_addresses:
                return {}

            # 设置每批处理的代币数量
            batch_size = 90  # Moralis限制最多100个
            all_prices = {}

            # 使用集合来去除重复地址
            unique_addresses = list(set(token_addresses))
            logger.info(f"去除重复后需要查询的代币数量: {len(unique_addresses)}")

            # 跳过空地址
            uncached_addresses = [addr for addr in unique_addresses if addr]

            # 获取 API 配置
            api_key = Config.MORALIS_API_KEY
            base_url = "https://deep-index.moralis.io/api/v2"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": api_key
            }

            # 获取当前链的 Moralis 链 ID
            chain_id_map = {
                "ETH": "eth",
                "ETH_SEPOLIA": "sepolia",
                "ETH_GOERLI": "goerli",
                "BSC": "bsc",
                "BSC_TESTNET": "bsc testnet",
                "MATIC": "polygon",
                "MATIC_MUMBAI": "mumbai",
                "ARB": "arbitrum",
                "ARB_SEPOLIA": "arbitrum sepolia",
                "OP": "optimism",
                "OP_GOERLI": "optimism-goerli",
                "AVAX": "avalanche",
                "AVAX_FUJI": "avalanche testnet",
                "BASE": "base",
                "BASE_SEPOLIA": "base-sepolia",
                "ZKSYNC": "zksync",
                "ZKSYNC_TESTNET": "zksync-testnet",
                "LINEA": "linea",
                "LINEA_GOERLI": "linea-goerli",
                "MANTA": "manta",
                "MANTA_TESTNET": "manta-testnet",
                "FTM": "fantom",
                "FTM_TESTNET": "fantom-testnet",
                "CRO": "cronos",
                "CRO_TESTNET": "cronos-testnet"
            }

            moralis_chain = chain_id_map.get(self.chain, "").lower()
            if not moralis_chain:
                logger.error(f"Unsupported chain for Moralis API: {self.chain}")
                return {}

            # 准备并行请求函数
            async def fetch_batch_prices(batch_num, batch):
                if not batch:
                    logger.warning(f"批次 {batch_num} 为空，跳过")
                    return {}

                # 将地址列表转换为对象数组格式
                formatted_tokens = [{"token_address": addr} for addr in batch]

                payload = {
                    "chain": moralis_chain,
                    "tokens": formatted_tokens
                }

                # 添加重试机制
                max_retries = 3
                retry_delay = 2  # 重试间隔时间（秒）
                batch_prices = {}
                success = False

                for retry in range(max_retries):
                    try:
                        # 使用共享的会话以减少连接建立开销
                        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                            url = f"{base_url}/erc20/prices"
                            start_time = time.time()
                            async with session.post(url, json=payload, headers=headers) as response:
                                end_time = time.time()
                                logger.debug(f"批次 {batch_num} 请求耗时: {end_time - start_time:.2f} 秒")
                                if response.status == 200:
                                    data = await response.json()

                                    # 检查响应是列表还是字典
                                    token_list = []
                                    if isinstance(data, list):
                                        # 如果是列表，直接使用
                                        token_list = data
                                        logger.info(f"成功获取 {self.chain} 链批次 {batch_num} 的价格数据，共 {len(token_list)} 条记录")
                                    elif isinstance(data, dict) and 'tokens' in data:
                                        # 如果是字典且包含 tokens 字段，使用 tokens 字段
                                        token_list = data['tokens']
                                        logger.info(f"成功获取 {self.chain} 链批次 {batch_num} 的价格数据，共 {len(token_list)} 条记录")
                                    else:
                                        # 其他情况，记录错误并跳过
                                        logger.error(f"意外的响应格式: {data}")
                                        continue

                                    for token_data in token_list:
                                        # 适应新的响应格式
                                        token_address = None
                                        if isinstance(token_data, dict):
                                            # 尝试不同的字段名称
                                            token_address = token_data.get("token_address") or token_data.get("address") or token_data.get("tokenAddress")

                                        if token_address:
                                            try:
                                                current_price = float(token_data.get("usdPrice", 0))
                                                price_change_24h = float(token_data.get("24hPercentChange", 0) or token_data.get("usdPrice24hrPercentChange", 0))

                                                price_data = {
                                                    "current_price": current_price,
                                                    "price_change_24h": price_change_24h
                                                }

                                                batch_prices[token_address] = price_data
                                                logger.debug(f"代币 {token_address} 当前价格: {current_price}, 24小时变化: {price_change_24h}%")
                                            except (ValueError, TypeError) as e:
                                                logger.error(f"处理代币 {token_address} 价格数据时出错: {e}")
                                                batch_prices[token_address] = {
                                                    "current_price": 0.0,
                                                    "price_change_24h": 0.0
                                                }
                                    success = True
                                    break  # 成功获取数据，跳出重试循环
                                else:
                                    error_text = await response.text()
                                    logger.error(f"获取 {self.chain} 链代币价格批次 {batch_num} 失败: {response.status}, 错误信息: {error_text}")
                                    if retry < max_retries - 1:  # 如果还有重试机会
                                        logger.info(f"将在 {retry_delay} 秒后重试（第 {retry+1} 次）")
                                        await asyncio.sleep(retry_delay)
                                        retry_delay *= 2  # 指数退避策略
                    except Exception as e:
                        logger.error(f"处理 {self.chain} 链批次 {batch_num} 时发生异常: {str(e)}")
                        if retry < max_retries - 1:  # 如果还有重试机会
                            logger.info(f"将在 {retry_delay} 秒后重试（第 {retry+1} 次）")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避策略

                if not success:
                    logger.warning(f"{self.chain} 链批次 {batch_num} 在多次重试后仍然失败，跳过该批次")

                # 增加批次间的等待时间，避免API限制
                await asyncio.sleep(0.5)
                
                return batch_prices

            # 分批处理代币地址
            batches = [uncached_addresses[i:i+batch_size] for i in range(0, len(uncached_addresses), batch_size)]
            logger.info(f"将 {len(uncached_addresses)} 个代币分为 {len(batches)} 个批次处理")

            # 并行处理所有批次
            tasks = [fetch_batch_prices(i, batch) for i, batch in enumerate(batches)]
            batch_results = await asyncio.gather(*tasks)

            # 合并所有批次的结果
            for result in batch_results:
                all_prices.update(result)

            # 记录总耗时
            prices_end_time = time.time()
            total_prices_time = prices_end_time - prices_start_time
            logger.info(f"完成 {self.chain} 链所有代币价格获取，共处理 {len(all_prices)} 个代币，总耗时: {total_prices_time:.2f} 秒")
            
            return all_prices

        except Exception as e:
            logger.error(f"获取 {self.chain} 链代币价格时出错: {e}")
            return {}  # 如果出错，返回空字典

    def get_moralis_token_balances(self, wallet_address: str) -> List[Dict[str, Any]]:
        """使用 Moralis API 获取所有代币余额"""
        try:
            import requests
            import time
            start_time = time.time()

            # 获取 Moralis API 配置
            api_key = Config.MORALIS_API_KEY
            if not api_key:
                logger.error("Moralis API key is not configured")
                return []

            # 准备请求参数
            chain_id_map = {
                "ETH": "eth",
                "ETH_SEPOLIA": "sepolia",
                "ETH_GOERLI": "goerli",
                "BSC": "bsc",
                "BSC_TESTNET": "bsc testnet",
                "MATIC": "polygon",
                "MATIC_MUMBAI": "mumbai",
                "ARB": "arbitrum",
                "ARB_SEPOLIA": "arbitrum sepolia",
                "OP": "optimism",
                "OP_GOERLI": "optimism-goerli",
                "AVAX": "avalanche",
                "AVAX_FUJI": "avalanche testnet",
                "BASE": "base",
                "BASE_SEPOLIA": "base-sepolia",
                "ZKSYNC": "zksync",
                "ZKSYNC_TESTNET": "zksync-testnet",
                "LINEA": "linea",
                "LINEA_GOERLI": "linea-goerli",
                "MANTA": "manta",
                "MANTA_TESTNET": "manta-testnet",
                "FTM": "fantom",
                "FTM_TESTNET": "fantom-testnet",
                "CRO": "cronos",
                "CRO_TESTNET": "cronos-testnet"
            }

            # 获取当前链的 Moralis 链 ID
            moralis_chain = chain_id_map.get(self.chain, "").lower()
            if not moralis_chain:
                logger.error(f"Unsupported chain for Moralis API: {self.chain}")
                return []

            # 构建 API URL
            base_url = "https://deep-index.moralis.io/api/v2"
            url = f"{base_url}/{wallet_address}/erc20"

            # 设置请求头
            headers = {
                "accept": "application/json",
                "X-API-Key": api_key
            }

            # 设置请求参数
            params = {
                "chain": moralis_chain
            }

            # 添加重试机制
            max_retries = 3
            retry_delay = 2  # 初始重试延迟（秒）

            for retry in range(max_retries):
                try:
                    # 发送请求
                    logger.info(f"Calling Moralis API: {url} with chain={moralis_chain}")
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                    logger.info(f"Moralis API response status: {response.status_code}")

                    # 检查响应状态
                    if response.status_code == 200:
                        data = response.json()
                        logger.info(f"Successfully got token balances from Moralis API: {len(data)} tokens")

                        # 处理响应数据
                        tokens = []
                        for token_data in data:
                            token_address = token_data.get("token_address", "")
                            if not token_address:
                                continue

                            # 获取代币余额
                            balance = token_data.get("balance", "0")
                            decimals = int(token_data.get("decimals", 18))

                            # 计算带精度的余额
                            from decimal import Decimal
                            balance_decimal = Decimal(balance) / Decimal(10**decimals)

                            # 如果余额为 0，跳过
                            if balance_decimal == 0:
                                continue

                            # 构建代币信息
                            token_info = {
                                "token_address": token_address,
                                "symbol": token_data.get("symbol", ""),
                                "name": token_data.get("name", ""),
                                "balance": str(balance_decimal),
                                "balance_formatted": str(balance_decimal),
                                "decimals": decimals,
                                "logo": token_data.get("logo", ""),
                                "current_price_usd": 0,
                                "price_change_24h": 0
                            }

                            tokens.append(token_info)

                        # 获取代币价格
                        if tokens:
                            # 收集所有代币地址
                            token_addresses = [token["token_address"] for token in tokens]

                            # 批量获取代币价格
                            token_prices = asyncio.run(self._get_token_prices(token_addresses))

                            # 更新代币价格
                            for token in tokens:
                                token_address = token["token_address"]
                                if token_address in token_prices:
                                    price_data = token_prices[token_address]
                                    token["current_price_usd"] = price_data.get("current_price", 0)
                                    token["price_change_24h"] = price_data.get("price_change_24h", 0)

                        end_time = time.time()
                        logger.info(f"Moralis API call completed in {end_time - start_time:.2f} seconds")
                        return tokens
                    elif response.status_code == 429:
                        # 如果遇到速率限制，等待一段时间后重试
                        logger.warning(f"Moralis API rate limit exceeded, retrying in {retry_delay} seconds")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        # 其他错误，记录错误信息
                        error_text = response.text
                        logger.error(f"Moralis API error: {response.status_code}, {error_text}")
                        if retry < max_retries - 1:
                            logger.info(f"Retrying in {retry_delay} seconds (attempt {retry + 1}/{max_retries})")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                        else:
                            logger.error("Max retries reached, giving up")
                            return []
                except Exception as e:
                    logger.error(f"Error calling Moralis API: {e}")
                    if retry < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay} seconds (attempt {retry + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        logger.error("Max retries reached, giving up")
                        return []

            return []
        except Exception as e:
            logger.error(f"Error getting token balances from Moralis API: {e}")
            return []

    def update_token_in_database(self, wallet_id: int, token: Dict[str, Any]) -> None:
        """更新数据库中的代币信息"""
        try:
            from wallets.models import Wallet, Chain, Token, WalletToken

            # 获取钱包和链对象
            wallet = Wallet.objects.get(id=wallet_id)
            chain = Chain.objects.get(chain=self.chain)

            # 获取代币信息
            token_address = token.get("token_address", "")
            symbol = token.get("symbol", "")
            name = token.get("name", "")
            decimals = token.get("decimals", 18)
            logo = token.get("logo", "")
            balance = token.get("balance", "0")
            balance_formatted = token.get("balance_formatted", "0")
            current_price_usd = token.get("current_price_usd", 0)
            price_change_24h = token.get("price_change_24h", 0)

            # 获取或创建代币对象
            token_obj, created = Token.objects.get_or_create(
                chain=chain,
                address=token_address,
                defaults={
                    "symbol": symbol,
                    "name": name,
                    "decimals": decimals,
                    "logo_url": logo,
                    "current_price_usd": current_price_usd,
                    "price_change_24h": price_change_24h,
                    "last_updated": timezone.now()
                }
            )

            # 如果代币对象已存在，更新价格信息
            if not created:
                token_obj.current_price_usd = current_price_usd
                token_obj.price_change_24h = price_change_24h
                token_obj.last_updated = timezone.now()
                token_obj.save(update_fields=["current_price_usd", "price_change_24h", "last_updated"])

            # 更新或创建钱包代币对象
            wallet_token, _ = WalletToken.objects.update_or_create(
                wallet=wallet,
                token_address=token_address,
                defaults={
                    "token": token_obj,
                    "balance": balance,
                    "balance_formatted": balance_formatted,
                    "is_visible": True,
                    "last_synced": timezone.now()
                }
            )

            logger.info(f"Successfully updated token {symbol} ({token_address}) in database")
        except Exception as e:
            logger.error(f"Error updating token in database: {e}")

    def get_all_token_balances(self, wallet_address: str, wallet_id: int = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """获取钱包所有代币余额"""
        try:
            # 初始化结果列表
            token_balances = []

            logger.info(f"直接从链上获取数据，不使用缓存")

            # 获取原生代币余额
            native_balance = self.get_native_balance(wallet_address, wallet_id)

            if native_balance:
                logger.info(f"成功获取原生代币余额: {native_balance}")
                token_balances.append(native_balance)
            else:
                logger.warning(f"无法获取原生代币余额")

            # 使用 Moralis API 获取所有代币余额
            moralis_tokens = self.get_moralis_token_balances(wallet_address)
            if moralis_tokens:
                logger.info(f"成功从 Moralis 获取代币余额，共 {len(moralis_tokens)} 个代币")
                # 将 Moralis 返回的代币添加到结果列表
                for token in moralis_tokens:
                    # 跳过原生代币，因为我们已经处理过了
                    if token.get('token_address', '') == '':
                        continue
                    token_balances.append(token)

                    # 如果提供了钱包ID，更新数据库
                    if wallet_id:
                        self.update_token_in_database(wallet_id, token)
            else:
                logger.warning(f"无法从 Moralis 获取代币余额")

            # 如果提供了 wallet_id，处理零余额的代币
            if wallet_id:
                try:
                    from wallets.models import WalletToken
                    # 获取数据库中当前钱包的所有代币
                    wallet_tokens = WalletToken.objects.filter(wallet_id=wallet_id)
                    logger.info(f"数据库中的代币数量: {wallet_tokens.count()}")

                    # 获取当前链上返回的所有代币地址
                    current_token_addresses = [token.get('token_address', '') for token in token_balances]
                    logger.info(f"链上返回的代币地址: {current_token_addresses}")

                    # 找出数据库中存在但链上没有返回的代币（可能是零余额的代币）
                    for wt in wallet_tokens:
                        logger.info(f"检查数据库中的代币: {wt.token_address}, 当前余额: {wt.balance}")
                        if wt.token_address not in current_token_addresses and wt.token_address != "":
                            logger.info(f"删除零余额代币: {wt.token_address}, 原余额: {wt.balance}")
                            # 删除零余额代币
                            wt.delete()
                            logger.info(f"已删除代币 {wt.token_address}")
                except Exception as e:
                    logger.error(f"Error processing zero balance tokens: {e}")

            # 返回所有代币余额
            return token_balances
        except Exception as e:
            logger.error(f"获取所有代币余额失败: {e}")
            return []