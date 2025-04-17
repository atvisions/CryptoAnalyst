from rest_framework import serializers
from .models import Device, Wallet, PaymentPassword, WalletToken, Token
from django.core.exceptions import ValidationError
import hashlib
import base58
from solders.keypair import Keypair
from eth_account import Account
from .constants import EVM_CHAINS  # 从 constants.py 导入

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
    kadena_chain_id = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ['id', 'chain', 'address', 'name', 'is_watch_only', 'avatar', 'kadena_chain_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def get_kadena_chain_id(self, obj):
        # 只有当钱包是 Kadena 钱包时才返回 kadena_chain_id
        if obj.chain == 'KDA' or obj.chain == 'KDA_TESTNET':
            return obj.kadena_chain_id
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
        elif chain in EVM_CHAINS:  # 支持所有 EVM 链
            try:
                account = Account.from_key(private_key)
                data['address'] = account.address
            except Exception as e:
                raise ValidationError(f"Invalid EVM private key: {str(e)}")
        elif chain == 'KDA':
            try:
                # 如果私钥是地址格式（以 'k:' 开头）
                if private_key.startswith('k:'):
                    # 直接使用作为地址
                    data['address'] = private_key
                    return data

                # 如果私钥已经是十六进制格式但没有 'k:' 前缀
                if len(private_key) == 64 and all(c in '0123456789abcdefABCDEF' for c in private_key):
                    # 添加 'k:' 前缀
                    data['address'] = f"k:{private_key}"
                    return data

                # 如果是十六进制格式的私钥
                try:
                    # 使用 nacl 库从私钥生成公钥和地址
                    import nacl.signing

                    # 尝试将私钥解析为字节
                    private_key_bytes = bytes.fromhex(private_key)
                    signing_key = nacl.signing.SigningKey(private_key_bytes)

                    # 从签名密钥获取验证密钥（公钥）
                    verify_key = signing_key.verify_key

                    # 生成地址
                    public_key = verify_key.encode().hex()
                    address = f"k:{public_key}"

                    data['address'] = address
                except ValueError as e:
                    raise ValidationError(f"Invalid Kadena private key format: {str(e)}")
            except Exception as e:
                raise ValidationError(f"Invalid Kadena private key: {str(e)}")
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


class TokenManagementSerializer(serializers.ModelSerializer):
    """代币管理序列化器"""
    symbol = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    current_price_usd = serializers.SerializerMethodField()
    price_change_24h = serializers.SerializerMethodField()

    class Meta:
        model = WalletToken
        fields = ['id', 'token_address', 'symbol', 'name', 'logo', 'is_visible', 'balance', 'balance_formatted', 'current_price_usd', 'price_change_24h']
        read_only_fields = ['id', 'token_address', 'symbol', 'name', 'logo', 'balance', 'balance_formatted', 'current_price_usd', 'price_change_24h']

    def get_symbol(self, obj):
        if obj.token:
            return obj.token.symbol

        # 如果没有关联的 Token 对象，尝试从链上获取代币信息
        try:
            if obj.chain == 'SOL':
                # 对于常见代币，直接返回符号
                if obj.token_address == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
                    return 'USDC'
                elif obj.token_address == 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB':
                    return 'USDT'
                elif obj.token_address == 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263':
                    return 'BONK'
                elif obj.token_address == 'JCYgnRRyM1ABMiZzRB9Ep3zLk1HZjk3B3yug9ebMmLsi':
                    return 'MPLX'
                elif obj.token_address == '7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr':
                    return 'PYTH'
                elif obj.token_address == 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm':
                    return 'RENDER'

                # 如果不是常见代币，尝试从 API 获取
                from chains.solana.services.balance import SolanaBalanceService
                balance_service = SolanaBalanceService()
                token_info = balance_service.get_token_info(obj.token_address)
                if token_info and 'symbol' in token_info:
                    return token_info['symbol']
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token symbol: {str(e)}")
        return ""

    def get_name(self, obj):
        if obj.token:
            return obj.token.name

        # 如果没有关联的 Token 对象，尝试从链上获取代币信息
        try:
            if obj.chain == 'SOL':
                # 对于常见代币，直接返回名称
                if obj.token_address == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
                    return 'USD Coin'
                elif obj.token_address == 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB':
                    return 'USDT'
                elif obj.token_address == 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263':
                    return 'Bonk'
                elif obj.token_address == 'JCYgnRRyM1ABMiZzRB9Ep3zLk1HZjk3B3yug9ebMmLsi':
                    return 'Metaplex'
                elif obj.token_address == '7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr':
                    return 'Pyth Network'
                elif obj.token_address == 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm':
                    return 'Render Token'

                # 如果不是常见代币，尝试从 API 获取
                from chains.solana.services.balance import SolanaBalanceService
                balance_service = SolanaBalanceService()
                token_info = balance_service.get_token_info(obj.token_address)
                if token_info and 'name' in token_info:
                    return token_info['name']
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token name: {str(e)}")
        return ""

    def get_logo(self, obj):
        # 如果是 KDA 链的原生代币，直接返回固定的 logo URL
        if obj.wallet.chain in ['KDA', 'KDA_TESTNET'] and obj.token_address == '':
            return 'https://cryptologos.cc/logos/kadena-kda-logo.png'

        if obj.token:
            # 如果有关联的 Token 对象但 logo_url 为空，对于 KDA 链的原生代币返回固定的 logo URL
            if obj.wallet.chain in ['KDA', 'KDA_TESTNET'] and obj.token_address == '' and not obj.token.logo_url:
                return 'https://cryptologos.cc/logos/kadena-kda-logo.png'
            return obj.token.logo_url

        # 如果没有关联的 Token 对象，尝试从链上获取代币信息
        try:
            # 对于 Kadena 链
            if obj.wallet.chain in ['KDA', 'KDA_TESTNET']:
                # 对于原生 KDA 代币
                if obj.token_address == '':
                    return 'https://cryptologos.cc/logos/kadena-kda-logo.png'

                # 如果不是原生代币，尝试从 API 获取
                from chains.kadena.services.token import KadenaTokenService
                token_service = KadenaTokenService()
                token_info = token_service.get_token_metadata(obj.token_address)
                if token_info and 'logo' in token_info:
                    return token_info['logo']

            # 对于 Solana 链
            elif obj.wallet.chain == 'SOL':
                # 对于常见代币，直接返回 logo URL
                if obj.token_address == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
                    return 'https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v/logo.png'
                elif obj.token_address == 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB':
                    return 'https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB/logo.svg'
                elif obj.token_address == 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263':
                    return 'https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263/logo.png'
                elif obj.token_address == 'JCYgnRRyM1ABMiZzRB9Ep3zLk1HZjk3B3yug9ebMmLsi':
                    return 'https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/JCYgnRRyM1ABMiZzRB9Ep3zLk1HZjk3B3yug9ebMmLsi/logo.png'
                elif obj.token_address == '7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr':
                    return 'https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr/logo.png'
                elif obj.token_address == 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm':
                    return 'https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm/logo.png'

                # 如果不是常见代币，尝试从 API 获取
                from chains.solana.services.balance import SolanaBalanceService
                balance_service = SolanaBalanceService()
                token_info = balance_service.get_token_info(obj.token_address)
                if token_info and 'logo' in token_info:
                    return token_info['logo']
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting token logo: {str(e)}")
        return ""

    def get_current_price_usd(self, obj):
        """获取代币当前价格"""
        if obj.token:
            return obj.token.current_price_usd
        return 0

    def get_price_change_24h(self, obj):
        """获取代币 24 小时价格变化"""
        if obj.token:
            return obj.token.price_change_24h
        return 0