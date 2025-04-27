from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .services.technical_analysis import TechnicalAnalysisService
from .services.token_data_service import TokenDataService
from .services.market_data_service import MarketDataService
from .services.analysis_report_service import AnalysisReportService
from .models import Token, Chain, AnalysisReport, TechnicalAnalysis, MarketData
from .utils import logger, sanitize_indicators, format_timestamp, parse_timestamp, safe_json_loads
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
import os

class TechnicalIndicatorsAPIView(APIView):
    """技术指标API视图"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ta_service = TechnicalAnalysisService()
        self.market_service = MarketDataService()
        self.report_service = AnalysisReportService()
        self.coze_api_key = os.getenv('COZE_API_KEY')
        self.coze_bot_id = os.getenv('COZE_BOT_ID', '7494575252253720584')
        self.coze_api_url = os.getenv('COZE_API_URL', 'https://api.coze.com')
        
        if not self.coze_api_key:
            raise ValueError("COZE_API_KEY 环境变量未设置")
        if not self.coze_bot_id:
            logger.warning("COZE_BOT_ID 环境变量未设置，使用默认值")
        if not self.coze_api_url:
            logger.warning("COZE_API_URL 环境变量未设置，使用默认值")

    def _init_coze_api(self):
        """初始化 Coze API 配置"""
        if not hasattr(self, 'coze_api_key') or not self.coze_api_key:
            self.coze_api_key = os.getenv('COZE_API_KEY')
            if not self.coze_api_key:
                raise ValueError("COZE_API_KEY 环境变量未设置")
        
        if not hasattr(self, 'coze_bot_id') or not self.coze_bot_id:
            self.coze_bot_id = os.getenv('COZE_BOT_ID', '7494575252253720584')
            if not self.coze_bot_id:
                logger.warning("COZE_BOT_ID 环境变量未设置，使用默认值")
        
        if not hasattr(self, 'coze_api_url') or not self.coze_api_url:
            self.coze_api_url = os.getenv('COZE_API_URL', 'https://api.coze.com')
            if not self.coze_api_url:
                logger.warning("COZE_API_URL 环境变量未设置，使用默认值")

    def _update_analysis_data(self, token: Token, indicators: Dict, current_price: float) -> None:
        """更新技术分析数据"""
        try:
            # 处理指标数据
            indicators = sanitize_indicators(indicators)
            
            # 创建或更新技术分析记录
            technical_analysis, _ = TechnicalAnalysis.objects.update_or_create(
                token=token,
                timestamp=datetime.now(timezone.utc),
                defaults={
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
                    'funding_rate': indicators.get('FundingRate'),
                    'exchange_netflow': indicators.get('ExchangeNetflow'),
                    'nupl': indicators.get('NUPL'),
                    'mayer_multiple': indicators.get('MayerMultiple')
                }
            )

            # 创建或更新市场数据记录
            MarketData.objects.update_or_create(
                token=token,
                timestamp=datetime.now(timezone.utc),
                defaults={
                    'price': current_price,
                    'volume': 0.0,
                    'price_change_24h': 0.0,
                    'price_change_percent_24h': 0.0,
                    'high_24h': 0.0,
                    'low_24h': 0.0
                }
            )

            logger.info(f"成功更新代币 {token.symbol} 的技术分析数据")
            
            return technical_analysis

        except Exception as e:
            logger.error(f"更新代币技术分析数据失败: {str(e)}")
            raise

    async def _get_coze_analysis(self, symbol: str, indicators: Dict, technical_analysis: TechnicalAnalysis) -> Dict:
        """异步获取 Coze 分析报告"""
        try:
            # 初始化 Coze API 配置
            self._init_coze_api()
            
            # 获取市场数据
            market_data = await sync_to_async(self.market_service.get_market_data)(symbol)
            if not market_data:
                logger.error(f"获取市场数据失败: {symbol}")
                return None

            # 构建请求头
            headers = {
                "Authorization": f"Bearer {self.coze_api_key}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Connection": "keep-alive"
            }
            
            # 构建请求体
            additional_messages = [{
                "role": "user",
                "content": json.dumps({
                    "technical_indicators": {
                        "symbol": symbol,
                        "interval": "1d",
                        "timestamp": format_timestamp(datetime.now(timezone.utc)),
                        "indicators": indicators
                    },
                    "market_data": {
                        "price": market_data['price']
                    }
                }, ensure_ascii=False),
                "content_type": "text"
            }]

            payload = {
                "bot_id": self.coze_bot_id,
                "user_id": "crypto_user_001",
                "stream": False,
                "auto_save_history": True,
                "additional_messages": additional_messages
            }

            # 设置超时
            timeout = aiohttp.ClientTimeout(total=30)
            
            # 发送请求创建对话
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.post(
                        f"{self.coze_api_url}/v3/chat",
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Coze API请求失败: {error_text}")
                            return None
                        
                        response_data = await response.json()
                        if response_data.get('code') != 0:
                            logger.error(f"Coze API响应错误: {response_data}")
                            return None

                        data = response_data.get('data', {})
                        chat_id = data.get('id')
                        conversation_id = data.get('conversation_id')

                        if not chat_id or not conversation_id:
                            logger.error("创建对话响应中缺少必要的ID")
                            return None

                        # 轮询获取对话结果
                        max_retries = 20
                        retry_count = 0
                        retry_interval = 1  # 初始重试间隔（秒）
                        
                        while retry_count < max_retries:
                            try:
                                # 构建获取对话状态的请求
                                retrieve_url = f"{self.coze_api_url}/v3/chat/retrieve"
                                retrieve_params = {
                                    "bot_id": self.coze_bot_id,
                                    "chat_id": chat_id,
                                    "conversation_id": conversation_id
                                }
                                
                                logger.info(f"第 {retry_count + 1} 次尝试获取对话状态")
                                
                                async with session.get(retrieve_url, headers=headers, params=retrieve_params) as status_response:
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
                                                    logger.info(f"消息列表响应: {messages_text}")
                                                    
                                                    if messages_response.status == 200:
                                                        messages_data = json.loads(messages_text)
                                                        if messages_data.get('code') == 0:
                                                            # 处理消息列表数据
                                                            if "data" in messages_data and isinstance(messages_data["data"], dict) and "messages" in messages_data["data"]:
                                                                messages = messages_data["data"]["messages"]
                                                            elif "data" in messages_data and isinstance(messages_data["data"], list):
                                                                messages = messages_data["data"]
                                                            else:
                                                                logger.error("无法解析消息列表格式")
                                                                return None

                                                            # 查找助手的回复
                                                            for message in messages:
                                                                if message.get('role') == 'assistant' and message.get('type') == 'answer':
                                                                    content = message.get('content', '')
                                                                    if content and content != '###':
                                                                        try:
                                                                            if content.startswith('```json'):
                                                                                content = content[7:-3].strip()
                                                                            analysis_data = json.loads(content)
                                                                            return analysis_data
                                                                        except json.JSONDecodeError as e:
                                                                            logger.error(f"解析JSON失败: {str(e)}")
                                                                            return None
                                
                                # 如果没有获取到完整结果，继续重试
                                await asyncio.sleep(retry_interval)
                                retry_interval = min(retry_interval * 1.5, 5)  # 指数退避，最大5秒
                                retry_count += 1
                                
                            except asyncio.TimeoutError:
                                logger.error("获取对话状态超时")
                                retry_count += 1
                                await asyncio.sleep(retry_interval)
                            except Exception as e:
                                logger.error(f"获取对话状态时发生错误: {str(e)}")
                                retry_count += 1
                                await asyncio.sleep(retry_interval)

                        logger.error("所有重试失败，无法获取对话结果")
                        return None
                        
                except asyncio.TimeoutError:
                    logger.error("Coze API 请求超时")
                    return None
                except aiohttp.ClientError as e:
                    logger.error(f"Coze API 请求错误: {str(e)}")
                    return None

        except Exception as e:
            logger.error(f"获取Coze分析时发生错误: {str(e)}")
            return None

    async def _test_coze_auth(self) -> bool:
        """测试Coze API认证"""
        try:
            url = f"{self.coze_api_url}/v3/chat"
            
            # 设置请求头
            headers = {
                "Authorization": f"Bearer {self.coze_api_key}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Connection": "keep-alive"
            }
            
            # 构建最简单的请求体
            payload = {
                "bot_id": self.coze_bot_id,
                "user_id": "crypto_user_001",
                "stream": False,
                "auto_save_history": True,
                "additional_messages": [
                    {
                        "role": "user",
                        "content": "hi",
                        "content_type": "text"
                    }
                ]
            }
            
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
            # 检查是否需要强制刷新
            force_refresh = request.query_params.get('force_refresh', 'false').lower() == 'true'
            
            # 尝试从数据库获取最新的分析报告
            try:
                # 获取或创建默认链
                chain, _ = await sync_to_async(Chain.objects.get_or_create)(
                    chain=symbol.replace('USDT', ''),
                    defaults={
                        'is_active': True,
                        'is_testnet': False
                    }
                )

                # 获取或创建代币
                token, _ = await sync_to_async(Token.objects.get_or_create)(
                    symbol=symbol.replace('USDT', '').upper(),
                    chain=chain,
                    defaults={
                        'name': symbol.replace('USDT', '').upper(),
                        'address': '0x0000000000000000000000000000000000000000',
                        'decimals': 18
                    }
                )

                latest_report = await sync_to_async(AnalysisReport.objects.filter(token=token).order_by('-timestamp').first)()
                
                if latest_report and not force_refresh:
                    # 获取相关的技术分析数据
                    technical_analysis = await sync_to_async(TechnicalAnalysis.objects.filter(token=token).order_by('-timestamp').first)()
                    market_data = await sync_to_async(MarketData.objects.filter(token=token).order_by('-timestamp').first)()
                    
                    # 构建响应数据
                    response_data = {
                        'status': 'success',
                        'data': {
                            'trend_analysis': {
                                'probabilities': {
                                    'up': int(latest_report.trend_up_probability),
                                    'sideways': int(latest_report.trend_sideways_probability),
                                    'down': int(latest_report.trend_down_probability)
                                },
                                'summary': latest_report.trend_summary
                            },
                            'indicators_analysis': {
                                'RSI': {
                                    'value': float(technical_analysis.rsi) if technical_analysis and technical_analysis.rsi is not None else None,
                                    'analysis': latest_report.rsi_analysis,
                                    'support_trend': latest_report.rsi_support_trend
                                },
                                'MACD': {
                                    'value': {
                                        'line': float(technical_analysis.macd_line) if technical_analysis and technical_analysis.macd_line is not None else None,
                                        'signal': float(technical_analysis.macd_signal) if technical_analysis and technical_analysis.macd_signal is not None else None,
                                        'histogram': float(technical_analysis.macd_histogram) if technical_analysis and technical_analysis.macd_histogram is not None else None
                                    },
                                    'analysis': latest_report.macd_analysis,
                                    'support_trend': latest_report.macd_support_trend
                                },
                                'BollingerBands': {
                                    'value': {
                                        'upper': float(technical_analysis.bollinger_upper) if technical_analysis and technical_analysis.bollinger_upper is not None else None,
                                        'middle': float(technical_analysis.bollinger_middle) if technical_analysis and technical_analysis.bollinger_middle is not None else None,
                                        'lower': float(technical_analysis.bollinger_lower) if technical_analysis and technical_analysis.bollinger_lower is not None else None
                                    },
                                    'analysis': latest_report.bollinger_analysis,
                                    'support_trend': latest_report.bollinger_support_trend
                                },
                                'BIAS': {
                                    'value': float(technical_analysis.bias) if technical_analysis and technical_analysis.bias is not None else None,
                                    'analysis': latest_report.bias_analysis,
                                    'support_trend': latest_report.bias_support_trend
                                },
                                'PSY': {
                                    'value': float(technical_analysis.psy) if technical_analysis and technical_analysis.psy is not None else None,
                                    'analysis': latest_report.psy_analysis,
                                    'support_trend': latest_report.psy_support_trend
                                },
                                'DMI': {
                                    'value': {
                                        'plus_di': float(technical_analysis.dmi_plus) if technical_analysis and technical_analysis.dmi_plus is not None else None,
                                        'minus_di': float(technical_analysis.dmi_minus) if technical_analysis and technical_analysis.dmi_minus is not None else None,
                                        'adx': float(technical_analysis.dmi_adx) if technical_analysis and technical_analysis.dmi_adx is not None else None
                                    },
                                    'analysis': latest_report.dmi_analysis,
                                    'support_trend': latest_report.dmi_support_trend
                                },
                                'VWAP': {
                                    'value': float(technical_analysis.vwap) if technical_analysis and technical_analysis.vwap is not None else None,
                                    'analysis': latest_report.vwap_analysis,
                                    'support_trend': latest_report.vwap_support_trend
                                },
                                'FundingRate': {
                                    'value': float(technical_analysis.funding_rate) if technical_analysis and technical_analysis.funding_rate is not None else None,
                                    'analysis': latest_report.funding_rate_analysis,
                                    'support_trend': latest_report.funding_rate_support_trend
                                },
                                'ExchangeNetflow': {
                                    'value': float(technical_analysis.exchange_netflow) if technical_analysis and technical_analysis.exchange_netflow is not None else None,
                                    'analysis': latest_report.exchange_netflow_analysis,
                                    'support_trend': latest_report.exchange_netflow_support_trend
                                },
                                'NUPL': {
                                    'value': float(technical_analysis.nupl) if technical_analysis and technical_analysis.nupl is not None else None,
                                    'analysis': latest_report.nupl_analysis,
                                    'support_trend': latest_report.nupl_support_trend
                                },
                                'MayerMultiple': {
                                    'value': float(technical_analysis.mayer_multiple) if technical_analysis and technical_analysis.mayer_multiple is not None else None,
                                    'analysis': latest_report.mayer_multiple_analysis,
                                    'support_trend': latest_report.mayer_multiple_support_trend
                                }
                            },
                            'trading_advice': {
                                'action': latest_report.trading_action,
                                'reason': latest_report.trading_reason,
                                'entry_price': float(latest_report.entry_price),
                                'stop_loss': float(latest_report.stop_loss),
                                'take_profit': float(latest_report.take_profit)
                            },
                            'risk_assessment': {
                                'level': latest_report.risk_level,
                                'score': int(latest_report.risk_score),
                                'details': latest_report.risk_details
                            }
                        }
                    }
                    return Response(response_data)
            except Token.DoesNotExist:
                logger.info(f"未找到代币 {symbol} 的记录")
                return Response({
                    'status': 'error',
                    'message': f"未找到代币 {symbol} 的记录，请先使用 force_refresh=true 参数刷新数据"
                }, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                logger.error(f"从数据库读取数据时发生错误: {str(e)}")
                return Response({
                    'status': 'error',
                    'message': f"读取数据失败: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 如果需要强制刷新，则执行刷新流程
            if force_refresh:
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
                technical_analysis = await sync_to_async(self._update_analysis_data)(token, indicators, market_data['price'])

                # 获取Coze分析结果
                coze_analysis = await self._get_coze_analysis(symbol, indicators, technical_analysis)
                if not coze_analysis:
                    return Response({
                        'status': 'error',
                        'message': "获取分析结果失败"
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # 返回完整响应
                return Response({
                    'status': 'success',
                    'data': coze_analysis
                })

            return Response({
                'status': 'error',
                'message': "未找到数据，请使用 force_refresh=true 参数刷新数据"
            }, status=status.HTTP_404_NOT_FOUND)

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

def _sanitize_indicators(self, indicators):
    """确保所有指标值都在合理范围内

    Args:
        indicators: 指标字典

    Returns:
        dict: 处理后的指标字典
    """
    try:
        # 处理简单数值
        for key in ['RSI', 'BIAS', 'PSY', 'VWAP', 'ExchangeNetflow', 'FundingRate']:
            if key in indicators:
                indicators[key] = self._sanitize_float(indicators[key])
                
        # 特殊处理 NUPL
        if 'NUPL' in indicators:
            nupl_value = indicators['NUPL']
            try:
                nupl_float = float(nupl_value)
                if np.isnan(nupl_float) or np.isinf(nupl_float):
                    indicators['NUPL'] = 0.0
                else:
                    indicators['NUPL'] = max(min(nupl_float, 100.0), -100.0)
            except (ValueError, TypeError):
                indicators['NUPL'] = 0.0
                
        # 特殊处理 MayerMultiple
        if 'MayerMultiple' in indicators:
            mm_value = indicators['MayerMultiple']
            try:
                mm_float = float(mm_value)
                if np.isnan(mm_float) or np.isinf(mm_float):
                    indicators['MayerMultiple'] = 1.0
                else:
                    indicators['MayerMultiple'] = max(min(mm_float, 5.0), 0.1)
            except (ValueError, TypeError):
                indicators['MayerMultiple'] = 1.0

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

class TechnicalIndicatorsDataAPIView(APIView):
    """技术指标数据API视图"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ta_service = TechnicalAnalysisService()
        self.market_service = MarketDataService()

    async def async_get(self, request, symbol: str):
        """异步处理 GET 请求"""
        try:
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

            # 格式化指标数据
            formatted_indicators = {
                'rsi': float(indicators.get('RSI', 0)),
                'macd_line': float(indicators.get('MACD', {}).get('line', 0)),
                'macd_signal': float(indicators.get('MACD', {}).get('signal', 0)),
                'macd_histogram': float(indicators.get('MACD', {}).get('histogram', 0)),
                'bollinger_upper': float(indicators.get('BollingerBands', {}).get('upper', 0)),
                'bollinger_middle': float(indicators.get('BollingerBands', {}).get('middle', 0)),
                'bollinger_lower': float(indicators.get('BollingerBands', {}).get('lower', 0)),
                'bias': float(indicators.get('BIAS', 0)),
                'psy': float(indicators.get('PSY', 0)),
                'dmi_plus': float(indicators.get('DMI', {}).get('plus_di', 0)),
                'dmi_minus': float(indicators.get('DMI', {}).get('minus_di', 0)),
                'dmi_adx': float(indicators.get('DMI', {}).get('adx', 0)),
                'vwap': float(indicators.get('VWAP', 0)),
                'funding_rate': float(indicators.get('FundingRate', 0)),
                'exchange_netflow': float(indicators.get('ExchangeNetflow', 0)),
                'nupl': float(indicators.get('NUPL', 0)),
                'mayer_multiple': float(indicators.get('MayerMultiple', 0))
            }

            return Response({
                'status': 'success',
                'data': {
                    'symbol': symbol,
                    'price': market_data['price'],
                    'indicators': formatted_indicators
                }
            })

        except Exception as e:
            logger.error(f"获取技术指标数据失败: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, symbol: str):
        """同步入口点，调用异步处理"""
        return asyncio.run(self.async_get(request, symbol))
