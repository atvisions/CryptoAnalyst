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
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    address = models.CharField(max_length=128)
    private_key = models.CharField(max_length=256)  # 加密后的私钥
    chain = models.CharField(max_length=32, choices=CHAIN_CHOICES)
    name = models.CharField(max_length=64, default="")
    is_watch_only = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)  # 添加激活状态字段
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
