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

    def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """获取代币余额"""
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

            contract = self.web3.eth.contract(address=token_address, abi=erc20_abi)
            balance = contract.functions.balanceOf(wallet_address).call()
            decimals = contract.functions.decimals().call()

            return {
                'balance': str(Decimal(balance) / Decimal(10**decimals)),
                'decimals': decimals,
                'chain': self.chain,
                'token_address': token_address,
                'wallet_address': wallet_address
            }
        except Exception as e:
            raise Exception(f"获取代币余额失败: {str(e)}")

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

    def get_all_token_balances(self, wallet_address: str, wallet_id: int = None) -> Dict[str, Any]:
        """获取钱包所有代币余额"""
        # 这里需要实现获取所有代币余额的逻辑
        # 可以使用 Moralis API 或其他服务
        return {}