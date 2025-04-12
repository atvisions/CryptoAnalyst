from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
import uuid
from django.utils import timezone
from django.conf import settings
import os
import random

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
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    chain = models.CharField(max_length=32)  # ETH, SOL, KDA
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('device', 'chain')

    def __str__(self):
        return f"{self.chain} chain for {self.device.device_id}"

class Wallet(models.Model):
    """钱包模型"""
    CHAIN_CHOICES = [
        ('ETH', 'Ethereum'),
        ('BSC', 'BNB Chain'),
        ('MATIC', 'Polygon'),
        ('AVAX', 'Avalanche'),
        ('OP', 'Optimism'),
        ('ARB', 'Arbitrum'),
        ('SOL', 'Solana'),
        ('KDA', 'Kadena'),
    ]

    CHAIN_LOGOS = {
        'ETH': 'https://assets.coingecko.com/coins/images/279/large/ethereum.png',
        'BSC': 'https://assets.coingecko.com/coins/images/825/large/bnb-icon2_2x.png',
        'MATIC': 'https://assets.coingecko.com/coins/images/4713/large/matic-token-icon.png',
        'AVAX': 'https://assets.coingecko.com/coins/images/12559/large/Avalanche_Circle_RedWhite_Trans.png',
        'OP': 'https://assets.coingecko.com/coins/images/25244/large/Optimism.png',
        'ARB': 'https://assets.coingecko.com/coins/images/16547/large/photo_2023-03-29_21.47.00.jpeg',
        'SOL': 'https://assets.coingecko.com/coins/images/4128/large/solana.png',
        'KDA': 'https://assets.coingecko.com/coins/images/12240/large/kadena.png',
    }

    CHAIN_TYPES = {
        'ETH': 'EVM',
        'BSC': 'EVM',
        'MATIC': 'EVM',
        'AVAX': 'EVM',
        'OP': 'EVM',
        'ARB': 'EVM',
        'SOL': 'Solana',
        'KDA': 'Kadena',
    }

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    address = models.CharField(max_length=128)
    private_key = models.CharField(max_length=256)  # 加密后的私钥
    chain = models.CharField(max_length=32, choices=CHAIN_CHOICES)
    name = models.CharField(max_length=64, default="")
    is_watch_only = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to='face/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

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
