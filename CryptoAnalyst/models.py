from django.db import models

class Chain(models.Model):
    """链模型"""
    chain = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    is_testnet = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "区块链"
        verbose_name_plural = "区块链"

    def __str__(self):
        return self.chain

class Token(models.Model):
    """代币模型"""
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE, related_name='tokens')
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20)
    address = models.CharField(max_length=100, blank=True)
    decimals = models.IntegerField(default=18)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "代币"
        verbose_name_plural = "代币"
        unique_together = ('chain', 'symbol')

    def __str__(self):
        return f"{self.chain.chain} - {self.symbol}"

class TokenAnalysisData(models.Model):
    """代币分析数据模型"""
    token = models.OneToOneField(Token, on_delete=models.CASCADE, related_name='analysis_data')
    price = models.FloatField(null=True, blank=True)
    volume_24h = models.FloatField(null=True, blank=True)
    price_change_24h = models.FloatField(null=True, blank=True)
    fear_greed_index = models.FloatField(null=True, blank=True)
    nupl = models.FloatField(null=True, blank=True, help_text="未实现盈亏")
    exchange_netflow = models.FloatField(null=True, blank=True, help_text="交易所净流入")
    mayer_multiple = models.FloatField(null=True, blank=True, help_text="梅耶倍数")
    
    # 技术指标
    rsi = models.FloatField(null=True, blank=True, help_text="相对强弱指标")
    macd_line = models.FloatField(null=True, blank=True, help_text="MACD线")
    macd_signal = models.FloatField(null=True, blank=True, help_text="MACD信号线")
    macd_histogram = models.FloatField(null=True, blank=True, help_text="MACD柱状图")
    bollinger_upper = models.FloatField(null=True, blank=True, help_text="布林带上轨")
    bollinger_middle = models.FloatField(null=True, blank=True, help_text="布林带中轨")
    bollinger_lower = models.FloatField(null=True, blank=True, help_text="布林带下轨")
    bias = models.FloatField(null=True, blank=True, help_text="乖离率")
    psy = models.FloatField(null=True, blank=True, help_text="心理线")
    dmi_plus = models.FloatField(null=True, blank=True, help_text="DMI+DI")
    dmi_minus = models.FloatField(null=True, blank=True, help_text="DMI-DI")
    dmi_adx = models.FloatField(null=True, blank=True, help_text="DMI ADX")
    vwap = models.FloatField(null=True, blank=True, help_text="成交量加权平均价格")
    funding_rate = models.FloatField(null=True, blank=True, help_text="资金费率")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "代币分析数据"
        verbose_name_plural = "代币分析数据"

    def __str__(self):
        return f"{self.token.symbol} 分析数据"

    def to_json_data(self):
        """转换为JSON数据"""
        return {
            'price': self.price,
            'volume_24h': self.volume_24h,
            'price_change_24h': self.price_change_24h,
            'fear_greed_index': self.fear_greed_index,
            'nupl': self.nupl,
            'exchange_netflow': self.exchange_netflow,
            'mayer_multiple': self.mayer_multiple,
            'rsi': self.rsi,
            'macd': {
                'line': self.macd_line,
                'signal': self.macd_signal,
                'histogram': self.macd_histogram
            },
            'bollinger_bands': {
                'upper': self.bollinger_upper,
                'middle': self.bollinger_middle,
                'lower': self.bollinger_lower
            },
            'bias': self.bias,
            'psy': self.psy,
            'dmi': {
                'plus_di': self.dmi_plus,
                'minus_di': self.dmi_minus,
                'adx': self.dmi_adx
            },
            'vwap': self.vwap,
            'funding_rate': self.funding_rate,
            'updated_at': self.updated_at.isoformat()
        } 