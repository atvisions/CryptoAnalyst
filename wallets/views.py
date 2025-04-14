from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from .models import Device, Wallet, PaymentPassword, Chain, TokenVisibility
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
from chains.solana.services.token import SolanaTokenService
from rest_framework.permissions import IsAuthenticated
import logging
import json

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
        if self.action in ['get_balance', 'get_token_balance', 'show_private_key', 'get_all_balances', 'token_management', 'set_token_visibility']:
            return Wallet.objects.all()

        # 如果是我们的新接口，使用钱包 ID 作为路径参数
        if self.action in ['token_metadata', 'token_price_history']:
            return Wallet.objects.all()

        # 其他操作需要设备 ID
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
                'logo': chain_obj.logo_url,
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
            address, private_key = generate_wallet_from_mnemonic(mnemonic, chain)

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

    @action(detail=True, methods=['get'])
    def get_balance(self, request, pk=None):
        """获取钱包余额"""
        wallet = self.get_object()
        try:
            if wallet.chain == 'SOL':
                balance_service = SolanaBalanceService()
                balance = balance_service.get_balance(wallet.address)
            else:
                rpc_service = EVMRPCService(wallet.chain)
                balance = rpc_service.get_balance(wallet.address)
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
            if wallet.chain in EVM_CHAINS:
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
        """获取钱包的所有代币余额"""
        try:
            wallet = self.get_object()
            if wallet.chain == 'SOL':
                balance_service = SolanaBalanceService()
                # 传递钱包ID用于缓存
                balances = balance_service.get_all_balances(wallet.address, wallet_id=wallet.id)
                return Response(balances)
            else:
                return Response({
                    'total_value_usd': '0',
                    'total_value_change_24h': '0',
                    'tokens': []
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

    @action(detail=True, methods=['get', 'post'])
    def token_management(self, request, pk=None):
        """获取钱包的所有代币，包括可见和不可见的"""
        try:
            # 尝试获取钱包
            try:
                wallet = self.get_object()
            except Exception as wallet_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error getting wallet: {str(wallet_error)}")
                return Response({"error": f"Error getting wallet: {str(wallet_error)}", "detail": "Please check if the wallet ID is correct and you have permission to access it."}, status=status.HTTP_404_NOT_FOUND)

            # 检查钱包链类型
            if wallet.chain != 'SOL':
                return Response({"error": f"This endpoint currently only supports Solana wallets. Wallet chain: {wallet.chain}"}, status=status.HTTP_400_BAD_REQUEST)

            # 获取所有代币余额
            balance_service = SolanaBalanceService()
            all_tokens = balance_service.get_all_token_balances(wallet.address)

            # 获取SOL原生代币余额
            sol_balance = balance_service.get_native_balance(wallet.address)

            # 获取SOL价格和24小时变化（使用缓存）
            sol_price_data = balance_service._get_cached_token_price("So11111111111111111111111111111111111111112")
            if sol_price_data:
                sol_balance["price_usd"] = str(sol_price_data["current_price"])
                sol_balance["price_change_24h"] = str(sol_price_data["price_change_24h"])
                sol_balance["value_usd"] = str(float(sol_balance["balance"]) * sol_price_data["current_price"])
            else:
                sol_balance["price_usd"] = "0"
                sol_balance["price_change_24h"] = "0"
                sol_balance["value_usd"] = "0"

            # 将SOL添加到代币列表中
            all_tokens.insert(0, sol_balance)

            # 获取不可见的代币记录（使用缓存）
            from django.core.cache import cache
            import json

            cache_key = f"token_visibility:{wallet.id}"
            cached_visibility = cache.get(cache_key)

            if cached_visibility:
                # 使用缓存数据
                hidden_tokens = json.loads(cached_visibility)
                print(f"使用缓存的代币可见性数据: {wallet.id}")
            else:
                # 从数据库获取并缓存
                hidden_tokens_queryset = TokenVisibility.objects.filter(
                    wallet=wallet,
                    is_visible=False
                ).values_list('token_address', flat=True)

                hidden_tokens = list(hidden_tokens_queryset)
                # 缓存1小时
                cache.set(cache_key, json.dumps(hidden_tokens), 60 * 60)
                print(f"缓存代币可见性数据: {wallet.id}, {hidden_tokens}")

            # 为每个代币添加可见性信息
            for token in all_tokens:
                token_address = token['token_address']
                # 如果代币在隐藏列表中，则不可见；否则默认可见
                token['is_visible'] = token_address not in hidden_tokens

            # 返回所有代币的信息，包括可见性
            return Response(all_tokens)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token list: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def set_token_visibility(self, request, pk=None):
        """设置代币可见性，使用钱包ID作为路径参数"""
        try:
            # 尝试获取钱包
            try:
                wallet = self.get_object()
            except Exception as wallet_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error getting wallet: {str(wallet_error)}")
                return Response({"error": f"Error getting wallet: {str(wallet_error)}", "detail": "Please check if the wallet ID is correct and you have permission to access it."}, status=status.HTTP_404_NOT_FOUND)

            # 获取请求参数
            token_address = request.data.get('token_address')
            is_visible = request.data.get('is_visible')

            # 验证参数
            if token_address is None or is_visible is None:
                return Response({'error': '代币地址和可见性不能为空'}, status=status.HTTP_400_BAD_REQUEST)

            # 将is_visible转换为布尔值
            if isinstance(is_visible, str):
                is_visible = is_visible.lower() == 'true'

            # 采用例外模式，只记录不可见的代币
            if is_visible:
                # 如果设置为可见，删除记录（如果存在）
                TokenVisibility.objects.filter(
                    wallet=wallet,
                    token_address=token_address
                ).delete()
                print(f"删除代币可见性记录，恢复默认可见状态: {token_address}")
            else:
                # 如果设置为不可见，创建或更新记录
                TokenVisibility.objects.update_or_create(
                    wallet=wallet,
                    token_address=token_address,
                    defaults={'is_visible': False}
                )
                print(f"设置代币为不可见: {token_address}")

            # 更新缓存
            from django.core.cache import cache
            cache_key = f"token_visibility:{wallet.id}"
            # 删除缓存，下次请求时会重新生成
            cache.delete(cache_key)
            print(f"删除代币可见性缓存: {wallet.id}")

            return Response({'message': '代币可见性设置成功'})
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error setting token visibility: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_token_metadata(self, request):
        """获取代币元数据（不需要钱包 ID）"""
        try:
            token_address = request.query_params.get('token_address')
            if not token_address:
                return Response({'error': '代币地址是必需的'}, status=status.HTTP_400_BAD_REQUEST)

            # 创建 Solana 代币服务
            token_service = SolanaTokenService()

            # 获取代币元数据
            metadata = token_service.get_token_metadata(token_address)

            return Response(metadata)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token metadata: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 删除不带钱包 ID 的接口

    @action(detail=True, methods=['get'])
    def token_metadata(self, request, pk=None):
        """获取代币元数据，使用钱包 ID 作为路径参数"""
        try:
            # 获取钱包对象
            wallet = self.get_object()

            token_address = request.query_params.get('token_address')
            if not token_address:
                return Response({'error': '代币地址是必需的'}, status=status.HTTP_400_BAD_REQUEST)

            # 如果是 SOL 原生代币，使用 Wrapped SOL 的地址
            if token_address.lower() in ['sol', 'solana']:
                # Wrapped SOL 的地址
                token_address = 'So11111111111111111111111111111111111111112'

            # 创建 Solana 代币服务
            token_service = SolanaTokenService()

            # 获取代币元数据，强制刷新缓存
            metadata = token_service.get_token_metadata(token_address, force_refresh=True)

            # 打印元数据信息
            print(f"代币元数据: {json.dumps(metadata, indent=2)}")

            # 添加钱包相关信息
            metadata['wallet_id'] = wallet.id
            metadata['wallet_address'] = wallet.address
            metadata['wallet_name'] = wallet.name

            # 获取钱包中该代币的余额（如果是 Solana 钱包）
            if wallet.chain == 'SOL':
                try:
                    # 使用已创建的 token_service 获取代币余额
                    token_balance = token_service.get_token_balance(token_address, wallet.address)
                    metadata['balance'] = token_balance.get('balance', '0')
                except Exception as e:
                    logger.error(f"Error getting token balance: {str(e)}")
                    metadata['balance'] = '0'

            return Response(metadata)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token metadata: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def token_price_history(self, request, pk=None):
        """获取代币历史价格，使用钱包 ID 作为路径参数"""
        try:
            # 获取钱包对象
            wallet = self.get_object()

            token_address = request.query_params.get('token_address')
            timeframe = request.query_params.get('timeframe', '1d')
            count = request.query_params.get('count', 7)

            # 尝试将 count 转换为整数
            try:
                count = int(count)
            except (ValueError, TypeError):
                count = 7  # 默认值

            # 如果是 SOL 原生代币，使用 Wrapped SOL 的地址
            if token_address and token_address.lower() in ['sol', 'solana']:
                # Wrapped SOL 的地址
                token_address = 'So11111111111111111111111111111111111111112'

            # 验证时间间隔类型
            valid_timeframes = ['1s', '10s', '30s', '1min', '5min', '10min', '30min',
                              '1h', '4h', '12h', '1d', '1w', '1M', '1Y']
            if timeframe not in valid_timeframes:
                return Response({'error': f'无效的时间间隔，支持的类型有: {valid_timeframes}'},
                                status=status.HTTP_400_BAD_REQUEST)

            # 尝试将 count 转换为整数
            try:
                count = int(count)
                if count <= 0:
                    count = 7  # 默认值
            except ValueError:
                count = 7  # 默认值

            if not token_address:
                return Response({'error': '代币地址是必需的'}, status=status.HTTP_400_BAD_REQUEST)

            # 创建 Solana 代币服务
            token_service = SolanaTokenService()

            # 获取代币历史价格，强制刷新缓存
            # 使用统一的接口，不区分原生代币和其他代币
            price_history = token_service.get_token_price_history(
                token_address=token_address,
                timeframe=timeframe,
                count=count,
                force_refresh=True
            )

            # 打印价格历史信息
            print(f"代币价格历史: {json.dumps(price_history, indent=2)}")

            # 添加钱包相关信息
            price_history['wallet_id'] = wallet.id
            price_history['wallet_address'] = wallet.address
            price_history['wallet_name'] = wallet.name

            # 获取钱包中该代币的余额（如果是 Solana 钱包）
            if wallet.chain == 'SOL':
                try:
                    # 使用已创建的 token_service 获取代币余额
                    token_balance = token_service.get_token_balance(token_address, wallet.address)
                    price_history['balance'] = token_balance.get('balance', '0')
                except Exception as e:
                    logger.error(f"Error getting token balance: {str(e)}")
                    price_history['balance'] = '0'

            return Response(price_history)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token price history: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

