from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
import uuid
from django.utils import timezone
from django.conf import settings
import os
import random
from .constants import CHAIN_NAMES, CHAIN_CHOICES, CHAIN_TYPES, CHAIN_LOGOS

class Device(models.Model):
    device_id = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.device_id

class PaymentPassword(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    password_hash = models.CharField(max_length=256)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment password for {self.device.device_id}"

class Chain(models.Model):
    chain = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    is_testnet = models.BooleanField(default=False)  # 添加测试网标记
    logo = models.ImageField(upload_to='chain_logos/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.chain

    @property
    def name(self):
        return CHAIN_NAMES.get(self.chain, self.chain)

    @property
    def logo_url(self):
        """返回 logo URL，如果上传了自定义 logo 则使用自定义的，否则使用默认的"""
        if self.logo:
            return self.logo.url if hasattr(self.logo, 'url') else None
        # 如果没有上传 logo，使用默认的
        default_logo = CHAIN_LOGOS.get(self.chain)
        if default_logo:
            return default_logo
        return None

class Wallet(models.Model):
    """钱包模型"""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='wallets')
    address = models.CharField(max_length=128)
    private_key = models.CharField(max_length=256, null=True, blank=True)  # 加密后的私钥
    # 保留chain字段以保持兼容性，但添加chain_obj外键字段
    chain = models.CharField(max_length=32, choices=CHAIN_CHOICES)
    chain_obj = models.ForeignKey(Chain, on_delete=models.CASCADE, related_name='wallets', null=True)
    name = models.CharField(max_length=64, default="")
    is_watch_only = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)  # 添加激活状态字段
    avatar = models.ImageField(upload_to='face/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 移除 unique_together 约束，允许一个设备有多个相同链类型的钱包
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.chain}) - {self.address}"

    def save(self, *args, **kwargs):
        if not self.avatar:
            if os.path.exists(os.path.join(settings.MEDIA_ROOT, 'face')):
                faces = [f for f in os.listdir(os.path.join(settings.MEDIA_ROOT, 'face')) if f.endswith(('.jpg', '.jpeg', '.png'))]
                if faces:
                    random_face = random.choice(faces)
                    self.avatar = f'face/{random_face}'
        super().save(*args, **kwargs)

    def decrypt_private_key(self, payment_password=None):
        """解密私钥"""
        from .utils import decrypt_private_key
        return decrypt_private_key(self.private_key, payment_password)

class Token(models.Model):
    """代币模型"""
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE, related_name='tokens')
    address = models.CharField(max_length=255)
    symbol = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    decimals = models.IntegerField(default=18)
    logo_url = models.CharField(max_length=255, blank=True, null=True)
    current_price_usd = models.DecimalField(max_digits=30, decimal_places=18, default=0)
    price_change_24h = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # 百分比
    market_cap_usd = models.DecimalField(max_digits=30, decimal_places=2, default=0)
    volume_24h_usd = models.DecimalField(max_digits=30, decimal_places=2, default=0)
    fully_diluted_value = models.DecimalField(max_digits=30, decimal_places=2, null=True, blank=True, default=0)
    total_supply = models.DecimalField(max_digits=40, decimal_places=18, default=0)
    total_supply_formatted = models.CharField(max_length=50, blank=True, null=True)
    standard = models.CharField(max_length=20, blank=True, null=True)  # ERC20, SPL 等
    mint = models.CharField(max_length=255, blank=True, null=True)  # Solana 的 mint address
    description = models.TextField(blank=True, null=True)
    website = models.CharField(max_length=255, blank=True, null=True)
    twitter = models.CharField(max_length=255, blank=True, null=True)
    telegram = models.CharField(max_length=255, blank=True, null=True)
    discord = models.CharField(max_length=255, blank=True, null=True)
    # Metaplex 元数据
    metadata_uri = models.CharField(max_length=255, blank=True, null=True)
    is_master_edition = models.BooleanField(default=False)
    is_mutable = models.BooleanField(default=True)
    seller_fee_basis_points = models.IntegerField(default=0)
    update_authority = models.CharField(max_length=255, blank=True, null=True)
    primary_sale_happened = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['chain', 'address']
        ordering = ['-current_price_usd']

    def __str__(self):
        return f"{self.symbol} ({self.chain.chain})"

class WalletToken(models.Model):
    """钱包代币模型"""
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='wallet_tokens')
    token = models.ForeignKey(Token, on_delete=models.SET_NULL, null=True, blank=True, related_name='wallet_tokens')
    token_address = models.CharField(max_length=255)
    # 移除 chain 字段，因为它是冗余的，可以通过 wallet.chain 或 wallet.chain_obj.chain 获取
    # chain = models.CharField(max_length=20, choices=CHAIN_CHOICES, default='SOL')
    balance = models.DecimalField(max_digits=40, decimal_places=18, default=0)
    balance_formatted = models.CharField(max_length=50, blank=True, null=True)
    is_visible = models.BooleanField(default=True)
    last_synced = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['wallet', 'token_address']
        ordering = ['-balance']

    def __str__(self):
        return f"{self.token_address} ({self.wallet.address})"

    @property
    def symbol(self):
        """返回代币符号"""
        if self.token:
            return self.token.symbol
        return ""

    @property
    def name(self):
        """返回代币名称"""
        if self.token:
            return self.token.name
        return ""

    @property
    def logo(self):
        """返回代币图标"""
        if self.token:
            return self.token.logo_url
        return ""

    @property
    def decimals(self):
        """返回代币精度"""
        if self.token:
            return self.token.decimals
        return 18

    @property
    def price_usd(self):
        """返回代币价格"""
        if self.token:
            return self.token.current_price_usd
        return 0

    @property
    def value_usd(self):
        """返回代币价值"""
        if self.token:
            return self.balance * self.token.current_price_usd
        return 0


