from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Device, Wallet, PaymentPassword, Chain, Token, WalletToken
from .tasks import fetch_token_metadata, process_token_metadata_batch
from celery.result import AsyncResult
from .serializers import (
    DeviceSerializer,
    PaymentPasswordSerializer,
    WalletSerializer,
    WalletCreateSerializer,
    WalletImportSerializer,
    WatchOnlyWalletSerializer,
    TokenManagementSerializer
)
from .constants import EVM_CHAINS  # 从 constants.py 导入
import uuid
import hashlib
from .utils import validate_mnemonic, generate_wallet_from_mnemonic, generate_mnemonic, encrypt_private_key
import os
import random
from django.conf import settings
from chains.evm.services.base import EVMRPCService
from chains.solana.services.base import SolanaRPCService
from chains.solana.services.balance import SolanaBalanceService
from rest_framework.permissions import IsAuthenticated
import logging

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
        """获取查询集"""
        # 如果是详情操作（如 get_balance），允许直接通过 ID 获取
        if self.action in ['retrieve', 'get_balance', 'get_token_balance', 'show_private_key', 'get_all_balances', 'token_metadata', 'token_price_history', 'refresh_balances', 'rename_wallet', 'delete_wallet']:
            return Wallet.objects.all()

        # 其他操作需要设备 ID，包括 list action
        device_id = self.request.query_params.get('device_id') or self.request.data.get('device_id')
        if device_id:
            device = get_or_create_device(device_id)
            return Wallet.objects.filter(device=device, is_active=True).order_by('-created_at')
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

    def list(self, request, *args, **kwargs):
        """获取钱包列表"""
        device_id = request.query_params.get('device_id')
        if not device_id:
            return Response({'error': 'Device ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        device_id = self.request.data.get('device_id')
        if not device_id:
            raise ValidationError({'error': 'Device ID is required'})
        device = get_or_create_device(device_id)
        wallet = serializer.save(device=device)

        # 获取钱包的代币余额并写入数据库
        try:
            if wallet.chain == 'SOL':
                balance_service = SolanaBalanceService()
                balance_service.get_all_token_balances(wallet.address, wallet_id=wallet.id)
            # 如果有其他链的处理逻辑，可以在这里添加
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token balances for new wallet: {str(e)}")
            # 不返回错误，因为钱包已经创建成功

    def perform_destroy(self, instance):
        # 软删除：将钱包标记为未激活，而不是真正删除
        instance.is_active = False
        instance.save()

        # 记录日志
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Wallet {instance.address} ({instance.chain}) marked as inactive via perform_destroy")

    @action(detail=False, methods=['get'])
    def get_supported_chains(self, request):
        """获取支持的链列表，返回所有已激活的链，包括主网和测试网"""
        # 获取所有已激活的链
        chains = Chain.objects.filter(is_active=True)

        chain_list = []
        for chain in chains:
            # 从数据库中获取链类型
            from wallets.constants import CHAIN_TYPES

            # 处理测试网链类型
            chain_code = chain.chain
            base_chain_code = chain_code.split('_')[0] if '_' in chain_code else chain_code

            # 先尝试获取完整链代码的类型，如果不存在，则使用基础链代码的类型
            chain_type = CHAIN_TYPES.get(chain_code, CHAIN_TYPES.get(base_chain_code, '')).upper()

            if chain_type == 'EVM':
                type_value = 'EVM'
            elif chain_type in ['SOLANA', 'KADENA']:
                type_value = 'NON_EVM'
            else:
                type_value = 'NON_EVM'  # 默认为非EVM

            chain_list.append({
                'chain': chain.chain,
                'name': chain.name,
                'logo': request.build_absolute_uri(chain.logo_url) if chain.logo_url else None,
                'type': type_value,
                'is_testnet': chain.is_testnet
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

        # 软删除：将钱包标记为未激活，而不是真正删除
        wallet.is_active = False
        wallet.save()

        # 记录日志
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Wallet {wallet.address} ({wallet.chain}) marked as inactive")

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

        # 检查链是否激活
        chain_code = request.data.get('chain')
        if chain_code:
            try:
                chain_obj = Chain.objects.get(chain=chain_code)
                if not chain_obj.is_active:
                    return Response({'error': f'链 {chain_code} 当前未激活'},
                                  status=status.HTTP_400_BAD_REQUEST)
            except Chain.DoesNotExist:
                return Response({'error': f'不支持的链 {chain_code}'},
                              status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 获取验证后的数据
        chain = serializer.validated_data['chain']
        address = serializer.validated_data['address']

        # 检查钱包是否已存在
        existing_wallet = Wallet.objects.filter(
            device=device,
            chain=chain,
            address=address
        ).first()

        if existing_wallet:
            if existing_wallet.is_active:
                return Response({
                    'error': '钱包已存在',
                    'wallet': WalletSerializer(existing_wallet).data
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # 激活已存在的钱包
                existing_wallet.is_active = True
                existing_wallet.save()
                return Response(WalletSerializer(existing_wallet).data)

        # 加密私钥
        private_key = request.data.get('private_key')
        payment_password = request.data.get('payment_password')
        encrypted_private_key = encrypt_private_key(private_key, payment_password)

        # 创建新钱包
        wallet = Wallet.objects.create(
            device=device,
            chain=chain,
            address=address,
            private_key=encrypted_private_key,
            name=request.data.get('name', f'My Wallet {Wallet.objects.filter(device=device).count() + 1:02d}'),
            avatar=f'face/face-{random.randint(1, 10):02d}.png'
        )

        # 获取钱包的代币余额并写入数据库
        try:
            if chain == 'SOL':
                balance_service = SolanaBalanceService()
                balance_service.get_all_token_balances(address, wallet_id=wallet.id)
            # 如果有其他链的处理逻辑，可以在这里添加
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token balances for new wallet: {str(e)}")
            # 不返回错误，因为钱包已经创建成功

        return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def import_by_mnemonic(self, request):
        # 获取设备 ID 和链类型
        device_id = request.data.get('device_id')
        chain_code = request.data.get('chain')
        mnemonic = request.data.get('mnemonic')
        payment_password = request.data.get('payment_password')

        if not all([device_id, chain_code, mnemonic, payment_password]):
            return Response({'error': 'Device ID, chain, mnemonic and payment password are required'},
                          status=status.HTTP_400_BAD_REQUEST)

        # 检查链是否激活
        try:
            chain_obj = Chain.objects.get(chain=chain_code)
            if not chain_obj.is_active:
                return Response({'error': f'链 {chain_code} 当前未激活'},
                              status=status.HTTP_400_BAD_REQUEST)
        except Chain.DoesNotExist:
            return Response({'error': f'不支持的链 {chain_code}'},
                          status=status.HTTP_400_BAD_REQUEST)

        # 验证助记词
        if not validate_mnemonic(mnemonic):
            return Response({'error': 'Invalid mnemonic'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 获取或创建设备
            device = get_or_create_device(device_id)

            # 生成钱包地址和私钥
            address, private_key = generate_wallet_from_mnemonic(mnemonic, chain_code)

            # 检查钱包是否已存在
            existing_wallet = Wallet.objects.filter(
                device=device,
                chain=chain_code,
                address=address
            ).first()

            if existing_wallet:
                if existing_wallet.is_active:
                    return Response({
                        'error': '钱包已存在',
                        'wallet': WalletSerializer(existing_wallet).data
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # 激活已存在的钱包
                    existing_wallet.is_active = True
                    existing_wallet.save()

                    # 获取钱包的代币余额并写入数据库
                    try:
                        if chain_code == 'SOL':
                            balance_service = SolanaBalanceService()
                            balance_service.get_all_token_balances(address, wallet_id=existing_wallet.id)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error getting token balances for reactivated wallet: {str(e)}")

                    return Response(WalletSerializer(existing_wallet).data)

            # 加密私钥
            encrypted_private_key = encrypt_private_key(private_key, payment_password)

            # 获取用户的钱包数量
            wallet_count = Wallet.objects.filter(device=device).count()

            # 生成钱包名称
            wallet_name = request.data.get('name', f"My Wallet {wallet_count + 1:02d}")

            # 随机选择头像
            avatar_number = random.randint(1, 10)
            avatar_path = f'face/face-{avatar_number:02d}.png'

            # 创建钱包
            wallet = Wallet.objects.create(
                device=device,
                address=address,
                private_key=encrypted_private_key,
                chain=chain_code,
                chain_obj=chain_obj,  # 使用外键关联
                name=wallet_name,
                avatar=avatar_path
            )

            # 获取钱包的代币余额并写入数据库
            try:
                if chain_code == 'SOL':
                    balance_service = SolanaBalanceService()
                    balance_service.get_all_token_balances(address, wallet_id=wallet.id)
                # 如果有其他链的处理逻辑，可以在这里添加
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error getting token balances for new wallet: {str(e)}")
                # 不返回错误，因为钱包已经创建成功

            return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def import_watch_only(self, request):
        # 获取设备 ID 和链类型
        device_id = request.data.get('device_id')
        chain_code = request.data.get('chain')
        address = request.data.get('address')

        if not all([device_id, chain_code, address]):
            return Response({'error': 'Device ID, chain and address are required'},
                          status=status.HTTP_400_BAD_REQUEST)

        # 检查链是否激活
        try:
            chain_obj = Chain.objects.get(chain=chain_code)
            if not chain_obj.is_active:
                return Response({'error': f'链 {chain_code} 当前未激活'},
                              status=status.HTTP_400_BAD_REQUEST)
        except Chain.DoesNotExist:
            return Response({'error': f'不支持的链 {chain_code}'},
                          status=status.HTTP_400_BAD_REQUEST)

        try:
            # 获取或创建设备
            device = get_or_create_device(device_id)

            # 检查钱包是否已存在
            existing_wallet = Wallet.objects.filter(
                device=device,
                chain=chain_code,
                address=address
            ).first()

            if existing_wallet:
                if existing_wallet.is_active:
                    return Response({
                        'error': '钱包已存在',
                        'wallet': WalletSerializer(existing_wallet).data
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # 激活已存在的钱包
                    existing_wallet.is_active = True
                    existing_wallet.save()

                    # 获取钱包的代币余额并写入数据库
                    try:
                        if chain_code == 'SOL':
                            balance_service = SolanaBalanceService()
                            balance_service.get_all_token_balances(address, wallet_id=existing_wallet.id)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error getting token balances for reactivated watch-only wallet: {str(e)}")

                    return Response(WalletSerializer(existing_wallet).data)

            # 获取用户的钱包数量
            wallet_count = Wallet.objects.filter(device=device).count()

            # 生成钱包名称
            wallet_name = request.data.get('name', f"My Wallet {wallet_count + 1:02d}")

            # 随机选择头像
            avatar_number = random.randint(1, 10)
            avatar_path = f'face/face-{avatar_number:02d}.png'

            # 创建观察钱包
            wallet = Wallet.objects.create(
                device=device,
                address=address,
                chain=chain_code,
                chain_obj=chain_obj,  # 使用外键关联
                name=wallet_name,
                avatar=avatar_path,
                is_watch_only=True
            )

            # 获取钱包的代币余额并写入数据库
            try:
                if chain_code == 'SOL':
                    balance_service = SolanaBalanceService()
                    balance_service.get_all_token_balances(address, wallet_id=wallet.id)
                # 如果有其他链的处理逻辑，可以在这里添加
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error getting token balances for new watch-only wallet: {str(e)}")
                # 不返回错误，因为钱包已经创建成功

            return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def select_chain(self, request):
        device_id = request.data.get('device_id')
        chain = request.data.get('chain')

        if not device_id or not chain:
            return Response({'error': 'Device ID and chain are required'},
                          status=status.HTTP_400_BAD_REQUEST)

        device = get_or_create_device(device_id)

        # 从数据库中验证链是否支持和激活
        try:
            chain_obj = Chain.objects.get(chain=chain)
            if not chain_obj.is_active:
                return Response({'error': f'链 {chain} 当前未激活'},
                              status=status.HTTP_400_BAD_REQUEST)
        except Chain.DoesNotExist:
            return Response({'error': f'不支持的链 {chain}'},
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
                'logo': chain_obj.logo_url,
                'is_active': chain_obj.is_active
            },
            'mnemonic': mnemonic
        })

    @action(detail=False, methods=['post'])
    def verify_mnemonic(self, request):
        device_id = request.data.get('device_id')
        chain_code = request.data.get('chain')
        mnemonic = request.data.get('mnemonic')
        payment_password = request.data.get('payment_password')

        if not all([device_id, chain_code, mnemonic, payment_password]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        # 检查链是否激活
        try:
            chain_obj = Chain.objects.get(chain=chain_code)
            if not chain_obj.is_active:
                return Response({'error': f'链 {chain_code} 当前未激活'},
                              status=status.HTTP_400_BAD_REQUEST)
        except Chain.DoesNotExist:
            return Response({'error': f'不支持的链类型: {chain_code}'},
                          status=status.HTTP_400_BAD_REQUEST)

        # 验证助记词
        if not validate_mnemonic(mnemonic):
            return Response({'error': 'Invalid mnemonic'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 获取或创建设备
            device = get_or_create_device(device_id)

            # 生成钱包
            address, private_key = generate_wallet_from_mnemonic(mnemonic, chain_code)

            # 加密私钥
            encrypted_private_key = encrypt_private_key(private_key, payment_password)

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
                address=address,
                private_key=encrypted_private_key,
                chain=chain_code,
                chain_obj=chain_obj,  # 使用外键关联
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

    @action(detail=True, methods=['get'])
    def get_balance(self, request, pk=None):
        """获取钱包余额"""
        wallet = self.get_object()
        try:
            if wallet.chain == 'SOL':
                balance_service = SolanaBalanceService()
                balance = balance_service.get_balance(wallet.address)
            # 判断是否是EVM兼容链（包括测试网）
            elif wallet.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO'] or \
                 wallet.chain.startswith('ETH_') or wallet.chain.startswith('BSC_') or wallet.chain.startswith('MATIC_') or \
                 wallet.chain.startswith('ARB_') or wallet.chain.startswith('OP_') or wallet.chain.startswith('AVAX_') or \
                 wallet.chain.startswith('BASE_') or wallet.chain.startswith('ZKSYNC_') or wallet.chain.startswith('LINEA_') or \
                 wallet.chain.startswith('MANTA_') or wallet.chain.startswith('FTM_') or wallet.chain.startswith('CRO_'):
                rpc_service = EVMRPCService(wallet.chain)
                balance = rpc_service.get_balance(wallet.address)
            else:
                return Response({'error': f'不支持的链类型: {wallet.chain}'}, status=status.HTTP_400_BAD_REQUEST)
            return Response(balance)
        except Exception as e:
            import traceback
            error_detail = {
                'error': str(e),
                'traceback': traceback.format_exc(),
                'wallet_id': pk,
                'chain': wallet.chain,
                'address': wallet.address
            }
            return Response(error_detail, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def get_token_balance(self, request, pk=None):
        """获取代币余额"""
        wallet = self.get_object()
        token_address = request.query_params.get('token_address')
        if not token_address:
            return Response({'error': '需要提供代币地址'},
                          status=status.HTTP_400_BAD_REQUEST)

        try:
            # 判断是否是EVM兼容链（包括测试网）
            if wallet.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO'] or \
               wallet.chain.startswith('ETH_') or wallet.chain.startswith('BSC_') or wallet.chain.startswith('MATIC_') or \
               wallet.chain.startswith('ARB_') or wallet.chain.startswith('OP_') or wallet.chain.startswith('AVAX_') or \
               wallet.chain.startswith('BASE_') or wallet.chain.startswith('ZKSYNC_') or wallet.chain.startswith('LINEA_') or \
               wallet.chain.startswith('MANTA_') or wallet.chain.startswith('FTM_') or wallet.chain.startswith('CRO_'):
                from chains.evm.services.token import EVMTokenService
                token_service = EVMTokenService(wallet.chain)
                balance = token_service.get_token_balance(token_address, wallet.address)
                decimals = token_service.get_token_decimals(token_address)
                symbol = token_service.get_token_symbol(token_address)
                return Response({
                    'balance': balance,
                    'decimals': decimals,
                    'symbol': symbol
                })
            elif wallet.chain == 'SOL':
                from chains.solana.services.token import SolanaTokenService
                token_service = SolanaTokenService()
                balance = token_service.get_token_balance(token_address, wallet.address)
                decimals = token_service.get_token_decimals(token_address)
                symbol = token_service.get_token_symbol(token_address)
                return Response({
                    'balance': balance,
                    'decimals': decimals,
                    'symbol': symbol
                })
            else:
                return Response({'error': f'不支持的链类型: {wallet.chain}'},
                              status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'获取代币余额失败: {str(e)}'},
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def get_all_balances(self, request, pk=None):
        """获取钱包的所有代币余额，直接从数据库中获取"""
        try:
            # 尝试获取钱包对象
            try:
                from wallets.models import Wallet, WalletToken
                wallet = Wallet.objects.get(id=pk)
            except Wallet.DoesNotExist:
                return Response({'error': f'钱包 ID {pk} 不存在'}, status=status.HTTP_404_NOT_FOUND)

            # 如果数据库中没有代币记录，则从链上获取并更新数据库
            if not WalletToken.objects.filter(wallet=wallet).exists():
                if wallet.chain == 'SOL':
                    balance_service = SolanaBalanceService()
                    balance_service.get_all_token_balances(wallet.address, wallet_id=wallet.id)
                # 判断是否是EVM兼容链（包括测试网）
                elif wallet.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO'] or \
                     wallet.chain.startswith('ETH_') or wallet.chain.startswith('BSC_') or wallet.chain.startswith('MATIC_') or \
                     wallet.chain.startswith('ARB_') or wallet.chain.startswith('OP_') or wallet.chain.startswith('AVAX_') or \
                     wallet.chain.startswith('BASE_') or wallet.chain.startswith('ZKSYNC_') or wallet.chain.startswith('LINEA_') or \
                     wallet.chain.startswith('MANTA_') or wallet.chain.startswith('FTM_') or wallet.chain.startswith('CRO_'):
                    from chains.evm.services.balance import EVMBalanceService
                    balance_service = EVMBalanceService(wallet.chain)
                    balance_service.get_all_token_balances(wallet.address, wallet_id=wallet.id)

            # 从数据库中获取代币余额
            wallet_tokens = WalletToken.objects.filter(wallet=wallet, is_visible=True)

            # 序列化数据
            serializer = TokenManagementSerializer(wallet_tokens, many=True)
            token_list = serializer.data

            # 注释掉从链上获取原生代币余额的代码，因为数据库中已经有了
            # 获取原生代币余额
            # 检查是否已经有原生代币的记录
            # has_native_token = False
            # if wallet.chain == 'SOL':
            #     # 检查是否已经有 SOL 代币的记录
            #     for token in token_list:
            #         if token.get('token_address') == 'So11111111111111111111111111111111111111112':
            #             has_native_token = True
            #             break

            #     # 如果没有 SOL 代币的记录，才从链上获取
            #     if not has_native_token:
            #         balance_service = SolanaBalanceService()
            #         native_balance = balance_service.get_native_balance(wallet.address, wallet_id=wallet.id)
            #         if native_balance:
            #             token_list = [native_balance] + list(token_list)
            # # 判断是否是EVM兼容链（包括测试网）
            # elif wallet.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO'] or \
            #      wallet.chain.startswith('ETH_') or wallet.chain.startswith('BSC_') or wallet.chain.startswith('MATIC_') or \
            #      wallet.chain.startswith('ARB_') or wallet.chain.startswith('OP_') or wallet.chain.startswith('AVAX_') or \
            #      wallet.chain.startswith('BASE_') or wallet.chain.startswith('ZKSYNC_') or wallet.chain.startswith('LINEA_') or \
            #      wallet.chain.startswith('MANTA_') or wallet.chain.startswith('FTM_') or wallet.chain.startswith('CRO_'):
            #     from chains.evm.services.balance import EVMBalanceService
            #     balance_service = EVMBalanceService(wallet.chain)
            #     native_balance = balance_service.get_native_balance(wallet.address, wallet_id=wallet.id)
            #     if native_balance:
            #         token_list = [native_balance] + list(token_list)

            # 计算总价值和 24 小时价值变化
            total_value_usd = 0
            total_value_change_24h = 0

            # 遍历所有代币，计算总价值
            for token in token_list:
                try:
                    # 获取代币价格和余额
                    price = float(token.get('current_price_usd', 0))
                    # 使用 balance 字段而不是 balance_formatted
                    balance = float(token.get('balance', token.get('balance_formatted', 0)))

                    # 计算代币价值
                    token_value = price * balance
                    total_value_usd += token_value

                    # 计算 24 小时价值变化
                    price_change = float(token.get('price_change_24h', 0))
                    if price_change != 0:
                        token_value_change = token_value * price_change / 100
                        total_value_change_24h += token_value_change
                except Exception as e:
                    logger.error(f"Error calculating token value: {str(e)}")
                    continue

            # 格式化总价值和 24 小时价值变化
            total_value_usd = str(round(total_value_usd, 2))
            total_value_change_24h = str(round(total_value_change_24h, 2))

            return Response({
                'total_value_usd': total_value_usd,
                'total_value_change_24h': total_value_change_24h,
                'tokens': token_list
            })
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting balances: {str(e)}")
            return Response({
                'total_value_usd': '0',
                'total_value_change_24h': '0',
                'tokens': []
            })

    @action(detail=True, methods=['get'])
    def token_metadata(self, request, pk=None):
        """获取代币的元数据信息"""
        try:
            # 尝试获取钱包对象
            try:
                from wallets.models import Wallet
                wallet = Wallet.objects.get(id=pk)
            except Wallet.DoesNotExist:
                return Response({'error': f'钱包 ID {pk} 不存在'}, status=status.HTTP_404_NOT_FOUND)

            token_address = request.query_params.get('token_address')

            if not token_address:
                return Response({'error': '代币地址不能为空'}, status=status.HTTP_400_BAD_REQUEST)

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Getting metadata for token {token_address}")

            # 检查是否需要强制刷新元数据
            force_refresh = request.query_params.get('force_refresh', 'false').lower() == 'true'

            # 先从数据库中查询代币元数据
            from wallets.models import Token
            token_obj = Token.objects.filter(address=token_address).first()

            # 如果需要强制刷新元数据
            if force_refresh and token_obj:
                logger.info(f"Force refreshing metadata for token {token_address}")
                # 异步获取代币元数据
                fetch_token_metadata.delay(token_obj.id)
                return Response({
                    'message': f'已开始异步获取代币 {token_address} 的元数据',
                    'token_id': token_obj.id
                })

            if token_obj:
                logger.info(f"Found token metadata in database for {token_address}")

                # 构建元数据对象
                metadata = {
                    'mint': token_obj.address,
                    'standard': token_obj.standard,
                    'name': token_obj.name,
                    'symbol': token_obj.symbol,
                    'logo': token_obj.logo_url,  # 正确的字段名称是 logo_url
                    'decimals': token_obj.decimals,
                    'description': token_obj.description,
                }

                # 添加 metaplex 元数据（如果有）
                if token_obj.metadata_uri or token_obj.is_master_edition is not None or token_obj.is_mutable is not None:
                    metadata['metaplex'] = {}
                    if token_obj.metadata_uri:
                        metadata['metaplex']['metadataUri'] = token_obj.metadata_uri
                    if token_obj.is_master_edition is not None:
                        metadata['metaplex']['masterEdition'] = token_obj.is_master_edition
                    if token_obj.is_mutable is not None:
                        metadata['metaplex']['isMutable'] = token_obj.is_mutable
                    if token_obj.seller_fee_basis_points is not None:
                        metadata['metaplex']['sellerFeeBasisPoints'] = token_obj.seller_fee_basis_points
                    if token_obj.update_authority:
                        metadata['metaplex']['updateAuthority'] = token_obj.update_authority
                    if token_obj.primary_sale_happened is not None:
                        metadata['metaplex']['primarySaleHappened'] = token_obj.primary_sale_happened

                # 添加社交媒体链接
                metadata['links'] = {}
                if token_obj.website:
                    metadata['links']['website'] = token_obj.website
                if token_obj.twitter:
                    metadata['links']['twitter'] = token_obj.twitter
                if token_obj.telegram:
                    metadata['links']['telegram'] = token_obj.telegram
                if token_obj.discord:
                    metadata['links']['discord'] = token_obj.discord

                # 添加其他字段
                if token_obj.total_supply:
                    metadata['totalSupply'] = str(token_obj.total_supply)
                if token_obj.total_supply_formatted:
                    metadata['totalSupplyFormatted'] = token_obj.total_supply_formatted
                if token_obj.fully_diluted_value:
                    metadata['fullyDilutedValue'] = str(token_obj.fully_diluted_value)

                logger.info(f"Using database metadata for token {token_address}")

            # 如果数据库中没有找到，则从 Moralis API 获取
            else:
                logger.info(f"Token metadata not found in database for {token_address}, fetching from API")

                # 根据钱包链类型获取代币元数据
                if wallet.chain == 'SOL':
                    from chains.solana.services.token import SolanaTokenService
                    token_service = SolanaTokenService()

                    try:
                        metadata = token_service.get_token_metadata(token_address)
                        logger.info(f"Received metadata from API for token {token_address}: {metadata}")
                    except Exception as e:
                        logger.error(f"Error getting token metadata from API: {str(e)}")
                        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                    # 确保 metadata 不是 None
                    if metadata is None:
                        logger.error(f"Metadata for token {token_address} is None")
                        return Response({'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 9})

            # 删除重复的空社交媒体字段，如果它们已经在 links 对象中存在
            try:
                if 'links' in metadata and metadata['links'] is not None:
                    links = metadata['links']
                    # 如果社交媒体链接已经在 links 对象中，删除顶层的空字段
                    if 'website' in links and links['website'] and 'website' in metadata and not metadata['website']:
                        metadata.pop('website', None)
                    if 'twitter' in links and links['twitter'] and 'twitter' in metadata and not metadata['twitter']:
                        metadata.pop('twitter', None)
                    if 'telegram' in links and links['telegram'] and 'telegram' in metadata and not metadata['telegram']:
                        metadata.pop('telegram', None)
                    if 'discord' in links and links['discord'] and 'discord' in metadata and not metadata['discord']:
                        metadata.pop('discord', None)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error processing links for token {token_address}: {str(e)}")

            if wallet.chain == 'SOL':
                return Response(metadata)
            elif wallet.chain in ['ETH', 'BSC', 'POLYGON', 'ARBITRUM', 'OPTIMISM', 'AVALANCHE']:
                from chains.evm.services.token import EVMTokenService
                token_service = EVMTokenService(wallet.chain)
                metadata = token_service.get_token_metadata(token_address)
                return Response(metadata)
            else:
                return Response({'error': f'不支持的链类型: {wallet.chain}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token metadata: {str(e)}")
            return Response({'error': f'获取代币元数据失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_token_metadata(self, request):
        """手动触发代币元数据更新任务"""
        try:
            # 获取请求参数
            chain = request.data.get('chain')
            token_address = request.data.get('token_address')
            batch_size = int(request.data.get('batch_size', 30))
            sync_mode = request.data.get('sync_mode', 'false').lower() == 'true'

            import logging
            logger = logging.getLogger(__name__)

            # 构建查询条件
            query = {}
            if chain:
                # 获取链对象
                try:
                    chain_obj = Chain.objects.get(chain=chain)
                    query['chain'] = chain_obj
                except Chain.DoesNotExist:
                    return Response({'error': f'链 {chain} 不存在'}, status=status.HTTP_404_NOT_FOUND)

            if token_address:
                query['address'] = token_address

            # 查询符合条件的代币
            tokens = Token.objects.filter(**query, is_active=True)

            if not tokens.exists():
                return Response({'error': '没有找到符合条件的代币'}, status=status.HTTP_404_NOT_FOUND)

            # 按链分组处理
            chain_tokens = {}
            for token in tokens:
                chain_code = token.chain.chain
                if chain_code not in chain_tokens:
                    chain_tokens[chain_code] = []
                chain_tokens[chain_code].append(token.id)

            # 如果是同步模式，直接处理代币元数据
            if sync_mode:
                logger.info(f"使用同步模式处理 {tokens.count()} 个代币的元数据")
                processed_count = 0
                success_count = 0

                for chain_code, token_ids in chain_tokens.items():
                    # 根据链类型选择相应的服务
                    if chain_code == 'SOL':
                        from chains.solana.services.token import SolanaTokenService
                        token_service = SolanaTokenService()
                    elif chain_code in ['ETH', 'BSC', 'POLYGON', 'ARBITRUM', 'OPTIMISM', 'AVALANCHE']:
                        from chains.evm.services.token import EVMTokenService
                        token_service = EVMTokenService(chain_code)
                    else:
                        logger.error(f"不支持的链类型: {chain_code}")
                        continue

                    # 批量处理代币元数据
                    for token_id in token_ids:
                        try:
                            token = Token.objects.get(id=token_id)
                            processed_count += 1

                            logger.info(f"处理代币 {token.symbol} ({token.address}) 的元数据")
                            metadata = token_service.get_token_metadata(token.address)

                            # 更新代币元数据
                            if metadata:
                                # 更新基本信息
                                if 'name' in metadata and metadata['name']:
                                    token.name = metadata['name']
                                if 'symbol' in metadata and metadata['symbol']:
                                    token.symbol = metadata['symbol']
                                if 'decimals' in metadata:
                                    token.decimals = int(metadata['decimals'])
                                if 'logo' in metadata and metadata['logo']:
                                    token.logo_url = metadata['logo']

                                # 更新标准和mint信息
                                if 'standard' in metadata:
                                    token.standard = metadata['standard']
                                if 'mint' in metadata:
                                    token.mint = metadata['mint']

                                # 更新描述和社交媒体链接
                                if 'description' in metadata:
                                    token.description = metadata['description']

                                # 处理链接信息
                                links = metadata.get('links', {})
                                if links:
                                    if 'website' in links:
                                        token.website = links['website']
                                    if 'twitter' in links:
                                        token.twitter = links['twitter']
                                    if 'telegram' in links:
                                        token.telegram = links['telegram']
                                    if 'discord' in links:
                                        token.discord = links['discord']

                                # 直接处理顶级链接
                                if 'website' in metadata:
                                    token.website = metadata['website']
                                if 'twitter' in metadata:
                                    token.twitter = metadata['twitter']
                                if 'telegram' in metadata:
                                    token.telegram = metadata['telegram']
                                if 'discord' in metadata:
                                    token.discord = metadata['discord']

                                # 更新 Metaplex 元数据
                                metaplex = metadata.get('metaplex', {})
                                if metaplex:
                                    if 'metadataUri' in metaplex:
                                        token.metadata_uri = metaplex.get('metadataUri', '')
                                    if 'masterEdition' in metaplex:
                                        token.is_master_edition = metaplex.get('masterEdition', False)
                                    if 'isMutable' in metaplex:
                                        token.is_mutable = metaplex.get('isMutable', True)
                                    if 'sellerFeeBasisPoints' in metaplex:
                                        token.seller_fee_basis_points = metaplex.get('sellerFeeBasisPoints', 0)
                                    if 'updateAuthority' in metaplex:
                                        token.update_authority = metaplex.get('updateAuthority', '')
                                    if 'primarySaleHappened' in metaplex:
                                        # primarySaleHappened 可能是数字或布尔值
                                        primary_sale = metaplex.get('primarySaleHappened', 0)
                                        if isinstance(primary_sale, bool):
                                            token.primary_sale_happened = primary_sale
                                        else:
                                            token.primary_sale_happened = bool(primary_sale)

                                # 更新时间戳
                                token.last_updated = timezone.now()
                                token.save()

                                success_count += 1
                                logger.info(f"成功更新代币 {token.symbol} ({token.address}) 的元数据")
                        except Exception as e:
                            logger.error(f"处理代币 ID {token_id} 元数据时出错: {str(e)}")
                            continue

                return Response({
                    'message': f'同步处理完成，共处理 {processed_count} 个代币，成功 {success_count} 个',
                    'processed_count': processed_count,
                    'success_count': success_count
                })
            else:
                # 异步模式，使用Celery任务
                try:
                    # 获取回调URL（可选）
                    callback_url = request.data.get('callback_url')
                    auto_monitor = request.data.get('auto_monitor', 'true').lower() == 'true'

                    # 为每个链启动批处理任务
                    task_ids = []
                    for chain_code, token_ids in chain_tokens.items():
                        # 每批处理batch_size个代币
                        for i in range(0, len(token_ids), batch_size):
                            batch = token_ids[i:i+batch_size]
                            logger.info(f"为 {chain_code} 链安排批处理任务，包含 {len(batch)} 个代币")
                            task = process_token_metadata_batch.delay(batch, chain_code)
                            task_ids.append(str(task.id))

                    # 如果启用了自动监控，启动任务监控
                    monitor_task_id = None
                    if auto_monitor and task_ids:
                        from .tasks import monitor_tasks
                        monitor_task = monitor_tasks.delay(task_ids, callback_url)
                        monitor_task_id = str(monitor_task.id)
                        logger.info(f"启动任务监控，监控任务ID: {monitor_task_id}")

                    response_data = {
                        'message': f'已安排 {len(task_ids)} 个代币元数据更新任务',
                        'task_ids': task_ids,
                        'token_count': tokens.count()
                    }

                    if monitor_task_id:
                        response_data['monitor_task_id'] = monitor_task_id
                        response_data['monitor_info'] = '系统已启动自动监控任务，将每30秒检查任务状态'

                    if callback_url:
                        response_data['callback_url'] = callback_url
                        response_data['callback_info'] = '当所有任务完成时，系统将发送回调到指定的URL'

                    return Response(response_data)
                except Exception as e:
                    logger.error(f"安排异步任务时出错: {str(e)}")
                    return Response({
                        'error': f'安排异步任务时出错，请尝试使用sync_mode=true参数: {str(e)}',
                        'suggestion': '请尝试使用sync_mode=true参数来同步处理'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"安排代币元数据更新任务时出错: {str(e)}")
            return Response({'error': f'安排代币元数据更新任务时出错: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def check_task_status(self, request):
        """检查Celery任务状态"""
        try:
            # 获取请求参数
            task_ids = request.data.get('task_ids', [])

            if not task_ids:
                return Response({'error': '需要提供任务ID列表'}, status=status.HTTP_400_BAD_REQUEST)

            # 如果只提供了一个任务ID字符串，将其转换为列表
            if isinstance(task_ids, str):
                task_ids = [task_ids]

            # 检查每个任务的状态
            results = {}
            completed_count = 0
            failed_count = 0
            pending_count = 0

            for task_id in task_ids:
                try:
                    # 获取任务结果
                    result = AsyncResult(task_id)

                    # 检查任务状态
                    if result.ready():
                        if result.successful():
                            state = 'SUCCESS'
                            completed_count += 1
                        else:
                            state = 'FAILURE'
                            failed_count += 1
                    else:
                        state = result.state
                        pending_count += 1

                    results[task_id] = {
                        'state': state,
                        'info': str(result.info) if hasattr(result, 'info') and result.info else None
                    }
                except Exception as e:
                    results[task_id] = {
                        'state': 'UNKNOWN',
                        'error': str(e)
                    }
                    pending_count += 1

            # 计算总体进度
            total_tasks = len(task_ids)
            progress = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0

            return Response({
                'task_statuses': results,
                'summary': {
                    'total': total_tasks,
                    'completed': completed_count,
                    'failed': failed_count,
                    'pending': pending_count,
                    'progress_percentage': round(progress, 2)
                },
                'all_completed': completed_count + failed_count == total_tasks
            })
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"检查任务状态时出错: {str(e)}")
            return Response({'error': f'检查任务状态时出错: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def refresh_balances(self, request, pk=None):
        """手动刷新钱包代币余额和元数据"""
        try:
            # 尝试获取钱包对象
            try:
                from wallets.models import Wallet
                wallet = Wallet.objects.get(id=pk)
            except Wallet.DoesNotExist:
                return Response({'error': f'钱包 ID {pk} 不存在'}, status=status.HTTP_404_NOT_FOUND)

            # 根据钱包链类型调用相应的服务更新余额
            if wallet.chain == 'SOL':
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Refreshing balances for wallet {wallet.address} (SOL)")

                from chains.solana.services.balance import SolanaBalanceService
                balance_service = SolanaBalanceService()

                # 获取钱包代币余额
                logger.info(f"Starting to refresh balances for wallet {wallet.address}")
                try:
                    result = balance_service.get_all_token_balances(wallet.address, wallet_id=wallet.id)
                    logger.info(f"Successfully refreshed balances for wallet {wallet.address}")

                    # 打印获取到的元数据
                    if result:
                        logger.info(f"Found {len(result)} tokens with non-zero balance")
                    else:
                        logger.warning(f"No tokens found for wallet {wallet.address}")
                except Exception as e:
                    logger.error(f"Error refreshing balances: {e}")
                    return Response({'error': f'刷新代币余额失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # 查询数据库中的代币数据
                from wallets.models import Token, WalletToken
                tokens = Token.objects.filter(chain__chain='SOL')
                logger.info(f"Database tokens count: {tokens.count()}")

                # 打印数据库中的 Bonk 代币数据
                bonk_token = Token.objects.filter(address="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263").first()
                if bonk_token:
                    logger.info(f"Bonk token in database: {bonk_token.__dict__}")
                else:
                    logger.warning("Bonk token not found in database")

                # 打印钱包代币数据
                wallet_tokens = WalletToken.objects.filter(wallet=wallet)
                logger.info(f"Wallet tokens count: {wallet_tokens.count()}")

                # 返回更详细的响应，包含钱包地址和刷新时间
                from datetime import datetime
                refresh_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 查询钱包代币数量
                token_count = wallet_tokens.count()

                return Response({
                    'message': f'钱包 {wallet.address} 的代币余额已成功更新',
                    'wallet_address': wallet.address,
                    'refresh_time': refresh_time,
                    'token_count': token_count,
                    'status': 'success'
                })
            elif wallet.chain.split('_')[0] in ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'ZKSYNC', 'LINEA', 'MANTA', 'FTM', 'CRO'] or \
                 wallet.chain.startswith('ETH_') or wallet.chain.startswith('BSC_') or wallet.chain.startswith('MATIC_') or \
                 wallet.chain.startswith('ARB_') or wallet.chain.startswith('OP_') or wallet.chain.startswith('AVAX_') or \
                 wallet.chain.startswith('BASE_') or wallet.chain.startswith('ZKSYNC_') or wallet.chain.startswith('LINEA_') or \
                 wallet.chain.startswith('MANTA_') or wallet.chain.startswith('FTM_') or wallet.chain.startswith('CRO_'):
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Refreshing balances for wallet {wallet.address} ({wallet.chain})")

                from chains.evm.services.balance import EVMBalanceService
                balance_service = EVMBalanceService(wallet.chain)
                balance_service.get_all_token_balances(wallet.address, wallet_id=wallet.id)

                # 查询钱包代币数量
                from wallets.models import WalletToken
                wallet_tokens = WalletToken.objects.filter(wallet=wallet)
                token_count = wallet_tokens.count()

                # 返回更详细的响应，包含钱包地址和刷新时间
                from datetime import datetime
                refresh_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                return Response({
                    'message': f'钱包 {wallet.address} 的代币余额已成功更新',
                    'wallet_address': wallet.address,
                    'refresh_time': refresh_time,
                    'token_count': token_count,
                    'status': 'success'
                })
            else:
                return Response({'error': f'不支持的链类型: {wallet.chain}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error refreshing wallet balances: {str(e)}")
            return Response({'error': f'更新钱包余额失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def token_price_history(self, request, pk=None):
        """获取代币的价格历史数据"""
        try:
            # 尝试获取钱包对象
            try:
                from wallets.models import Wallet
                wallet = Wallet.objects.get(id=pk)
            except Wallet.DoesNotExist:
                return Response({'error': f'钱包 ID {pk} 不存在'}, status=status.HTTP_404_NOT_FOUND)

            token_address = request.query_params.get('token_address')
            timeframe = request.query_params.get('timeframe', '1d')  # 默认为日线
            count = request.query_params.get('count', '30')  # 默认获取 30 个数据点

            if not token_address:
                return Response({'error': '代币地址不能为空'}, status=status.HTTP_400_BAD_REQUEST)

            # 验证时间单位
            valid_timeframes = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '3d', '1w', '1M', 'all']
            if timeframe not in valid_timeframes:
                return Response({'error': f'无效的时间单位，有效值为: {valid_timeframes}'}, status=status.HTTP_400_BAD_REQUEST)

            # 验证数量
            try:
                count_int = int(count)
                if count_int <= 0 or count_int > 1000:
                    return Response({'error': '数量必须在 1 到 1000 之间'}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({'error': '数量必须是有效的整数'}, status=status.HTTP_400_BAD_REQUEST)

            # 根据钱包链类型选择合适的服务
            if wallet.chain == 'SOL' or wallet.chain in ['ETH', 'BSC', 'POLYGON', 'ARBITRUM', 'OPTIMISM', 'AVALANCHE']:
                # 使用辅助函数获取价格历史
                from django.conf import settings
                from wallets.views_helper import get_token_symbol, get_timeframe_params, get_price_history_from_cryptocompare

                try:
                    # 获取代币符号
                    symbol = get_token_symbol(wallet, token_address)

                    # 获取时间单位参数
                    endpoint, aggregate, count_int = get_timeframe_params(timeframe, count_int)

                    # 获取 API 密钥
                    api_key = settings.CRYPTOCOMPARE_API_KEY if hasattr(settings, 'CRYPTOCOMPARE_API_KEY') else None

                    # 获取价格历史数据
                    result = get_price_history_from_cryptocompare(symbol, endpoint, aggregate, count_int, api_key)

                    # 添加代币地址
                    result['token_address'] = token_address

                    return Response(result)
                except ValueError as e:
                    return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error getting price history: {str(e)}")
                    return Response({'error': f'获取价格历史数据失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response({'error': f'不支持的链类型: {wallet.chain}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token price history: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class WalletTokenViewSet(viewsets.ModelViewSet):
    """钱包代币视图集"""
    serializer_class = TokenManagementSerializer
    permission_classes = []  # 移除认证要求

    def get_queryset(self):
        queryset = WalletToken.objects.all()

        # 如果 URL 中有 wallet_id 参数，按钱包过滤
        wallet_id = self.kwargs.get('wallet_id')
        if wallet_id:
            queryset = queryset.filter(wallet_id=wallet_id)

        return queryset

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def set_visibility(self, request, wallet_id=None):
        """设置单个代币的可见性"""
        token_address = request.data.get('token_address')
        is_visible = request.data.get('is_visible', True)

        # 如果 URL 中有 wallet_id 参数，直接使用该参数
        if wallet_id:
            wallet = get_object_or_404(Wallet, id=wallet_id)
            chain = wallet.chain
        else:
            # 兼容旧的接口
            device_id = request.data.get('device_id')
            chain = request.data.get('chain')

            if not device_id or not token_address or not chain:
                raise ValidationError({'error': '设备ID、代币地址和链不能为空'})

            device = Device.objects.get(device_id=device_id)
            wallet = Wallet.objects.get(device=device, chain=chain)

        # 更新或创建代币可见性设置
        wallet_token, created = WalletToken.objects.get_or_create(
            wallet=wallet,
            token_address=token_address,
            chain=chain,
            defaults={
                'is_visible': is_visible,
                'balance': 0
            }
        )

        if not created:
            wallet_token.is_visible = is_visible
            wallet_token.save()

        return Response({'message': '代币可见性设置成功'})


class TokenManagementViewSet(viewsets.ModelViewSet):
    """代币管理视图集"""
    serializer_class = TokenManagementSerializer
    permission_classes = []  # 移除认证要求

    def get_queryset(self):
        """获取钱包的所有代币，直接从数据库中获取"""
        wallet_id = self.kwargs.get('wallet_id')
        if wallet_id:
            # 直接从数据库中获取钱包的代币记录
            return WalletToken.objects.filter(wallet_id=wallet_id)
        else:
            # 如果没有指定 wallet_id，返回所有代币记录
            return WalletToken.objects.all()

    def get_object(self):
        """获取单个代币可见性记录"""
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, obj)
        return obj

    def list(self, request, *args, **kwargs):
        """获取代币列表"""
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token list: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        """更新代币可见性"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating token visibility: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
