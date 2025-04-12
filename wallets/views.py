from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from .models import Device, Wallet, PaymentPassword, Chain
from .serializers import (
    DeviceSerializer,
    PaymentPasswordSerializer,
    WalletSerializer,
    WalletCreateSerializer,
    WalletImportSerializer,
    WatchOnlyWalletSerializer
)
from .constants import EVM_CHAINS  # 从 constants.py 导入
import uuid
import hashlib
from .utils import validate_mnemonic, generate_wallet_from_mnemonic, generate_mnemonic, encrypt_private_key
import os
import random
from django.conf import settings

# Create your views here.

def get_or_create_device(device_id):
    """
    获取或创建设备，如果设备已存在则返回现有设备
    """
    if not device_id:
        raise ValidationError({'error': 'Device ID is required'})
        
    device, created = Device.objects.get_or_create(device_id=device_id)
    return device

class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    
    def create(self, request, *args, **kwargs):
        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'error': 'Device ID is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        device = Device.objects.create(device_id=device_id)
        serializer = self.get_serializer(device)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class PaymentPasswordViewSet(viewsets.ModelViewSet):
    queryset = PaymentPassword.objects.all()
    serializer_class = PaymentPasswordSerializer
    permission_classes = [permissions.AllowAny]  # 允许匿名访问
    authentication_classes = []  # 禁用认证
    
    @action(detail=False, methods=['get'])
    def status(self, request, device_id=None):
        device = get_or_create_device(device_id)
        has_password = PaymentPassword.objects.filter(device=device).exists()
        return Response({'has_password': has_password})
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'error': 'Device ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        device = get_or_create_device(device_id)
        password = request.data.get('payment_password')
        
        try:
            payment_password = PaymentPassword.objects.get(device=device)
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if payment_password.password_hash == password_hash:
                return Response({'valid': True})
            return Response({'valid': False}, status=status.HTTP_400_BAD_REQUEST)
        except PaymentPassword.DoesNotExist:
            return Response({'valid': False, 'message': 'Payment password not set'}, 
                          status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def set_password(self, request):
        device_id = request.data.get('device_id')
        payment_password = request.data.get('payment_password')
        payment_password_confirm = request.data.get('payment_password_confirm')
        
        if not device_id:
            return Response({'error': 'Device ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not payment_password or not payment_password_confirm:
            return Response({'error': 'Password and confirmation are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if payment_password != payment_password_confirm:
            return Response({'error': 'Passwords do not match'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        device = get_or_create_device(device_id)
        
        # 检查是否已经设置过密码
        if PaymentPassword.objects.filter(device=device).exists():
            return Response({'error': 'Payment password already set'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # 创建密码哈希
        password_hash = hashlib.sha256(payment_password.encode()).hexdigest()
        PaymentPassword.objects.create(
            device=device,
            password_hash=password_hash
        )
        
        return Response({'message': 'Payment password set successfully'})
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        device_id = request.data.get('device_id')
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        if not all([device_id, old_password, new_password, confirm_password]):
            return Response({'error': 'All fields are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if new_password != confirm_password:
            return Response({'error': 'New passwords do not match'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        device = get_or_create_device(device_id)
        
        try:
            payment_password = PaymentPassword.objects.get(device=device)
            old_password_hash = hashlib.sha256(old_password.encode()).hexdigest()
            
            if payment_password.password_hash != old_password_hash:
                return Response({'error': 'Invalid old password'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # 更新密码
            new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            payment_password.password_hash = new_password_hash
            payment_password.save()
            
            return Response({'message': 'Password changed successfully'})
            
        except PaymentPassword.DoesNotExist:
            return Response({'error': 'Payment password not set'}, 
                          status=status.HTTP_400_BAD_REQUEST)

class WalletViewSet(viewsets.ModelViewSet):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def get_queryset(self):
        device_id = self.request.query_params.get('device_id') or self.request.data.get('device_id')
        if device_id:
            device = get_or_create_device(device_id)
            return Wallet.objects.filter(device=device).order_by('-created_at')
        return Wallet.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return WalletCreateSerializer
        elif self.action == 'import_private_key':
            return WalletImportSerializer
        elif self.action == 'import_by_mnemonic':
            return WalletImportSerializer
        elif self.action == 'import_watch_only':
            return WatchOnlyWalletSerializer
        return WalletSerializer
    
    def perform_create(self, serializer):
        device_id = self.request.data.get('device_id')
        if not device_id:
            raise ValidationError({'error': 'Device ID is required'})
        device = get_or_create_device(device_id)
        serializer.save(device=device)
    
    @action(detail=False, methods=['get'])
    def get_supported_chains(self, request):
        """获取支持的链列表"""
        chains = Chain.objects.filter(is_active=True)
        
        chain_list = []
        for chain in chains:
            chain_list.append({
                'chain': chain.chain,
                'name': chain.name,
                'logo': request.build_absolute_uri(chain.logo_url) if chain.logo_url else None,
                'type': 'EVM' if chain.chain in EVM_CHAINS else 'NON_EVM',
                'is_testnet': False
            })
        
        return Response(chain_list)
    
    @action(detail=True, methods=['post'])
    def rename_wallet(self, request, pk=None):
        wallet = self.get_object()
        new_name = request.data.get('new_name')
        if new_name:
            wallet.name = new_name
            wallet.save()
            return Response(WalletSerializer(wallet).data)
        return Response({'error': 'New name is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def delete_wallet(self, request, pk=None):
        wallet = self.get_object()
        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'error': 'Device ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        device = get_or_create_device(device_id)
        payment_password = request.data.get('payment_password')
        
        try:
            payment_password_obj = PaymentPassword.objects.get(device=device)
            password_hash = hashlib.sha256(payment_password.encode()).hexdigest()
            if payment_password_obj.password_hash != password_hash:
                return Response({'error': 'Invalid payment password'}, 
                              status=status.HTTP_400_BAD_REQUEST)
        except PaymentPassword.DoesNotExist:
            return Response({'error': 'Payment password not set'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        wallet.delete()
        return Response({'message': 'Wallet deleted successfully'})
    
    @action(detail=True, methods=['post'], url_path='show_private_key')
    def show_private_key(self, request, pk=None):
        wallet = self.get_object()
        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'error': 'Device ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        device = get_or_create_device(device_id)
        payment_password = request.data.get('payment_password')
        
        try:
            payment_password_obj = PaymentPassword.objects.get(device=device)
            password_hash = hashlib.sha256(payment_password.encode()).hexdigest()
            if payment_password_obj.password_hash != password_hash:
                return Response({'error': 'Invalid payment password'}, 
                              status=status.HTTP_400_BAD_REQUEST)
        except PaymentPassword.DoesNotExist:
            return Response({'error': 'Payment password not set'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # 解密私钥
        try:
            private_key = wallet.decrypt_private_key(payment_password)
            if wallet.chain in ['SOL', 'Solana']:
                # 对于 Solana 钱包，返回 base58 格式的私钥
                return Response({'private_key': private_key})
            else:
                # 对于其他链，返回十六进制格式的私钥
                return Response({'private_key': private_key})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def import_private_key(self, request):
        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'error': 'Device ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        device = get_or_create_device(device_id)
        request.data['device'] = device.id
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 加密私钥
        private_key = request.data.get('private_key')
        payment_password = request.data.get('payment_password')
        encrypted_private_key = encrypt_private_key(private_key, payment_password)
        
        # 创建钱包
        wallet = Wallet.objects.create(
            device=device,
            chain=request.data.get('chain'),
            address=serializer.validated_data['address'],
            private_key=encrypted_private_key,
            name=request.data.get('name', f'My Wallet {Wallet.objects.filter(device=device).count() + 1:02d}'),
            avatar=f'face/face-{random.randint(1, 10):02d}.png'
        )
        
        return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def import_by_mnemonic(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def import_watch_only(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def select_chain(self, request):
        device_id = request.data.get('device_id')
        chain = request.data.get('chain')
        
        if not device_id or not chain:
            return Response({'error': 'Device ID and chain are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        device = get_or_create_device(device_id)
        
        # 验证链是否支持
        if chain not in EVM_CHAINS and chain not in ['SOL', 'KDA']:
            return Response({'error': 'Unsupported chain'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # 更新或创建链
        chain_obj, created = Chain.objects.update_or_create(
            chain=chain,
            defaults={'is_active': True}
        )
        
        # 生成助记词
        mnemonic = generate_mnemonic()
        
        return Response({
            'message': f'Chain {chain} selected successfully',
            'chain': {
                'code': chain_obj.chain,
                'name': chain_obj.name,
                'logo': chain_obj.logo,
                'is_active': chain_obj.is_active
            },
            'mnemonic': mnemonic
        })
    
    @action(detail=False, methods=['post'])
    def verify_mnemonic(self, request):
        device_id = request.data.get('device_id')
        chain = request.data.get('chain')
        mnemonic = request.data.get('mnemonic')
        payment_password = request.data.get('payment_password')

        if not all([device_id, chain, mnemonic, payment_password]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        # 验证助记词
        if not validate_mnemonic(mnemonic):
            return Response({'error': 'Invalid mnemonic'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 获取或创建设备
            device = get_or_create_device(device_id)
            
            # 生成钱包
            wallet_data = generate_wallet_from_mnemonic(mnemonic, chain)
            
            # 加密私钥
            encrypted_private_key = encrypt_private_key(wallet_data['private_key'], payment_password)
            
            # 获取用户的钱包数量
            wallet_count = Wallet.objects.filter(device=device).count()
            
            # 生成钱包名称
            wallet_name = f"My Wallet {wallet_count + 1:02d}"
            
            # 随机选择头像
            avatar_number = random.randint(1, 10)
            avatar_path = f'face/face-{avatar_number:02d}.png'
            
            # 创建钱包
            wallet = Wallet.objects.create(
                device=device,
                address=wallet_data['address'],
                private_key=encrypted_private_key,
                chain=chain,
                name=wallet_name,
                avatar=avatar_path
            )
            
            return Response({
                'success': True,
                'wallet': {
                    'id': wallet.id,
                    'address': wallet.address,
                    'name': wallet.name,
                    'chain': wallet.chain,
                    'avatar': request.build_absolute_uri(wallet.avatar.url) if wallet.avatar else None
                }
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
