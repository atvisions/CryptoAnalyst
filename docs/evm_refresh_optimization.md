# EVM 链刷新逻辑优化

本文档详细介绍了钱包系统中 EVM 链刷新逻辑的优化方法，包括缓存策略、批量查询、异步处理和数据库优化等方面。

## 目录

- [整体架构](#整体架构)
- [优化前的问题](#优化前的问题)
- [优化策略](#优化策略)
  - [缓存优化](#缓存优化)
  - [批量查询优化](#批量查询优化)
  - [异步处理优化](#异步处理优化)
  - [数据库操作优化](#数据库操作优化)
- [代码实现](#代码实现)
- [性能对比](#性能对比)
- [后续优化建议](#后续优化建议)

## 整体架构

钱包系统的 EVM 链刷新逻辑主要包括以下几个部分：

1. **钱包余额查询**：获取钱包中所有代币的余额
2. **代币元数据获取**：获取代币的名称、符号、小数位等信息
3. **代币价格查询**：获取代币的当前价格和24小时变化率
4. **数据库更新**：将获取到的数据更新到数据库中

整体流程如下：

```
用户请求 → 获取钱包余额 → 获取代币元数据 → 获取代币价格 → 更新数据库 → 返回响应
```

## 优化前的问题

优化前，系统存在以下几个主要问题：

1. **响应时间长**：刷新一个钱包需要16.54秒，用户体验差
2. **重复查询**：即使代币余额为0，也会查询其价格
3. **串行处理**：所有操作都是串行执行，效率低下
4. **缓存策略不合理**：缓存时间不合理，导致缓存命中率低
5. **数据库操作频繁**：每次更新都会触发数据库操作

## 优化策略

### 缓存优化

针对不同类型的数据，采用不同的缓存策略：

1. **钱包余额列表**：
   - 缓存时间：5分钟
   - 缓存键：`{chain}:{wallet_address}:all_tokens`

2. **原生代币余额**：
   - 缓存时间：5分钟
   - 缓存键：`{chain}:{wallet_address}:native_balance`

3. **代币余额**：
   - 余额为0的代币：24小时
   - 有余额的代币：5分钟
   - 缓存键：`{chain}:{wallet_address}:{token_address}:balance`

4. **代币价格**：
   - 缓存时间：1分钟
   - 缓存键：`{chain}_token_price_{token_address}`

5. **代币元数据**：
   - 缓存时间：24小时
   - 缓存键：`{chain}:token:{token_address}:metadata`

### 批量查询优化

使用批量查询和并行处理，提高查询效率：

1. **批量余额查询**：
   - 使用线程池并行查询多个代币的余额
   - 每批处理10个代币，最多5个并行线程

2. **批量价格查询**：
   - 一次性查询所有有余额的代币的价格
   - 使用异步IO提高效率

### 异步处理优化

将价格更新操作从主请求流程中分离出来，使用异步任务处理：

1. **立即返回余额数据**：
   - API立即返回缓存的余额数据
   - 用户无需等待价格更新

2. **后台更新价格**：
   - 使用Celery任务异步更新价格
   - 不阻塞API响应

### 数据库操作优化

优化数据库操作，减少不必要的更新：

1. **条件更新**：
   - 只在价格有显著变化时更新数据库（变化超过0.5%）
   - 对于价格为0的代币，始终更新价格

2. **批量更新**：
   - 使用`bulk_update`批量更新代币价格
   - 减少数据库交互次数

3. **事务处理**：
   - 使用事务确保数据一致性
   - 避免部分更新导致的数据不一致

## 代码实现

### 1. 批量余额查询

```python
def batch_query_balances(addresses, batch_size=10):
    results = {}
    uncached_addresses = []
    
    # 首先检查缓存
    for addr in addresses:
        balance_cache_key = f"{self.chain}:{wallet_address}:{addr}:balance"
        cached_balance = cache.get(balance_cache_key)
        if cached_balance is not None:
            print(f"从缓存中获取代币 {addr} 的余额: {cached_balance}")
            if cached_balance > 0:
                results[addr] = cached_balance
        else:
            uncached_addresses.append(addr)
    
    # 如果所有地址都有缓存，直接返回
    if not uncached_addresses:
        print(f"所有 {len(addresses)} 个代币余额都从缓存中获取")
        return results
        
    print(f"需要从链上查询 {len(uncached_addresses)} 个代币的余额")
    
    # 使用线程池并行查询未缓存的地址
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # 分批处理，每批10个代币
        for i in range(0, len(uncached_addresses), batch_size):
            batch = uncached_addresses[i:i+batch_size]
            futures = {executor.submit(self.get_token_balance, addr, wallet_address): addr for addr in batch}
            for future in concurrent.futures.as_completed(futures):
                addr = futures[future]
                try:
                    balance = future.result()
                    
                    # 缓存代币余额
                    balance_cache_key = f"{self.chain}:{wallet_address}:{addr}:balance"
                    # 如果余额为0，使用更长的缓存时间
                    cache_timeout = 60 * 60 * 24 if balance == 0 else 60 * 5  # 24小时或者5分钟
                    cache.set(balance_cache_key, balance, cache_timeout)
                    
                    if balance > 0:
                        results[addr] = balance
                except Exception as e:
                    logger.error(f"批量查询代币 {addr} 余额失败: {e}")
    return results
```

### 2. 异步价格更新

```python
@shared_task
def update_wallet_token_prices(wallet_id):
    """
    异步更新钱包代币的价格信息
    """
    try:
        wallet = Wallet.objects.get(id=wallet_id)
        logger.info(f"开始异步更新钱包 {wallet.address} ({wallet.chain}) 的代币价格")
        
        # 获取钱包的所有代币
        wallet_tokens = WalletToken.objects.filter(wallet_id=wallet_id, token_address__isnull=False, token_address__gt="")
        
        # 收集所有需要查询价格的代币地址
        token_addresses = [wt.token_address for wt in wallet_tokens]
        
        if not token_addresses:
            logger.info(f"钱包 {wallet.address} 没有需要更新价格的代币")
            return True
            
        # 根据链类型选择相应的服务
        if wallet.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO']:
            from chains.evm.services.balance import EVMBalanceService
            balance_service = EVMBalanceService(wallet.chain)
            
        # 批量获取代币价格
        prices = asyncio.run(balance_service._get_token_prices(token_addresses))
        
        # 收集需要更新的代币
        tokens_to_update = []
        updated_count = 0
        
        for wallet_token in wallet_tokens:
            token_address = wallet_token.token_address
            if token_address in prices and wallet_token.token:
                price_data = prices[token_address]
                token = wallet_token.token
                
                # 获取新的价格数据
                new_price = price_data.get("current_price", 0)
                new_change = price_data.get("price_change_24h", 0)
                
                # 只在价格有显著变化时更新数据库
                current_price = float(token.current_price_usd or 0)
                price_change = float(token.price_change_24h or 0)
                
                # 如果价格变化超过0.5%或者价格为0，则更新
                if current_price == 0 or new_price == 0 or abs(new_price - current_price) / max(current_price, 0.000001) > 0.005 or abs(new_change - price_change) > 0.5:
                    token.current_price_usd = new_price
                    token.price_change_24h = new_change
                    token.last_updated = timezone.now()
                    tokens_to_update.append(token)
                    updated_count += 1
        
        # 批量更新代币价格
        if tokens_to_update:
            from django.db import transaction
            with transaction.atomic():
                # 使用bulk_update批量更新
                Token.objects.bulk_update(tokens_to_update, ['current_price_usd', 'price_change_24h', 'last_updated'])
                logger.info(f"成功批量更新 {len(tokens_to_update)} 个代币的价格")
        
        logger.info(f"成功更新钱包 {wallet.address} 的 {updated_count}/{len(token_addresses)} 个代币价格")
        return True
    except Exception as e:
        logger.error(f"异步更新钱包代币价格失败: {str(e)}")
        return False
```

### 3. API视图优化

```python
@action(detail=True, methods=['post'])
def refresh_balances(self, request, pk=None):
    """手动刷新钱包代币余额和元数据，使用异步方式更新价格"""
    try:
        # 尝试获取钱包对象
        try:
            from wallets.models import Wallet
            wallet = Wallet.objects.get(id=pk)
        except Wallet.DoesNotExist:
            return Response({'error': f'钱包 ID {pk} 不存在'}, status=status.HTTP_404_NOT_FOUND)
            
        # 根据钱包链类型调用相应的服务更新余额
        if wallet.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO']:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Refreshing balances for wallet {wallet.address} ({wallet.chain})")

            from chains.evm.services.balance import EVMBalanceService
            balance_service = EVMBalanceService(wallet.chain)

            # 获取所有代币余额
            token_balances = balance_service.get_all_token_balances(wallet.address, wallet_id=wallet.id)

            # 更新数据库中的代币余额
            from wallets.models import WalletToken, Token, Chain

            # 获取链对象
            chain_obj, _ = Chain.objects.get_or_create(chain=wallet.chain, defaults={'is_active': True})

            for token_balance in token_balances:
                token_address = token_balance.get('token_address', '')
                balance = token_balance.get('balance', '0')
                symbol = token_balance.get('symbol', '')
                name = token_balance.get('name', '')
                decimals = token_balance.get('decimals', 18)
                logo = token_balance.get('logo', '')

                # 更新或创建 Token 记录
                if token_address:
                    token, created = Token.objects.get_or_create(
                        chain=chain_obj,
                        address=token_address,
                        defaults={
                            'symbol': symbol,
                            'name': name,
                            'decimals': decimals,
                            'logo_url': logo,
                            'is_active': True
                        }
                    )
                else:
                    # 对于原生代币，使用特殊处理
                    token, created = Token.objects.get_or_create(
                        chain=chain_obj,
                        address='',
                        defaults={
                            'symbol': symbol or wallet.chain.split('_')[0],
                            'name': name or f"{wallet.chain.split('_')[0]} Coin",
                            'decimals': decimals,
                            'logo_url': logo,
                            'is_active': True
                        }
                    )

                # 更新或创建 WalletToken 记录
                wallet_token, created = WalletToken.objects.get_or_create(
                    wallet=wallet,
                    token_address=token_address,
                    defaults={
                        'token': token,
                        'balance': balance,
                        'is_visible': True
                    }
                )

                if not created:
                    wallet_token.balance = balance
                    wallet_token.token = token
                    wallet_token.save()

            # 查询钱包代币数量
            from wallets.models import WalletToken, Token
            wallet_tokens = WalletToken.objects.filter(wallet=wallet)
            token_count = wallet_tokens.count()
            
            # 异步更新代币价格
            from wallets.tasks import update_wallet_token_prices
            update_wallet_token_prices.delay(wallet.id)
            logger.info(f"已开始异步更新钱包 {wallet.address} 的代币价格")

            # 返回更详细的响应，包含钱包地址和刷新时间
            from datetime import datetime
            refresh_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            return Response({
                'message': f'钱包 {wallet.address} 的代币余额已成功更新',
                'wallet_address': wallet.address,
                'refresh_time': refresh_time,
                'token_count': token_count,
                'status': 'success'
            })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error refreshing wallet balances: {str(e)}")
        return Response({'error': f'更新钱包余额失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

## 性能对比

### 优化前（原始版本）
- 总耗时：16.54秒
- 处理代币数据耗时：11.51秒（69.6%）
- 获取原生代币余额耗时：3.56秒
- 获取代币余额耗时：1.47秒（8.9%）
- 查询了8个余额为0的代币

### 优化后（当前版本）
- 首次请求总耗时：5.95秒（减少了64%）
- 缓存命中后总耗时：接近0秒（减少了99.9%）
- 处理代币数据耗时：0.02秒（减少了99.8%）
- 获取原生代币余额耗时：3.44秒
- 获取代币余额耗时：2.48秒（首次）/ 1.42秒（后续）
- 跳过了余额为0的代币查询

## 后续优化建议

1. **进一步优化原生代币余额获取**：
   - 使用更快的RPC节点
   - 实现批量RPC调用

2. **实现更智能的缓存策略**：
   - 根据用户行为调整缓存时间
   - 对于活跃用户，使用更短的缓存时间

3. **添加WebSocket支持**：
   - 安装`channels`和`channels-redis`包
   - 实现实时价格更新通知

4. **优化前端体验**：
   - 实现轮询机制，定期获取最新价格
   - 添加加载指示器，提示用户价格正在更新

5. **监控系统性能**：
   - 监控API响应时间
   - 监控Celery任务执行情况
   - 监控缓存命中率
