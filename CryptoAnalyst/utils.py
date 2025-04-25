import logging
import json
from typing import Dict, Any
from datetime import datetime, timezone

# 配置日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 创建文件处理器
file_handler = logging.FileHandler('crypto_analyst.log')
file_handler.setLevel(logging.INFO)

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# 添加处理器到日志记录器
logger.addHandler(console_handler)
logger.addHandler(file_handler)

def sanitize_float(value: Any, min_value: float = -1000000.0, max_value: float = 1000000.0) -> float:
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
        if not isinstance(float_value, float) or float_value != float_value or abs(float_value) == float('inf'):
            return 0.0

        # 限制数值范围
        return max(min(float_value, max_value), min_value)

    except (ValueError, TypeError):
        return 0.0

def sanitize_indicators(indicators: Dict) -> Dict:
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
                indicators[key] = sanitize_float(indicators[key])

        # 处理MACD
        if 'MACD' in indicators:
            macd = indicators['MACD']
            macd['line'] = sanitize_float(macd.get('line'), -10000.0, 10000.0)
            macd['signal'] = sanitize_float(macd.get('signal'), -10000.0, 10000.0)
            macd['histogram'] = sanitize_float(macd.get('histogram'), -10000.0, 10000.0)

        # 处理布林带
        if 'BollingerBands' in indicators:
            bb = indicators['BollingerBands']
            bb['upper'] = sanitize_float(bb.get('upper'), 0.0, 1000000.0)
            bb['middle'] = sanitize_float(bb.get('middle'), 0.0, 1000000.0)
            bb['lower'] = sanitize_float(bb.get('lower'), 0.0, 1000000.0)

        # 处理DMI
        if 'DMI' in indicators:
            dmi = indicators['DMI']
            dmi['plus_di'] = sanitize_float(dmi.get('plus_di'), 0.0, 100.0)
            dmi['minus_di'] = sanitize_float(dmi.get('minus_di'), 0.0, 100.0)
            dmi['adx'] = sanitize_float(dmi.get('adx'), 0.0, 100.0)

        return indicators

    except Exception as e:
        logger.error(f"处理指标数据时出错: {str(e)}")
        return {}

def format_timestamp(timestamp: datetime) -> str:
    """格式化时间戳为ISO格式
    
    Args:
        timestamp: 时间戳
        
    Returns:
        str: ISO格式的时间字符串
    """
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.isoformat()

def parse_timestamp(timestamp_str: str) -> datetime:
    """解析ISO格式的时间字符串
    
    Args:
        timestamp_str: ISO格式的时间字符串
        
    Returns:
        datetime: 时间戳对象
    """
    return datetime.fromisoformat(timestamp_str)

def safe_json_loads(json_str: str) -> Dict:
    """安全地解析JSON字符串
    
    Args:
        json_str: JSON字符串
        
    Returns:
        dict: 解析后的字典，如果解析失败则返回空字典
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.error(f"JSON解析失败: {json_str}")
        return {} 