from typing import Dict, Any, List, Optional
from decimal import Decimal
import logging
import requests
from common.config import Config
from wallets.models import Token, WalletToken, Wallet, Chain

logger = logging.getLogger(__name__)

class KadenaBalanceService:
    """Kadena 余额服务"""

    def __init__(self):
        """初始化 Kadena 服务"""
        self.config = Config()

    def get_balance(self, chain: str, address: str) -> Dict[str, Any]:
        """获取账户余额"""
        try:
            logger.info(f"获取 {chain} 链上地址 {address} 的余额")

            # 使用 Kadena SDK 获取余额
            from kadena_sdk.kadena_sdk import KadenaSdk
            from decimal import Decimal
            kadena_config = self.config.get_kadena_config(chain)

            # 检查是否是多链架构
            if kadena_config.get('multi_chain', False):
                # 如果是多链架构，并行查询所有链上的余额
                import concurrent.futures
                import time

                # 使用缓存键来检查是否有缓存
                cache_key = f"{chain}:{address}:balance"
                cache_timeout = 60  # 缓存 60 秒

                # 尝试从缓存中获取余额
                from django.core.cache import cache
                cached_balance = cache.get(cache_key)
                if cached_balance is not None:
                    logger.info(f"从缓存中获取余额: {cached_balance}")
                    return {
                        "balance": cached_balance,
                        "chain": chain,
                        "address": address
                    }

                # 如果没有缓存，并行查询链
                logger.info(f"没有缓存，开始并行查询所有 Kadena 平行链上的余额")
                total_balance = Decimal('0')
                start_time = time.time()

                # 定义查询单个链的函数
                def query_chain_balance(kadena_chain_id):
                    try:
                        # 更新 API 版本以匹配当前 Kadena 链 ID
                        # 注意: 这里的 kadena_chain_id 是 Kadena 平行链的 ID（0-19）
                        # 不要与钱包模型中的 chain 字段（如 "KDA", "KDA_TESTNET"）混淆
                        if chain == "KDA":
                            api_version = f"chainweb/0.0/mainnet01/chain/{kadena_chain_id}"
                        else:  # KDA_TESTNET
                            api_version = f"chainweb/0.0/testnet04/chain/{kadena_chain_id}"

                        # 对Chain 0的查询进行特殊处理
                        if kadena_chain_id == 0:
                            logger.info(f"开始查询 Kadena 平行链 0 (主链) 上的余额")
                        else:
                            logger.info(f"开始查询 Kadena 平行链 {kadena_chain_id} 上的余额")

                        # 创建 SDK 实例
                        sdk = KadenaSdk(
                            kadena_config['rpc_url'],
                            str(kadena_chain_id),  # 使用当前 Kadena 链 ID
                            kadena_config['network_id'],
                            api_version
                        )

                        # 获取当前链上的余额
                        chain_balance = sdk.get_balance(address)

                        # 对Chain 0的结果进行特殊处理
                        if kadena_chain_id == 0:
                            logger.info(f"Kadena 平行链 0 (主链) 上的余额: {chain_balance}")
                            # 如果Chain 0有余额，打印更详细的日志
                            if chain_balance > 0:
                                logger.info(f"\u2605\u2605\u2605 发现Chain 0上有余额: {chain_balance} \u2605\u2605\u2605")
                        else:
                            logger.info(f"Kadena 平行链 {kadena_chain_id} 上的余额: {chain_balance}")

                        return kadena_chain_id, chain_balance
                    except Exception as chain_error:
                        # 对Chain 0的错误进行特殊处理
                        if kadena_chain_id == 0:
                            logger.error(f"\u2757\u2757\u2757 获取 Kadena 链 0 (主链) 上的余额失败: {str(chain_error)}")
                        else:
                            logger.error(f"获取 Kadena 链 {kadena_chain_id} 上的余额失败: {str(chain_error)}")
                        return kadena_chain_id, Decimal('0')

                # 使用线程池并行查询
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    # 提交所有查询任务
                    # 优先查询Chain 0，然后再查询其他链
                    # 将Chain 0放在列表的最前面，确保它首先被查询
                    kadena_chain_ids_to_query = [0] + [i for i in kadena_config['kadena_chain_ids'] if i != 0]
                    future_to_chain = {executor.submit(query_chain_balance, kadena_chain_id): kadena_chain_id for kadena_chain_id in kadena_chain_ids_to_query}

                    # 处理查询结果
                    chain0_balance = Decimal('0')  # 专门记录Chain 0的余额
                    other_chains_balance = Decimal('0')  # 记录其他链的余额

                    for future in concurrent.futures.as_completed(future_to_chain):
                        kadena_chain_id = future_to_chain[future]
                        try:
                            kadena_chain_id, chain_balance = future.result()
                            if chain_balance > 0:
                                logger.info(f"Kadena 链 {kadena_chain_id} 上的余额: {chain_balance}")

                                # 分开记录Chain 0和其他链的余额
                                if kadena_chain_id == 0:
                                    chain0_balance = chain_balance
                                    logger.info(f"Chain 0 余额: {chain0_balance}")
                                else:
                                    other_chains_balance += chain_balance
                                    logger.info(f"其他链累计余额: {other_chains_balance}")

                                total_balance += chain_balance
                        except Exception as exc:
                            logger.error(f"处理 Kadena 链 {kadena_chain_id} 的查询结果时出错: {str(exc)}")

                    # 如果所有链的总余额为0，但Chain 0有余额，使用Chain 0的余额
                    if total_balance == 0 and chain0_balance > 0:
                        logger.warning(f"总余额为0，但Chain 0有余额 {chain0_balance}，使用Chain 0的余额")
                        total_balance = chain0_balance

                end_time = time.time()
                logger.info(f"并行查询所有链上的余额耗时: {end_time - start_time:.2f} 秒")
                logger.info(f"所有链上的总余额: {total_balance}")

                # 记录查询的链数量
                logger.info(f"共查询了 {len(kadena_chain_ids_to_query)} 个 Kadena 平行链")

                # 将结果存入缓存
                cache.set(cache_key, str(total_balance), cache_timeout)

                return {
                    "balance": str(total_balance),
                    "chain": chain,
                    "address": address
                }
            else:
                # 如果不是多链架构，只查询指定链上的余额
                sdk = KadenaSdk(
                    kadena_config['rpc_url'],
                    kadena_config['chain_id'],
                    kadena_config['network_id'],
                    kadena_config['api_version']
                )

                balance = sdk.get_balance(address)
                logger.info(f"获取到余额: {balance}")

                return {
                    "balance": str(balance),
                    "chain": chain,
                    "address": address
                }
        except Exception as e:
            logger.error(f"获取 Kadena 余额失败: {str(e)}")
            raise Exception(f"获取 Kadena 余额失败: {str(e)}")

    def get_all_token_balances(self, chain: str, address: str, wallet_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有代币余额并更新数据库"""
        try:
            import time
            start_time = time.time()
            logger.info(f"开始获取 {chain} 链上地址 {address} 的所有代币余额")

            # 使用缓存键来检查是否有缓存
            cache_key = f"{chain}:{address}:all_tokens"
            cache_timeout = 60  # 缓存 60 秒

            # 尝试从缓存中获取代币列表
            from django.core.cache import cache
            cached_tokens = cache.get(cache_key)

            # 如果提供了钱包ID并且有缓存，直接更新数据库
            if wallet_id and cached_tokens is not None:
                logger.info(f"从缓存中获取代币列表，共 {len(cached_tokens)} 个代币")

                # 更新数据库
                self._update_database(wallet_id, chain, cached_tokens)

                end_time = time.time()
                logger.info(f"从缓存获取并更新数据库耗时: {end_time - start_time:.2f} 秒")
                return cached_tokens

            # 如果没有缓存，查询原生代币余额
            native_balance = self.get_balance(chain, address)
            logger.info(f"获取到原生代币余额: {native_balance}")

            # 获取代币列表
            from chains.kadena.services.token import KadenaTokenService
            token_service = KadenaTokenService()
            tokens = token_service.get_token_list(address)
            logger.info(f"获取到 {len(tokens)} 个代币")

            # 合并所有代币余额
            all_tokens = [native_balance] + tokens

            # 将结果存入缓存
            cache.set(cache_key, all_tokens, cache_timeout)

            # 如果提供了钱包ID，更新数据库
            if wallet_id:
                self._update_database(wallet_id, chain, all_tokens)

            end_time = time.time()
            logger.info(f"获取所有代币余额并更新数据库耗时: {end_time - start_time:.2f} 秒")
            return all_tokens
        except Exception as e:
            logger.error(f"获取所有代币余额失败: {str(e)}")
            raise Exception(f"获取所有代币余额失败: {str(e)}")

    def _update_database(self, wallet_id: int, chain: str, tokens: List[Dict[str, Any]]) -> None:
        """更新数据库中的代币余额"""
        try:
            logger.info(f"开始更新数据库中的代币余额，钱包ID: {wallet_id}")

            # 获取钱包对象
            wallet = Wallet.objects.get(id=wallet_id)

            # 获取链对象
            chain_obj = Chain.objects.get(chain=chain)

            # 更新原生代币（第一个代币）
            if tokens and len(tokens) > 0:
                self._update_native_token(wallet, chain_obj, tokens[0])

            # 更新其他代币
            for token in tokens[1:] if len(tokens) > 1 else []:
                self._update_token(wallet, chain_obj, token)

            logger.info(f"数据库更新完成，共处理 {len(tokens)} 个代币")
        except Exception as e:
            logger.error(f"更新数据库失败: {str(e)}")
            raise Exception(f"更新数据库失败: {str(e)}")

    def _update_native_token(self, wallet: Wallet, chain: Chain, balance_data: Dict[str, Any]) -> None:
        """更新原生代币信息"""
        try:
            logger.info(f"开始更新钱包 {wallet.address} 的原生 KDA 代币信息")
            logger.info(f"从链上获取的余额数据: {balance_data}")

            # 检查数据库中是否已有该代币
            token, created = Token.objects.get_or_create(
                address="",  # 原生 KDA 代币使用空字符串作为地址
                chain=chain,
                defaults={
                    "name": "Kadena",
                    "symbol": "KDA",
                    "decimals": 12,  # Kadena 默认精度为 12
                    "logo_url": "https://cryptologos.cc/logos/kadena-kda-logo.png",  # KDA 的 logo URL
                    "current_price_usd": 0,
                    "price_change_24h": 0,
                    "is_active": True
                }
            )

            if created:
                logger.info(f"创建了新的 KDA 代币记录")
            else:
                logger.info(f"使用现有的 KDA 代币记录 (ID: {token.id})")
                # 确保现有记录也有正确的logo_url
                if not token.logo_url:
                    token.logo_url = "https://cryptologos.cc/logos/kadena-kda-logo.png"
                    token.save(update_fields=['logo_url'])
                    logger.info(f"更新了 KDA 代币的 logo_url")

            # 获取KDA的价格和24小时涨跌
            try:
                import requests
                from django.conf import settings

                # 使用CryptoCompare API获取KDA的价格
                cryptocompare_url = "https://min-api.cryptocompare.com/data/price"
                params = {
                    "fsym": "KDA",
                    "tsyms": "USD"
                }

                # 添加API密钥（如果有）
                if hasattr(settings, 'CRYPTOCOMPARE_API_KEY') and settings.CRYPTOCOMPARE_API_KEY:
                    params['api_key'] = settings.CRYPTOCOMPARE_API_KEY

                response = requests.get(cryptocompare_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if 'USD' in data:
                        current_price_usd = data['USD']
                        logger.info(f"获取到KDA当前价格: {current_price_usd} USD")

                        # 获取24小时价格变化
                        histohour_url = "https://min-api.cryptocompare.com/data/v2/histohour"
                        histohour_params = {
                            "fsym": "KDA",
                            "tsym": "USD",
                            "limit": 24
                        }

                        # 添加API密钥（如果有）
                        if hasattr(settings, 'CRYPTOCOMPARE_API_KEY') and settings.CRYPTOCOMPARE_API_KEY:
                            histohour_params['api_key'] = settings.CRYPTOCOMPARE_API_KEY

                        histohour_response = requests.get(histohour_url, params=histohour_params)
                        if histohour_response.status_code == 200:
                            histohour_data = histohour_response.json()
                            if histohour_data.get('Response') == 'Success' and histohour_data.get('Data') and histohour_data['Data'].get('Data'):
                                price_24h_ago = histohour_data['Data']['Data'][0]['open']
                                if price_24h_ago > 0:
                                    price_change_24h = ((current_price_usd - price_24h_ago) / price_24h_ago) * 100
                                    logger.info(f"KDA 24小时价格变化: {price_change_24h:.2f}%")

                                    # 更新代币价格和24小时变化
                                    token.current_price_usd = current_price_usd
                                    token.price_change_24h = price_change_24h
                                    token.save()
                                    logger.info(f"更新了KDA代币价格和24小时变化")

                                    # 确保也更新了WalletToken记录
                                    wallet_token = WalletToken.objects.filter(wallet=wallet, token_address="").first()
                                    if wallet_token:
                                        wallet_token.token = token
                                        wallet_token.save()
                                        logger.info(f"更新了WalletToken记录的Token关联")
            except Exception as e:
                logger.error(f"获取KDA价格和24小时变化失败: {str(e)}")

            # 更新钱包代币关系
            # 尝试查找现有的钱包代币关系
            # 同时查找空地址和"coin"地址的记录
            empty_tokens = WalletToken.objects.filter(wallet=wallet, token_address="")
            coin_tokens = WalletToken.objects.filter(wallet=wallet, token_address="coin")
            logger.info(f"现有的空地址原生代币记录数量: {empty_tokens.count()}")
            logger.info(f"现有的'coin'地址原生代币记录数量: {coin_tokens.count()}")

            # 如果同时存在空地址和"coin"地址的记录，合并它们
            if empty_tokens.count() > 0 and coin_tokens.count() > 0:
                logger.warning(f"同时存在空地址和'coin'地址的记录，将合并它们")

                # 获取两种记录的余额
                empty_balance = Decimal('0')
                coin_balance = Decimal('0')

                for token_record in empty_tokens:
                    try:
                        empty_balance += Decimal(token_record.balance)
                    except:
                        pass

                for token_record in coin_tokens:
                    try:
                        coin_balance += Decimal(token_record.balance)
                    except:
                        pass

                logger.info(f"空地址记录的余额: {empty_balance}")
                logger.info(f"'coin'地址记录的余额: {coin_balance}")

                # 如果'coin'记录有余额，但空地址记录没有余额，将余额转移到空地址记录
                if coin_balance > 0 and empty_balance == 0:
                    logger.info(f"将'coin'记录的余额转移到空地址记录")
                    empty_token = empty_tokens.first()
                    empty_token.balance = str(coin_balance)
                    empty_token.save()

                # 删除'coin'记录
                for token_record in coin_tokens:
                    logger.info(f"删除'coin'地址记录 ID: {token_record.id}")
                    token_record.delete()

            # 如果只有'coin'地址的记录，将其转换为空地址记录
            elif empty_tokens.count() == 0 and coin_tokens.count() > 0:
                logger.warning(f"只有'coin'地址的记录，将其转换为空地址记录")

                for token_record in coin_tokens:
                    # 创建新的空地址记录
                    WalletToken.objects.create(
                        wallet=token_record.wallet,
                        token=token,
                        token_address="",
                        balance=token_record.balance,
                        is_visible=token_record.is_visible
                    )

                    # 删除'coin'记录
                    logger.info(f"删除'coin'地址记录 ID: {token_record.id}")
                    token_record.delete()

            # 如果有多个空地址记录，删除多余的
            if empty_tokens.count() > 1:
                logger.warning(f"发现多个空地址原生代币记录，将删除多余的")
                for token_record in empty_tokens[1:]:
                    logger.info(f"删除多余的空地址原生代币记录 ID: {token_record.id}")
                    token_record.delete()

            # 创建或更新钱包代币关系
            wallet_token, created = WalletToken.objects.get_or_create(
                wallet=wallet,
                token_address="",  # 原生代币使用空字符串作为 token_address
                defaults={
                    "token": token,
                    "balance": balance_data["balance"],
                    "balance_formatted": balance_data["balance"],
                    "is_visible": True
                }
            )

            # 如果已存在，更新余额
            if not created:
                old_balance = wallet_token.balance
                new_balance = balance_data["balance"]

                # 如果新余额为0但旧余额大于0，保留旧余额
                if Decimal(new_balance) == 0 and Decimal(old_balance) > 0:
                    logger.warning(f"\u2757 新余额为0，但旧余额为 {old_balance}，保留旧余额")
                    # 不更新余额，保留旧值
                else:
                    wallet_token.balance = new_balance
                    wallet_token.balance_formatted = new_balance
                    wallet_token.save()
                    logger.info(f"更新了现有的 KDA 余额记录，从 {old_balance} 变为 {new_balance}")
            else:
                logger.info(f"创建了新的 KDA 余额记录，余额为 {balance_data['balance']}")

            logger.info(f"更新原生代币 KDA 成功，余额: {balance_data['balance']}")
        except Exception as e:
            logger.error(f"更新原生代币失败: {str(e)}")
            raise Exception(f"更新原生代币失败: {str(e)}")

    def _update_token(self, wallet: Wallet, chain: Chain, token_data: Dict[str, Any]) -> None:
        """更新代币信息"""
        try:
            token_address = token_data.get("token_address")
            if not token_address:
                logger.warning(f"代币数据缺少地址: {token_data}")
                return

            logger.info(f"开始更新钱包 {wallet.address} 的代币 {token_address} 信息")
            logger.info(f"从链上获取的代币数据: {token_data}")

            # 获取代币元数据
            from chains.kadena.services.token import KadenaTokenService
            token_service = KadenaTokenService()
            metadata = token_service.get_token_metadata(token_address)
            logger.info(f"获取到代币元数据: {metadata}")

            # 检查数据库中是否已有该代币
            token, created = Token.objects.get_or_create(
                address=token_address,
                chain=chain,
                defaults={
                    "name": metadata.get("name", "Unknown"),
                    "symbol": metadata.get("symbol", "Unknown"),
                    "decimals": metadata.get("decimals", 12),  # Kadena 默认精度为 12
                    "logo_url": metadata.get("logo", ""),
                    "is_active": True
                }
            )

            if created:
                logger.info(f"创建了新的代币记录: {token.symbol}")
            else:
                logger.info(f"使用现有的代币记录: {token.symbol} (ID: {token.id})")

            # 更新钱包代币关系
            # 尝试查找现有的钱包代币关系
            existing_tokens = WalletToken.objects.filter(wallet=wallet, token_address=token_address)
            logger.info(f"现有的代币 {token_address} 记录数量: {existing_tokens.count()}")

            # 如果有多个记录，删除多余的
            if existing_tokens.count() > 1:
                logger.warning(f"发现多个代币 {token_address} 记录，将删除多余的")
                for token_record in existing_tokens[1:]:
                    logger.info(f"删除多余的代币记录 ID: {token_record.id}")
                    token_record.delete()

            # 创建或更新钱包代币关系
            wallet_token, created = WalletToken.objects.get_or_create(
                wallet=wallet,
                token_address=token_address,  # 使用代币地址作为 token_address
                defaults={
                    "token": token,
                    "balance": token_data.get("balance", "0"),
                    "is_visible": True
                }
            )

            # 如果已存在，更新余额
            if not created:
                old_balance = wallet_token.balance
                new_balance = token_data.get("balance", "0")

                # 如果新余额为0但旧余额大于0，保留旧余额
                if Decimal(new_balance) == 0 and Decimal(old_balance) > 0:
                    logger.warning(f"\u2757 代币 {token.symbol} 的新余额为0，但旧余额为 {old_balance}，保留旧余额")
                    # 不更新余额，保留旧值
                else:
                    wallet_token.balance = new_balance
                    wallet_token.save()
                    logger.info(f"更新了现有的 {token.symbol} 余额记录，从 {old_balance} 变为 {new_balance}")
            else:
                logger.info(f"创建了新的 {token.symbol} 余额记录，余额为 {token_data.get('balance', '0')}")

            logger.info(f"更新代币 {token.symbol} 成功，余额: {token_data.get('balance', '0')}")
        except Exception as e:
            logger.error(f"更新代币失败: {str(e)}")
            # 不抛出异常，继续处理其他代币