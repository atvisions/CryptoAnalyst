from rest_framework import serializers
from .models import Device, Wallet, PaymentPassword
from django.core.exceptions import ValidationError
import hashlib
import base58
from solders.keypair import Keypair
from eth_account import Account

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['device_id', 'created_at', 'updated_at']

class PaymentPasswordSerializer(serializers.ModelSerializer):
    payment_password = serializers.CharField(write_only=True)
    payment_password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = PaymentPassword
        fields = ['payment_password', 'payment_password_confirm']
    
    def validate(self, data):
        if data['payment_password'] != data['payment_password_confirm']:
            raise ValidationError("Passwords do not match")
        return data
    
    def create(self, validated_data):
        device = validated_data['device']
        password = validated_data['payment_password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        payment_password = PaymentPassword.objects.create(
            device=device,
            password_hash=password_hash
        )
        return payment_password

class WalletSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = ['id', 'chain', 'address', 'name', 'is_watch_only', 'avatar', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

class WalletCreateSerializer(serializers.ModelSerializer):
    payment_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = Wallet
        fields = ['chain', 'address', 'private_key', 'public_key', 'name', 'payment_password']
    
    def validate(self, data):
        # 验证支付密码
        device = self.context['device']
        payment_password = data.pop('payment_password')
        password_hash = hashlib.sha256(payment_password.encode()).hexdigest()
        
        try:
            payment_password_obj = PaymentPassword.objects.get(device=device)
            if payment_password_obj.password_hash != password_hash:
                raise ValidationError("Invalid payment password")
        except PaymentPassword.DoesNotExist:
            raise ValidationError("Payment password not set")
        
        return data

class WalletImportSerializer(serializers.ModelSerializer):
    payment_password = serializers.CharField(write_only=True)
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), write_only=True)
    
    class Meta:
        model = Wallet
        fields = ['chain', 'private_key', 'name', 'payment_password', 'device']
    
    def validate(self, data):
        # 验证支付密码
        device = data.get('device')
        payment_password = data.pop('payment_password')
        password_hash = hashlib.sha256(payment_password.encode()).hexdigest()
        
        try:
            payment_password_obj = PaymentPassword.objects.get(device=device)
            if payment_password_obj.password_hash != password_hash:
                raise ValidationError("Invalid payment password")
        except PaymentPassword.DoesNotExist:
            raise ValidationError("Payment password not set")
        
        # 从私钥生成地址
        chain = data.get('chain')
        private_key = data.get('private_key')
        
        if chain in ['SOL', 'Solana']:
            try:
                # 解码 base58 私钥，使用完整的 64 字节
                secret_key = base58.b58decode(private_key)
                keypair = Keypair.from_bytes(secret_key)
                data['address'] = str(keypair.pubkey())
            except Exception as e:
                raise ValidationError(f"Invalid Solana private key: {str(e)}")
        elif chain in ['ETH', 'Ethereum']:
            try:
                account = Account.from_key(private_key)
                data['address'] = account.address
            except Exception as e:
                raise ValidationError(f"Invalid Ethereum private key: {str(e)}")
        else:
            raise ValidationError(f"Unsupported chain: {chain}")
        
        return data

class WatchOnlyWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['chain', 'address', 'name']
    
    def create(self, validated_data):
        validated_data['is_watch_only'] = True
        return super().create(validated_data) 