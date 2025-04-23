from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .services.technical_analysis import TechnicalAnalysisService
from .services.token_data_service import TokenDataService
from .services.market_data_service import MarketDataService
import logging
from .models import TokenAnalysisData, Token, Chain
import numpy as np
from typing import Dict, Optional
from datetime import datetime, timezone
import requests
import json
import asyncio
import aiohttp
from asgiref.sync import sync_to_async
import time
import base64
import traceback

logger = logging.getLogger(__name__)

class TechnicalIndicatorsAPIView(APIView):
    """技术指标API视图"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ta_service = TechnicalAnalysisService()
        self.market_service = MarketDataService()
        self.coze_api_key = "pat_wWEutZZ0aGsa0lpxNoOFQjG4UKnh2sSbexsq8wWV6dOcG7d7wXLGuiZ9C70Vlwgl"  # 使用示例代码中的 API key
        self.coze_bot_id = "7496475126733537334"  # 使用示例代码中的 bot_id
        self.coze_api_url = settings.COZE_API_URL

    def _update_analysis_data(self, token: Token, indicators: Dict, current_price: float) -> None:
        """更新代币分析数据

        Args:
            token: Token模型实例
            indicators: 指标数据字典
            current_price: 当前价格
        """
        try:
            # 获取或创建分析数据记录
            analysis_data, created = TokenAnalysisData.objects.get_or_create(
                token=token,
                defaults={
                    'price': current_price,  # 使用当前价格
                    'volume_24h': indicators.get('VWAP'),
                    'price_change_24h': indicators.get('BIAS'),
                    'fear_greed_index': indicators.get('RSI'),
                    'nupl': indicators.get('NUPL'),
                    'exchange_netflow': indicators.get('ExchangeNetflow'),
                    'mayer_multiple': indicators.get('MayerMultiple'),
                    'rsi': indicators.get('RSI'),
                    'macd_line': indicators.get('MACD', {}).get('line'),
                    'macd_signal': indicators.get('MACD', {}).get('signal'),
                    'macd_histogram': indicators.get('MACD', {}).get('histogram'),
                    'bollinger_upper': indicators.get('BollingerBands', {}).get('upper'),
                    'bollinger_middle': indicators.get('BollingerBands', {}).get('middle'),
                    'bollinger_lower': indicators.get('BollingerBands', {}).get('lower'),
                    'bias': indicators.get('BIAS'),
                    'psy': indicators.get('PSY'),
                    'dmi_plus': indicators.get('DMI', {}).get('plus_di'),
                    'dmi_minus': indicators.get('DMI', {}).get('minus_di'),
                    'dmi_adx': indicators.get('DMI', {}).get('adx'),
                    'vwap': indicators.get('VWAP'),
                    'funding_rate': indicators.get('FundingRate')
                }
            )

            # 如果记录已存在，更新数据
            if not created:
                analysis_data.price = current_price  # 使用当前价格
                analysis_data.volume_24h = indicators.get('VWAP')
                analysis_data.price_change_24h = indicators.get('BIAS')
                analysis_data.fear_greed_index = indicators.get('RSI')
                analysis_data.nupl = indicators.get('NUPL')
                analysis_data.exchange_netflow = indicators.get('ExchangeNetflow')
                analysis_data.mayer_multiple = indicators.get('MayerMultiple')
                analysis_data.rsi = indicators.get('RSI')
                analysis_data.macd_line = indicators.get('MACD', {}).get('line')
                analysis_data.macd_signal = indicators.get('MACD', {}).get('signal')
                analysis_data.macd_histogram = indicators.get('MACD', {}).get('histogram')
                analysis_data.bollinger_upper = indicators.get('BollingerBands', {}).get('upper')
                analysis_data.bollinger_middle = indicators.get('BollingerBands', {}).get('middle')
                analysis_data.bollinger_lower = indicators.get('BollingerBands', {}).get('lower')
                analysis_data.bias = indicators.get('BIAS')
                analysis_data.psy = indicators.get('PSY')
                analysis_data.dmi_plus = indicators.get('DMI', {}).get('plus_di')
                analysis_data.dmi_minus = indicators.get('DMI', {}).get('minus_di')
                analysis_data.dmi_adx = indicators.get('DMI', {}).get('adx')
                analysis_data.vwap = indicators.get('VWAP')
                analysis_data.funding_rate = indicators.get('FundingRate')
                analysis_data.save()

            logger.info(f"成功更新代币 {token.symbol} 的分析数据")

        except Exception as e:
            logger.error(f"更新代币分析数据失败: {str(e)}")
            raise

    def _sanitize_float(self, value, min_value=-1000000.0, max_value=1000000.0):
        """确保浮点数值在合理范围内

        Args:
            value: 要检查的值
            min_value: 最小值
            max_value: 最大值

        Returns:
            float: 在范围内的值
        """
        try:
            if value is None:
                return 0.0

            float_value = float(value)

            # 检查是否为无穷大或NaN
            if not np.isfinite(float_value):
                return 0.0

            # 限制数值范围
            return max(min(float_value, max_value), min_value)

        except (ValueError, TypeError):
            return 0.0

    def _sanitize_indicators(self, indicators):
        """确保所有指标值都在合理范围内

        Args:
            indicators: 指标字典

        Returns:
            dict: 处理后的指标字典
        """
        try:
            # 处理简单数值
            for key in ['RSI', 'BIAS', 'PSY', 'VWAP', 'ExchangeNetflow', 'NUPL', 'MayerMultiple', 'FundingRate']:
                if key in indicators:
                    indicators[key] = self._sanitize_float(indicators[key])

            # 处理MACD
            if 'MACD' in indicators:
                macd = indicators['MACD']
                macd['line'] = self._sanitize_float(macd.get('line'), -10000.0, 10000.0)
                macd['signal'] = self._sanitize_float(macd.get('signal'), -10000.0, 10000.0)
                macd['histogram'] = self._sanitize_float(macd.get('histogram'), -10000.0, 10000.0)

            # 处理布林带
            if 'BollingerBands' in indicators:
                bb = indicators['BollingerBands']
                bb['upper'] = self._sanitize_float(bb.get('upper'), 0.0, 1000000.0)
                bb['middle'] = self._sanitize_float(bb.get('middle'), 0.0, 1000000.0)
                bb['lower'] = self._sanitize_float(bb.get('lower'), 0.0, 1000000.0)

            # 处理DMI
            if 'DMI' in indicators:
                dmi = indicators['DMI']
                dmi['plus_di'] = self._sanitize_float(dmi.get('plus_di'), 0.0, 100.0)
                dmi['minus_di'] = self._sanitize_float(dmi.get('minus_di'), 0.0, 100.0)
                dmi['adx'] = self._sanitize_float(dmi.get('adx'), 0.0, 100.0)

            return indicators

        except Exception as e:
            logger.error(f"处理指标数据时出错: {str(e)}")
            return {}

    async def _get_coze_analysis(self, symbol: str, indicators: Dict) -> Dict:
        """异步获取 Coze 分析报告"""
        try:
            # 获取市场数据
            market_data = await sync_to_async(self.market_service.get_market_data)(symbol)
            if not market_data:
                logger.error("无法获取市场数据")
                return {'analysis': '无法获取市场数据'}

            # 获取或创建 Chain 记录
            chain, _ = await sync_to_async(Chain.objects.get_or_create)(
                chain=symbol.replace('USDT', ''),
                defaults={
                    'is_active': True,
                    'is_testnet': False
                }
            )

            # 获取或创建 Token 记录
            token, created = await sync_to_async(Token.objects.get_or_create)(
                symbol=symbol.replace('USDT', '').upper(),
                chain=chain,
                defaults={
                    'name': symbol.replace('USDT', '').upper(),
                    'address': '0x0000000000000000000000000000000000000000',
                    'decimals': 18
                }
            )

            # 更新分析数据
            await sync_to_async(self._update_analysis_data)(token, indicators, market_data['price'])

            # 构建请求URL
            url = f"{self.coze_api_url}/v3/chat"
            
            # 设置请求头
            headers = {
                "Authorization": f"Bearer {self.coze_api_key}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Connection": "keep-alive"
            }

            # 构建消息内容
            additional_messages = [{
                "role": "user",
                "content": json.dumps({
                    "technical_indicators": {
                        "symbol": symbol,
                        "interval": "1d",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "indicators": indicators
                    },
                    "market_data": {
                        "price": market_data['price']
                    }
                }, ensure_ascii=False),
                "content_type": "text"
            }]
            
            # 构建请求体
            payload = {
                "bot_id": self.coze_bot_id,
                "user_id": "crypto_user_001",
                "stream": False,
                "auto_save_history": True,
                "additional_messages": additional_messages
            }
            
            # 打印完整的调试信息
            print("\n==================== DEBUG INFO START ====================")
            print(f"API URL: {url}")
            print(f"API KEY: {self.coze_api_key}")
            print(f"BOT ID: {self.coze_bot_id}")
            print(f"完整请求头: {json.dumps(headers, indent=2, ensure_ascii=False)}")
            print(f"完整请求体: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            print("==================== DEBUG INFO END ====================\n")
            
            # 发送创建对话请求
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    logger.info("=== 创建对话响应详情 ===")
                    logger.info(f"响应状态码: {response.status}")
                    logger.info(f"响应内容: {response_text}")
                    
                    if response.status == 200:
                        try:
                            data = json.loads(response_text)
                            if data.get('code') == 0:
                                chat_id = data.get('data', {}).get('id')
                                conversation_id = data.get('data', {}).get('conversation_id')
                                
                                if not chat_id or not conversation_id:
                                    logger.error("创建对话响应中缺少必要的ID")
                                    return {'analysis': '分析服务暂时不可用'}
                                
                                # 获取对话结果
                                max_retries = 20
                                retry_count = 0
                                
                                while retry_count < max_retries:
                                    # 构建获取对话状态的请求
                                    retrieve_url = f"{self.coze_api_url}/v3/chat/retrieve"
                                    retrieve_params = {
                                        "bot_id": self.coze_bot_id,
                                        "chat_id": chat_id,
                                        "conversation_id": conversation_id
                                    }
                                    
                                    logger.info(f"第 {retry_count + 1} 次尝试获取对话状态")
                                    try:
                                        async with session.get(retrieve_url, headers=headers, params=retrieve_params, timeout=10) as status_response:
                                            status_text = await status_response.text()
                                            logger.info(f"状态响应: {status_text}")
                                            
                                            if status_response.status == 200:
                                                status_data = json.loads(status_text)
                                                if status_data.get('code') == 0:
                                                    data = status_data.get('data', {})
                                                    status = data.get('status')
                                                    
                                                    if status == "completed":
                                                        # 获取消息列表
                                                        message_list_url = f"{self.coze_api_url}/v3/chat/message/list"
                                                        message_list_params = {
                                                            "bot_id": self.coze_bot_id,
                                                            "chat_id": chat_id,
                                                            "conversation_id": conversation_id
                                                        }
                                                        
                                                        async with session.get(message_list_url, headers=headers, params=message_list_params) as messages_response:
                                                            messages_text = await messages_response.text()
                                                            logger.info("==================== 消息列表响应 开始 ====================")
                                                            logger.info(f"状态码: {messages_response.status}")
                                                            logger.info(f"响应头: {dict(messages_response.headers)}")
                                                            logger.info(f"响应内容: {messages_text}")
                                                            logger.info("==================== 消息列表响应 结束 ====================")
                                                            
                                                            if messages_response.status == 200:
                                                                messages_data = json.loads(messages_text)
                                                                if messages_data.get('code') == 0:
                                                                    # 处理消息列表数据
                                                                    if "data" in messages_data and isinstance(messages_data["data"], dict) and "messages" in messages_data["data"]:
                                                                        messages = messages_data["data"]["messages"]
                                                                        logger.info(f"从 data.messages 获取到 {len(messages)} 条消息")
                                                                    elif "data" in messages_data and isinstance(messages_data["data"], list):
                                                                        messages = messages_data["data"]
                                                                        logger.info(f"从 data 列表获取到 {len(messages)} 条消息")
                                                                    else:
                                                                        logger.error("无法解析消息列表格式")
                                                                        logger.error(f"消息数据结构: {json.dumps(messages_data, indent=2, ensure_ascii=False)}")
                                                                        return {'analysis': '分析服务响应格式错误'}
                                                                    
                                                                    # 查找助手的回复
                                                                    logger.info("开始遍历消息列表...")
                                                                    for i, message in enumerate(messages):
                                                                        logger.info(f"消息 {i + 1}:")
                                                                        logger.info(f"角色: {message.get('role')}")
                                                                        logger.info(f"类型: {message.get('type')}")
                                                                        if message.get('role') == 'assistant' and message.get('type') == 'answer':
                                                                            content = message.get('content', '')
                                                                            if content and content != '###':
                                                                                logger.info("找到助手回复:")
                                                                                logger.info("=" * 50)
                                                                                logger.info(content)
                                                                                logger.info("=" * 50)
                                                                                try:
                                                                                    analysis_data = json.loads(content)
                                                                                    logger.info("成功解析为JSON格式")
                                                                                    return {'analysis': analysis_data}
                                                                                except json.JSONDecodeError as e:
                                                                                    logger.error(f"JSON解析错误: {str(e)}")
                                                                                    logger.error("尝试处理非JSON格式的响应...")
                                                                                    # 如果内容包含大括号，可能是格式问题
                                                                                    if '{' in content and '}' in content:
                                                                                        try:
                                                                                            # 尝试提取第一个 { 到最后一个 } 之间的内容
                                                                                            start = content.find('{')
                                                                                            end = content.rfind('}') + 1
                                                                                            json_str = content[start:end]
                                                                                            logger.info("提取的JSON字符串:")
                                                                                            logger.info(json_str)
                                                                                            analysis_data = json.loads(json_str)
                                                                                            logger.info("成功解析提取的JSON")
                                                                                            return {'analysis': analysis_data}
                                                                                        except Exception as e2:
                                                                                            logger.error(f"处理提取的JSON失败: {str(e2)}")
                                                                                    return {'analysis': '分析服务返回格式错误'}
                                                    
                                                    elif status == "failed":
                                                        logger.error("消息处理失败")
                                                        return {'analysis': '分析服务处理失败'}
                                                    
                                    except asyncio.TimeoutError:
                                        logger.error("获取状态请求超时")
                                    except Exception as e:
                                        logger.error(f"获取状态出错: {str(e)}")
                                    
                                    retry_count += 1
                                    wait_time = min(1 + (retry_count * 0.2), 3)  # 最小1秒，最大3秒
                                    logger.info(f"等待 {wait_time} 秒后重试...")
                                    await asyncio.sleep(wait_time)
                                
                                logger.error("获取结果超时")
                                return {'analysis': '分析服务响应超时'}
                            else:
                                logger.error(f"创建对话失败: {data}")
                                return {'analysis': '无法创建分析对话'}
                        except json.JSONDecodeError as e:
                            logger.error(f"解析响应JSON失败: {str(e)}")
                            return {'analysis': '分析服务响应格式错误'}
                    else:
                        logger.error(f"创建对话请求失败: {response.status} - {response_text}")
                        return {'analysis': '分析服务暂时不可用'}
                        
        except Exception as e:
            logger.error(f"获取Coze分析报告失败: {str(e)}")
            logger.error(f"异常类型: {type(e)}")
            logger.error(f"堆栈跟踪: {traceback.format_exc()}")
            return {'analysis': '分析服务暂时不可用'}

    async def _test_coze_auth(self) -> bool:
        """测试Coze API认证"""
        try:
            url = f"{self.coze_api_url}/api/v3/chat"
            
            # 打印原始API密钥
            logger.info(f"原始API密钥: {self.coze_api_key}")
            
            # 设置请求头
            headers = {
                "Authorization": f"Bearer {self.coze_api_key}",  # 使用Bearer前缀，但不使用pat_前缀
                "Content-Type": "application/json"
            }
            
            # 构建最简单的请求体
            payload = {
                "bot_id": self.coze_bot_id,
                "user_id": "crypto_user_001",
                "query": "hi",
                "stream": False
            }
            
            # 打印完整的请求信息
            logger.info("=== 测试认证请求详情 ===")
            logger.info(f"URL: {url}")
            logger.info(f"Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}")
            logger.info(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    logger.info("=== 测试认证响应详情 ===")
                    logger.info(f"响应状态码: {response.status}")
                    logger.info(f"响应头: {dict(response.headers)}")
                    logger.info(f"响应内容: {response_text}")
                    
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"测试认证失败: {str(e)}")
            return False

    async def async_get(self, request, symbol: str):
        """异步处理 GET 请求"""
        try:
            # 首先测试API认证
            auth_ok = await self._test_coze_auth()
            if not auth_ok:
                logger.error("Coze API认证失败")
                return Response({
                    'status': 'error',
                    'message': "Coze API认证失败"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 获取技术指标
            technical_data = await sync_to_async(self.ta_service.get_all_indicators)(symbol)
            if technical_data['status'] == 'error':
                return Response(technical_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            indicators = technical_data['data']['indicators']

            # 获取市场数据
            market_data = await sync_to_async(self.market_service.get_market_data)(symbol)
            if not market_data:
                return Response({
                    'status': 'error',
                    'message': f"无法获取{symbol}的市场数据"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 获取或创建 Chain 记录
            chain, _ = await sync_to_async(Chain.objects.get_or_create)(
                chain=symbol.replace('USDT', ''),
                defaults={
                    'is_active': True,
                    'is_testnet': False
                }
            )

            # 获取或创建 Token 记录
            token, created = await sync_to_async(Token.objects.get_or_create)(
                symbol=symbol.replace('USDT', '').upper(),
                chain=chain,
                defaults={
                    'name': symbol.replace('USDT', '').upper(),
                    'address': '0x0000000000000000000000000000000000000000',
                    'decimals': 18
                }
            )

            # 更新分析数据
            await sync_to_async(self._update_analysis_data)(token, indicators, market_data['price'])

            # 获取Coze分析结果
            coze_analysis = await self._get_coze_analysis(symbol, indicators)

            # 返回完整响应
            return Response({
                'status': 'success',
                'data': {
                    'technical_indicators': technical_data['data'],
                    'market_data': market_data,
                    'coze_analysis': coze_analysis
                }
            })

        except Exception as e:
            logger.error(f"处理请求时发生错误: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, symbol: str):
        """同步入口点，调用异步处理"""
        return asyncio.run(self.async_get(request, symbol))

class TokenDataAPIView(APIView):
    """代币数据API视图"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.token_service = TokenDataService()  # 不传入API密钥，使用免费API

    def get(self, request, token_id: str):
        """获取指定代币的数据

        Args:
            request: HTTP请求对象
            token_id: 代币ID，例如 'bitcoin'

        Returns:
            Response: 包含代币数据的响应
        """
        try:
            # 获取代币数据
            token_data = self.token_service.get_token_data(token_id)

            return Response({
                'status': 'success',
                'data': token_data
            })

        except Exception as e:
            logger.error(f"获取代币数据失败: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)