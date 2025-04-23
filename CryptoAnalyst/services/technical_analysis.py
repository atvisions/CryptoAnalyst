import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
from CryptoAnalyst.services.binance_api import BinanceAPI

logger = logging.getLogger(__name__)

class TechnicalAnalysisService:
    """技术分析服务类"""
    
    def __init__(self):
        """初始化技术分析服务"""
        self.binance_api = BinanceAPI()
        logger.info("技术分析服务初始化完成")
    
    def get_all_indicators(self, symbol: str, interval: str = '1d', limit: int = 1000) -> Dict:
        """
        获取所有技术指标
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            interval: K线间隔，例如 '1d', '4h', '1h'
            limit: 获取的K线数量，默认为1000（确保有足够数据计算梅耶倍数）
            
        Returns:
            Dict: 包含所有技术指标的字典
        """
        try:
            # 获取历史K线数据
            klines = self.binance_api.get_historical_klines(symbol, interval, '1000 days ago UTC')
            if not klines:
                logger.warning(f"无法获取{symbol}的K线数据")
                return {}
                
            # 转换为DataFrame
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
            
            # 打印原始K线数据
            logger.info(f"获取到的K线数据:")
            logger.info(f"数据长度: {len(df)}")
            logger.info(f"时间范围: {df['timestamp'].iloc[0]} 到 {df['timestamp'].iloc[-1]}")
            logger.info(f"价格范围: {df['close'].min()} 到 {df['close'].max()}")
            
            # 确保数据类型正确
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            # 按时间排序
            df = df.sort_values('timestamp')
            
            # 检查数据是否连续
            df['time_diff'] = df['timestamp'].diff()
            expected_diff = pd.Timedelta(days=1) if interval == '1d' else pd.Timedelta(hours=1) if interval == '1h' else pd.Timedelta(minutes=1)
            missing_data = df[df['time_diff'] > expected_diff * 1.5]  # 允许50%的时间差
            
            if not missing_data.empty:
                logger.warning(f"发现数据缺失: {len(missing_data)} 个时间点")
                for _, row in missing_data.iterrows():
                    logger.warning(f"缺失数据时间点: {row['timestamp']}")
            
            # 检查数据长度
            if len(df) < 200:
                logger.warning(f"数据长度不足200天，无法计算NUPL和MayerMultiple")
                nupl = 0.0
                mayer_multiple = 1.0
            else:
                nupl = self._calculate_nupl(df)
                mayer_multiple = self._calculate_mayer_multiple(df)
            
            # 计算技术指标
            indicators = {
                'RSI': self._calculate_rsi(df),
                'MACD': self._calculate_macd(df),
                'BollingerBands': self._calculate_bollinger_bands(df),
                'BIAS': self._calculate_bias(df),
                'PSY': self._calculate_psy(df),
                'DMI': self._calculate_dmi(df),
                'VWAP': self._calculate_vwap(df),
                'FundingRate': self._get_funding_rate(symbol),
                'ExchangeNetflow': self._calculate_exchange_netflow(df),
                'NUPL': nupl,
                'MayerMultiple': mayer_multiple
            }
            
            return {
                'status': 'success',
                'data': {
                    'symbol': symbol,
                    'interval': interval,
                    'timestamp': datetime.utcnow().isoformat(),
                    'indicators': indicators
                }
            }
            
        except Exception as e:
            logger.error(f"计算技术指标时发生错误: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算RSI指标
        
        Args:
            df: 包含价格数据的DataFrame
            period: RSI周期，默认为14
            
        Returns:
            float: 当前RSI值
        """
        try:
            # 计算价格变化
            delta = df['close'].diff()
            
            # 分离上涨和下跌
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            # 计算相对强度
            rs = gain / loss
            
            # 计算RSI
            rsi = 100 - (100 / (1 + rs))
            
            # 获取最新的RSI值并验证
            rsi_value = float(rsi.iloc[-1])
            
            # 限制数值范围
            rsi_value = max(min(rsi_value, 100.0), 0.0)
            
            return round(rsi_value, 2)
            
        except Exception as e:
            logger.error(f"计算RSI指标时发生错误: {str(e)}")
            return 50.0  # 默认值
    
    def _calculate_macd(self, df: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict:
        """计算MACD指标
        
        Args:
            df: 包含价格数据的DataFrame
            fast_period: 快线周期，默认为12
            slow_period: 慢线周期，默认为26
            signal_period: 信号线周期，默认为9
            
        Returns:
            Dict: 包含MACD线、信号线和柱状图的值
        """
        try:
            # 计算快线和慢线的EMA
            exp1 = df['close'].ewm(span=fast_period, adjust=False).mean()
            exp2 = df['close'].ewm(span=slow_period, adjust=False).mean()
            
            # 计算MACD线
            macd_line = exp1 - exp2
            
            # 计算信号线
            signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
            
            # 计算MACD柱状图
            histogram = macd_line - signal_line
            
            # 获取最新的值并验证
            macd_value = float(macd_line.iloc[-1])
            signal_value = float(signal_line.iloc[-1])
            hist_value = float(histogram.iloc[-1])
            
            # 限制数值范围
            macd_value = max(min(macd_value, 10000.0), -10000.0)
            signal_value = max(min(signal_value, 10000.0), -10000.0)
            hist_value = max(min(hist_value, 10000.0), -10000.0)
            
            return {
                'line': round(macd_value, 2),
                'signal': round(signal_value, 2),
                'histogram': round(hist_value, 2)
            }
            
        except Exception as e:
            logger.error(f"计算MACD指标时发生错误: {str(e)}")
            return {
                'line': 0.0,
                'signal': 0.0,
                'histogram': 0.0
            }
    
    def _calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Dict:
        """计算布林带指标
        
        Args:
            df: 包含价格数据的DataFrame
            period: 移动平均周期，默认为20
            std_dev: 标准差倍数，默认为2
            
        Returns:
            Dict: 包含上轨、中轨和下轨的值
        """
        try:
            # 获取最新的价格数据
            current_price = float(df['close'].iloc[-1])
            
            # 计算中轨（20日移动平均线）
            middle_band = df['close'].rolling(window=period).mean()
            
            # 计算标准差
            std = df['close'].rolling(window=period).std()
            
            # 计算上轨和下轨
            upper_band = middle_band + (std * std_dev)
            lower_band = middle_band - (std * std_dev)
            
            # 获取最新的值并验证
            upper_value = float(upper_band.iloc[-1])
            middle_value = float(middle_band.iloc[-1])
            lower_value = float(lower_band.iloc[-1])
            
            # 验证值是否有效
            if pd.isna(upper_value) or not np.isfinite(upper_value):
                upper_value = current_price * 1.02
            if pd.isna(middle_value) or not np.isfinite(middle_value):
                middle_value = current_price
            if pd.isna(lower_value) or not np.isfinite(lower_value):
                lower_value = current_price * 0.98
            
            # 限制数值范围
            upper_value = max(min(upper_value, current_price * 1.5), current_price * 1.02)
            middle_value = max(min(middle_value, current_price * 1.2), current_price * 0.8)
            lower_value = max(min(lower_value, current_price * 0.98), current_price * 0.5)
            
            return {
                'upper': round(upper_value, 2),
                'middle': round(middle_value, 2),
                'lower': round(lower_value, 2)
            }
            
        except Exception as e:
            logger.error(f"计算布林带指标时发生错误: {str(e)}")
            current_price = float(df['close'].iloc[-1])
            return {
                'upper': round(current_price * 1.02, 2),
                'middle': round(current_price, 2),
                'lower': round(current_price * 0.98, 2)
            }
    
    def _calculate_bias(self, df: pd.DataFrame, period: int = 6) -> float:
        """计算乖离率指标
        
        Args:
            df: 包含价格数据的DataFrame
            period: 计算周期，默认为6
            
        Returns:
            float: 当前乖离率值
        """
        try:
            # 计算移动平均线
            ma = df['close'].rolling(window=period).mean()
            
            # 计算乖离率：(收盘价 - MA) / MA × 100%
            bias = ((df['close'] - ma) / ma * 100).iloc[-1]
            
            # 验证值是否有效
            bias_value = float(bias)
            if pd.isna(bias_value) or not np.isfinite(bias_value):
                return 0.0
                
            return round(bias_value, 2)
            
        except Exception as e:
            logger.error(f"计算乖离率指标时发生错误: {str(e)}")
            return 0.0
    
    def _calculate_psy(self, df: pd.DataFrame, period: int = 12) -> float:
        """计算心理线指标
        
        Args:
            df: 包含价格数据的DataFrame
            period: 计算周期，默认为12
            
        Returns:
            float: 当前心理线值
        """
        try:
            # 计算价格变化
            df['change'] = df['close'].diff()
            
            # 标记上涨天数
            df['up'] = df['change'].apply(lambda x: 1 if x > 0 else 0)
            
            # 计算心理线：上涨天数 / 总天数 × 100
            psy = (df['up'].rolling(window=period).sum() / period * 100).iloc[-1]
            
            # 验证值是否有效
            psy_value = float(psy)
            if pd.isna(psy_value) or not np.isfinite(psy_value):
                return 50.0
                
            return round(psy_value, 1)
            
        except Exception as e:
            logger.error(f"计算心理线指标时发生错误: {str(e)}")
            return 50.0
    
    def _calculate_dmi(self, df: pd.DataFrame, period: int = 14) -> Dict:
        """计算动向指标
        
        Args:
            df: 包含价格数据的DataFrame
            period: 计算周期，默认为14
            
        Returns:
            Dict: 包含+DI、-DI和ADX的值
        """
        try:
            # 确保数据类型正确
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            
            # 计算TR（真实波幅）
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift(1))
            df['tr3'] = abs(df['low'] - df['close'].shift(1))
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            
            # 计算+DM和-DM
            df['up_move'] = df['high'] - df['high'].shift(1)
            df['down_move'] = df['low'].shift(1) - df['low']
            df['plus_dm'] = df.apply(lambda x: x['up_move'] if x['up_move'] > x['down_move'] and x['up_move'] > 0 else 0, axis=1)
            df['minus_dm'] = df.apply(lambda x: x['down_move'] if x['down_move'] > x['up_move'] and x['down_move'] > 0 else 0, axis=1)
            
            # 计算+DI和-DI
            plus_di = 100 * (df['plus_dm'].rolling(window=period).sum() / df['tr'].rolling(window=period).sum())
            minus_di = 100 * (df['minus_dm'].rolling(window=period).sum() / df['tr'].rolling(window=period).sum())
            
            # 计算ADX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(window=period).mean()
            
            # 获取最新的值并验证
            plus_di_value = float(plus_di.iloc[-1])
            minus_di_value = float(minus_di.iloc[-1])
            adx_value = float(adx.iloc[-1])
            
            # 验证值是否有效
            if pd.isna(plus_di_value) or not np.isfinite(plus_di_value):
                plus_di_value = 0.0
            if pd.isna(minus_di_value) or not np.isfinite(minus_di_value):
                minus_di_value = 0.0
            if pd.isna(adx_value) or not np.isfinite(adx_value):
                adx_value = 0.0
            
            return {
                'plus_di': round(plus_di_value, 1),
                'minus_di': round(minus_di_value, 1),
                'adx': round(adx_value, 1)
            }
            
        except Exception as e:
            logger.error(f"计算动向指标时发生错误: {str(e)}")
            return {
                'plus_di': 0.0,
                'minus_di': 0.0,
                'adx': 0.0
            }
    
    def _calculate_vwap(self, df: pd.DataFrame) -> float:
        """计算成交量加权平均价
        
        Args:
            df: 包含价格和成交量数据的DataFrame
            
        Returns:
            float: 当前VWAP值
        """
        try:
            # 计算典型价格
            df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
            
            # 计算价格×成交量
            df['price_volume'] = df['typical_price'] * df['volume']
            
            # 计算VWAP
            vwap = df['price_volume'].sum() / df['volume'].sum()
            
            # 验证值是否有效
            vwap_value = float(vwap)
            if pd.isna(vwap_value) or not np.isfinite(vwap_value):
                return float(df['close'].iloc[-1])
                
            return round(vwap_value, 2)
            
        except Exception as e:
            logger.error(f"计算成交量加权平均价时发生错误: {str(e)}")
            return float(df['close'].iloc[-1])
    
    def _get_funding_rate(self, symbol: str) -> float:
        """获取资金费率
        
        Args:
            symbol: 交易对符号，例如 'BTCUSDT'
            
        Returns:
            float: 资金费率
        """
        try:
            funding_rate = self.binance_api.get_funding_rate(symbol)
            if funding_rate is not None:
                return round(float(funding_rate), 6)
            return 0.0
            
        except Exception as e:
            logger.error(f"获取资金费率时发生错误: {str(e)}")
            return 0.0
    
    def _calculate_exchange_netflow(self, df: pd.DataFrame, period: int = 30) -> float:
        """计算交易所净流入流出
        
        Args:
            df: 包含价格和成交量数据的DataFrame
            period: 计算周期，默认为30天
            
        Returns:
            float: 交易所净流入流出值
        """
        try:
            # 计算每日净流入流出
            df['net_flow'] = df['volume'] * df['close']
            
            # 计算30日平均净流入流出
            avg_net_flow = df['net_flow'].rolling(window=period).mean()
            
            # 计算当前净流入流出与平均值的比率
            current_net_flow = df['net_flow'].iloc[-1]
            avg_net_flow_value = float(avg_net_flow.iloc[-1])
            
            if avg_net_flow_value == 0:
                return 0.0
                
            netflow_ratio = (current_net_flow - avg_net_flow_value) / avg_net_flow_value * 100
            
            # 限制数值范围
            netflow_ratio = max(min(netflow_ratio, 1000.0), -1000.0)
            
            return round(float(netflow_ratio), 2)
            
        except Exception as e:
            logger.error(f"计算交易所净流入流出时发生错误: {str(e)}")
            return 0.0
    
    def _calculate_nupl(self, df: pd.DataFrame) -> float:
        """计算未实现盈亏比率
        
        Args:
            df: 包含价格数据的DataFrame
            
        Returns:
            float: 未实现盈亏比率
        """
        try:
            # 检查数据长度
            if len(df) < 200:
                logger.warning(f"数据长度不足200天，无法计算NUPL")
                return 0.0
            
            # 打印原始数据
            logger.info(f"计算NUPL的原始数据:")
            logger.info(f"数据长度: {len(df)}")
            logger.info(f"最新价格: {df['close'].iloc[-1]}")
            
            # 计算200日移动平均线作为成本基准
            ma200 = df['close'].rolling(window=200).mean()
            
            # 打印MA200数据
            logger.info(f"MA200值: {ma200.iloc[-1]}")
            
            # 计算当前价格与200日均线的比率
            current_price = float(df['close'].iloc[-1])
            ma200_value = float(ma200.iloc[-1])
            
            if ma200_value == 0:
                logger.warning("MA200值为0，无法计算NUPL")
                return 0.0
                
            nupl = (current_price - ma200_value) / ma200_value * 100
            
            # 打印计算结果
            logger.info(f"NUPL计算结果: {nupl}")
            
            # 限制数值范围
            nupl = max(min(nupl, 1000.0), -1000.0)
            
            return round(float(nupl), 2)
            
        except Exception as e:
            logger.error(f"计算未实现盈亏比率时发生错误: {str(e)}")
            return 0.0
    
    def _calculate_mayer_multiple(self, df: pd.DataFrame) -> float:
        """计算梅耶倍数
        
        Args:
            df: 包含价格数据的DataFrame
            
        Returns:
            float: 梅耶倍数
        """
        try:
            # 检查数据长度
            if len(df) < 200:
                logger.warning(f"数据长度不足200天，无法计算梅耶倍数")
                return 1.0
            
            # 打印原始数据
            logger.info(f"计算梅耶倍数的原始数据:")
            logger.info(f"数据长度: {len(df)}")
            logger.info(f"最新价格: {df['close'].iloc[-1]}")
            
            # 计算200日移动平均线
            ma200 = df['close'].rolling(window=200).mean()
            
            # 打印MA200数据
            logger.info(f"MA200值: {ma200.iloc[-1]}")
            
            # 计算当前价格与200日均线的比率
            current_price = float(df['close'].iloc[-1])
            ma200_value = float(ma200.iloc[-1])
            
            if ma200_value == 0:
                logger.warning("MA200值为0，无法计算梅耶倍数")
                return 1.0
                
            mayer_multiple = current_price / ma200_value
            
            # 打印计算结果
            logger.info(f"梅耶倍数计算结果: {mayer_multiple}")
            
            # 限制数值范围
            mayer_multiple = max(min(mayer_multiple, 100.0), 0.01)
            
            return round(float(mayer_multiple), 2)
            
        except Exception as e:
            logger.error(f"计算梅耶倍数时发生错误: {str(e)}")
            return 1.0

    def calculate_vwap(self, klines):
        """计算成交量加权平均价格
        
        Args:
            klines: K线数据列表
            
        Returns:
            float: VWAP值
        """
        try:
            total_volume = sum(float(k[5]) for k in klines)  # 成交量
            if total_volume == 0:
                return 0.0
                
            weighted_sum = sum(float(k[4]) * float(k[5]) for k in klines)  # 收盘价 * 成交量
            return weighted_sum / total_volume
            
        except Exception as e:
            logger.error(f"计算VWAP时出错: {str(e)}")
            return 0.0
            
    def calculate_nupl(self, current_price, realized_price):
        """计算未实现盈亏比例
        
        Args:
            current_price: 当前价格
            realized_price: 已实现价格
            
        Returns:
            float: NUPL值
        """
        try:
            if realized_price == 0:
                return 0.0
                
            nupl = ((current_price - realized_price) / realized_price) * 100
            return max(min(nupl, 100), -100)  # 限制在-100到100之间
            
        except Exception as e:
            logger.error(f"计算NUPL时出错: {str(e)}")
            return 0.0
            
    def calculate_mayer_multiple(self, current_price, ma_200):
        """计算Mayer倍数
        
        Args:
            current_price: 当前价格
            ma_200: 200日移动平均线
            
        Returns:
            float: Mayer倍数
        """
        try:
            if ma_200 == 0:
                return 1.0
                
            multiple = current_price / ma_200
            return max(min(multiple, 10), 0.1)  # 限制在0.1到10之间
            
        except Exception as e:
            logger.error(f"计算Mayer倍数时出错: {str(e)}")
            return 1.0 