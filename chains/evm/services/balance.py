from typing import Dict, Any, List
from web3 import Web3
from decimal import Decimal
import asyncio
import aiohttp
import logging
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

    async def _get_token_prices(self, token_addresses: List[str]) -> Dict[str, Dict]:
        """批量获取代币价格和24小时变化，使用分批处理避免请求过大"""
        try:
            # 设置每批处理的代币数量，减小批次大小
            batch_size = 30  # 从50减小到30
            all_prices = {}

            # 获取 API 配置
            api_key = Config.MORALIS_API_KEY
            base_url = "https://deep-index.moralis.io/api/v2"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": api_key
            }

            # 分批处理代币地址
            for i in range(0, len(token_addresses), batch_size):
                batch = token_addresses[i:i+batch_size]
                batch_num = i//batch_size + 1
                total_batches = (len(token_addresses) + batch_size - 1)//batch_size
                logger.info(f"处理 {self.chain} 链代币价格批次 {batch_num}/{total_batches}，包含 {len(batch)} 个代币")

                # 准备请求数据
                payload = {
                    "chain": self.chain.lower(),
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
                            url = f"{base_url}/erc20/prices"
                            # 增加超时设置
                            async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    logger.info(f"成功获取 {self.chain} 链批次 {batch_num} 的价格数据，共 {len(data.get('tokens', []))} 条记录")

                                    for token_data in data.get('tokens', []):
                                        token_address = token_data.get("address")
                                        if token_address:
                                            try:
                                                current_price = float(token_data.get("usdPrice", 0))
                                                price_change_24h = float(token_data.get("24hPercentChange", 0))

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
                await asyncio.sleep(1.5)  # 从0.5秒增加到1.5秒

            logger.info(f"完成 {self.chain} 链所有代币价格获取，共处理 {len(all_prices)} 个代币")
            return all_prices

        except Exception as e:
            logger.error(f"获取 {self.chain} 链代币价格时出错: {e}")
            return {}

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
                token, created = Token.objects.get_or_create(
                    chain=chain,
                    address="native",
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

            try:
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

    def get_all_token_balances(self, wallet_address: str, wallet_id: int = None) -> List[Dict[str, Any]]:
        """获取钱包所有代币余额"""
        try:
            # 初始化结果列表
            token_balances = []

            # 获取原生代币余额
            native_balance = self.get_native_balance(wallet_address, wallet_id)
            if native_balance:
                logger.info(f"成功获取原生代币余额: {native_balance}")
                token_balances.append(native_balance)
            else:
                logger.warning(f"无法获取原生代币余额")

            # 获取 ERC20 代币余额
            # 如果有 wallet_id，尝试从数据库中获取已知的代币列表
            if wallet_id:
                from wallets.models import WalletToken, Token
                # 获取钱包已有的代币列表
                wallet_tokens = WalletToken.objects.filter(wallet_id=wallet_id, token_address__isnull=False, token_address__gt="")

                for wallet_token in wallet_tokens:
                    try:
                        # 获取代币余额
                        token_balance = self.get_token_balance(wallet_token.token_address, wallet_address)
                        if token_balance > 0:
                            # 获取代币信息
                            token_info = {}
                            if wallet_token.token:
                                token_info = {
                                    "token_address": wallet_token.token_address,
                                    "symbol": wallet_token.token.symbol,
                                    "name": wallet_token.token.name,
                                    "balance": str(token_balance),
                                    "balance_formatted": str(token_balance),
                                    "decimals": wallet_token.token.decimals,
                                    "logo": wallet_token.token.logo_url,
                                    "current_price_usd": float(wallet_token.token.current_price_usd),
                                    "price_change_24h": float(wallet_token.token.price_change_24h)
                                }
                            else:
                                # 如果没有代币信息，尝试从链上获取
                                from chains.evm.services.token import EVMTokenService
                                token_service = EVMTokenService(self.chain)
                                token_metadata = token_service.get_token_metadata(wallet_token.token_address)

                                token_info = {
                                    "token_address": wallet_token.token_address,
                                    "symbol": token_metadata.get("symbol", ""),
                                    "name": token_metadata.get("name", ""),
                                    "balance": str(token_balance),
                                    "balance_formatted": str(token_balance),  # 确保 balance_formatted 不为 null
                                    "decimals": token_metadata.get("decimals", 18),
                                    "logo": token_metadata.get("logo", ""),
                                    "current_price_usd": 0,
                                    "price_change_24h": 0
                                }

                                # 更新数据库中的 balance_formatted
                                wallet_token.balance_formatted = str(token_balance)
                                wallet_token.save(update_fields=['balance_formatted'])

                            token_balances.append(token_info)
                    except Exception as token_error:
                        logger.error(f"获取代币 {wallet_token.token_address} 余额失败: {token_error}")

            # 尝试获取常见 ERC20 代币的余额
            # 根据链类型选择不同的常见代币列表
            common_tokens = []

            # 为了避免重复查询，记录已查询过的代币地址
            queried_tokens = set([token.get('token_address', '') for token in token_balances])

            # 根据链类型选择常见代币
            if self.chain.startswith('ETH'):
                # 以太坊主网常见代币
                common_tokens = [
                    # USDT
                    {'address': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'symbol': 'USDT', 'name': 'Tether USD', 'decimals': 6, 'logo': 'https://cryptologos.cc/logos/tether-usdt-logo.png'},
                    # USDC
                    {'address': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'symbol': 'USDC', 'name': 'USD Coin', 'decimals': 6, 'logo': 'https://cryptologos.cc/logos/usd-coin-usdc-logo.png'},
                    # DAI
                    {'address': '0x6B175474E89094C44Da98b954EedeAC495271d0F', 'symbol': 'DAI', 'name': 'Dai Stablecoin', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/multi-collateral-dai-dai-logo.png'},
                    # WETH
                    {'address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', 'symbol': 'WETH', 'name': 'Wrapped Ether', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/ethereum-eth-logo.png'},
                    # WBTC
                    {'address': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', 'symbol': 'WBTC', 'name': 'Wrapped BTC', 'decimals': 8, 'logo': 'https://cryptologos.cc/logos/wrapped-bitcoin-wbtc-logo.png'},
                    # UNI
                    {'address': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', 'symbol': 'UNI', 'name': 'Uniswap', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/uniswap-uni-logo.png'},
                    # LINK
                    {'address': '0x514910771AF9Ca656af840dff83E8264EcF986CA', 'symbol': 'LINK', 'name': 'ChainLink Token', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/chainlink-link-logo.png'},
                    # AAVE
                    {'address': '0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9', 'symbol': 'AAVE', 'name': 'Aave Token', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/aave-aave-logo.png'},
                    # SHIB
                    {'address': '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE', 'symbol': 'SHIB', 'name': 'SHIBA INU', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/shiba-inu-shib-logo.png'},
                ]
            elif self.chain.startswith('BSC'):
                # 币安主网常见代币
                common_tokens = [
                    # BUSD
                    {'address': '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56', 'symbol': 'BUSD', 'name': 'Binance USD', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/binance-usd-busd-logo.png'},
                    # USDT
                    {'address': '0x55d398326f99059fF775485246999027B3197955', 'symbol': 'USDT', 'name': 'Tether USD', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/tether-usdt-logo.png'},
                    # USDC
                    {'address': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d', 'symbol': 'USDC', 'name': 'USD Coin', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/usd-coin-usdc-logo.png'},
                    # WBNB
                    {'address': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', 'symbol': 'WBNB', 'name': 'Wrapped BNB', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/bnb-bnb-logo.png'},
                    # CAKE
                    {'address': '0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82', 'symbol': 'CAKE', 'name': 'PancakeSwap Token', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/pancakeswap-cake-logo.png'},
                ]
            elif self.chain.startswith('MATIC') or self.chain.startswith('POLYGON'):
                # Polygon主网常见代币
                common_tokens = [
                    # USDT
                    {'address': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F', 'symbol': 'USDT', 'name': 'Tether USD', 'decimals': 6, 'logo': 'https://cryptologos.cc/logos/tether-usdt-logo.png'},
                    # USDC
                    {'address': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', 'symbol': 'USDC', 'name': 'USD Coin', 'decimals': 6, 'logo': 'https://cryptologos.cc/logos/usd-coin-usdc-logo.png'},
                    # WMATIC
                    {'address': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270', 'symbol': 'WMATIC', 'name': 'Wrapped Matic', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/polygon-matic-logo.png'},
                    # WETH
                    {'address': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619', 'symbol': 'WETH', 'name': 'Wrapped Ether', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/ethereum-eth-logo.png'},
                ]
            elif self.chain.startswith('ARB'):
                # Arbitrum主网常见代币
                common_tokens = [
                    # USDT
                    {'address': '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9', 'symbol': 'USDT', 'name': 'Tether USD', 'decimals': 6, 'logo': 'https://cryptologos.cc/logos/tether-usdt-logo.png'},
                    # USDC
                    {'address': '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8', 'symbol': 'USDC', 'name': 'USD Coin', 'decimals': 6, 'logo': 'https://cryptologos.cc/logos/usd-coin-usdc-logo.png'},
                    # WETH
                    {'address': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1', 'symbol': 'WETH', 'name': 'Wrapped Ether', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/ethereum-eth-logo.png'},
                    # ARB
                    {'address': '0x912CE59144191C1204E64559FE8253a0e49E6548', 'symbol': 'ARB', 'name': 'Arbitrum', 'decimals': 18, 'logo': 'https://cryptologos.cc/logos/arbitrum-arb-logo.png'},
                ]

            # 查询常见代币的余额
            for token in common_tokens:
                if token['address'] not in queried_tokens:
                    try:
                        # 获取代币余额
                        token_balance = self.get_token_balance(token['address'], wallet_address)
                        if token_balance > 0:
                            # 获取代币价格和24小时变化
                            current_price_usd = 0
                            price_change_24h = 0

                            try:
                                # 尝试使用 CryptoCompare API 获取价格
                                import requests
                                response = requests.get(f"https://min-api.cryptocompare.com/data/price?fsym={token['symbol']}&tsyms=USD")
                                if response.status_code == 200:
                                    data = response.json()
                                    current_price_usd = data.get('USD', 0)

                                    # 获取 24 小时价格变化
                                    response_24h = requests.get(f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={token['symbol']}&tsym=USD&limit=24")
                                    if response_24h.status_code == 200:
                                        data_24h = response_24h.json()
                                        if data_24h.get('Response') == 'Success' and data_24h.get('Data') and data_24h['Data'].get('Data'):
                                            price_24h_ago = data_24h['Data']['Data'][0]['open']
                                            if price_24h_ago > 0:
                                                price_change_24h = ((current_price_usd - price_24h_ago) / price_24h_ago) * 100
                                            else:
                                                price_change_24h = 0
                            except Exception as e:
                                logger.error(f"获取代币 {token['symbol']} 价格失败: {e}")

                            # 添加到结果列表
                            token_info = {
                                "token_address": token['address'],
                                "symbol": token['symbol'],
                                "name": token['name'],
                                "balance": str(token_balance),
                                "balance_formatted": str(token_balance),  # 确保 balance_formatted 不为 null
                                "decimals": token['decimals'],
                                "logo": token['logo'],
                                "current_price_usd": current_price_usd,
                                "price_change_24h": price_change_24h
                            }

                            # 如果提供了钱包ID，更新数据库
                            if wallet_id:
                                from wallets.models import Wallet, WalletToken
                                wallet = Wallet.objects.get(id=wallet_id)
                                # 获取或创建 Token 对象
                                from wallets.models import Chain, Token
                                chain = Chain.objects.get(chain=self.chain)
                                token_obj, created = Token.objects.get_or_create(
                                    chain=chain,
                                    address=token['address'],
                                    defaults={
                                        "symbol": token['symbol'],
                                        "name": token['name'],
                                        "decimals": token['decimals'],
                                        "logo_url": token['logo'],
                                        "current_price_usd": current_price_usd,
                                        "price_change_24h": price_change_24h
                                    }
                                )

                                # 如果 Token 对象已存在，更新价格信息
                                if not created:
                                    token_obj.current_price_usd = current_price_usd
                                    token_obj.price_change_24h = price_change_24h
                                    token_obj.save(update_fields=['current_price_usd', 'price_change_24h'])

                                # 更新或创建 WalletToken 对象
                                wallet_token, _ = WalletToken.objects.update_or_create(
                                    wallet=wallet,
                                    token_address=token['address'],
                                    defaults={
                                        "token": token_obj,
                                        "balance": str(token_balance),
                                        "balance_formatted": str(token_balance),  # 确保 balance_formatted 不为 null
                                        "is_visible": True
                                    }
                                )
                            token_balances.append(token_info)
                            queried_tokens.add(token['address'])
                    except Exception as token_error:
                        logger.error(f"获取代币 {token['address']} 余额失败: {token_error}")

            # 返回所有代币余额
            return token_balances
        except Exception as e:
            logger.error(f"获取所有代币余额失败: {e}")
            return []