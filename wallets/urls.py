from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DeviceViewSet,
    WalletViewSet,
    PaymentPasswordViewSet,
    WalletTokenViewSet
)

# 创建路由器
router = DefaultRouter()
router.register(r'devices', DeviceViewSet)
router.register(r'wallets', WalletViewSet)
router.register(r'payment-passwords', PaymentPasswordViewSet)

# URL 配置
urlpatterns = [
    # 代币相关的路由
    path('<int:wallet_id>/token-management/', WalletTokenViewSet.as_view({'get': 'list'}), name='wallet-token-management'),
    path('<int:wallet_id>/set-token-visibility/', WalletTokenViewSet.as_view({'post': 'set_visibility'}), name='set-token-visibility'),

    # 支付密码相关的路由
    path('set_password/', PaymentPasswordViewSet.as_view({'post': 'set_password'})),
    path('verify_password/', PaymentPasswordViewSet.as_view({'post': 'verify'})),
    path('change_password/', PaymentPasswordViewSet.as_view({'post': 'change_password'})),
    path('payment_password/status/<str:device_id>/', PaymentPasswordViewSet.as_view({'get': 'status'})),

    # 钱包相关的路由
    path('<int:pk>/show_private_key/', WalletViewSet.as_view({'post': 'show_private_key'})),
    path('<int:pk>/get_all_balances/', WalletViewSet.as_view({'get': 'get_all_balances'})),
    path('<int:pk>/token_metadata/', WalletViewSet.as_view({'get': 'token_metadata'})),
    path('<int:pk>/token_price_history/', WalletViewSet.as_view({'get': 'token_price_history'})),
    path('<int:pk>/refresh_balances/', WalletViewSet.as_view({'post': 'refresh_balances'})),
    path('update_token_metadata/', WalletViewSet.as_view({'post': 'update_token_metadata'})),
    path('check_task_status/', WalletViewSet.as_view({'post': 'check_task_status'})),
    path('<int:pk>/rename_wallet/', WalletViewSet.as_view({'post': 'rename_wallet'})),
    path('<int:pk>/delete_wallet/', WalletViewSet.as_view({'post': 'delete_wallet'})),
    path('<int:pk>/update_kadena_chain_id/', WalletViewSet.as_view({'post': 'update_kadena_chain_id'})),
    path('get_supported_chains/', WalletViewSet.as_view({'get': 'get_supported_chains'})),
    path('select_chain/', WalletViewSet.as_view({'post': 'select_chain'})),
    path('verify_mnemonic/', WalletViewSet.as_view({'post': 'verify_mnemonic'})),

    # 钱包列表相关的路由
    path('', WalletViewSet.as_view({'get': 'list'})),  # 显式定义钱包列表路由

    # 钱包导入相关的路由
    path('import_private_key/', WalletViewSet.as_view({'post': 'import_private_key'})),
    path('import_by_mnemonic/', WalletViewSet.as_view({'post': 'import_by_mnemonic'})),
    path('import_watch_only/', WalletViewSet.as_view({'post': 'import_watch_only'})),

    # 包含路由器的其他 URL
    path('router/', include(router.urls)),
]