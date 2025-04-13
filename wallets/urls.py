from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DeviceViewSet,
    WalletViewSet,
    PaymentPasswordViewSet
)

# 创建路由器
router = DefaultRouter()
router.register(r'devices', DeviceViewSet)
router.register(r'wallets', WalletViewSet)
router.register(r'payment-passwords', PaymentPasswordViewSet)

# URL 配置
urlpatterns = [
    # 支付密码相关的路由
    path('set_password/', PaymentPasswordViewSet.as_view({'post': 'set_password'})),
    path('verify_password/', PaymentPasswordViewSet.as_view({'post': 'verify'})),
    path('change_password/', PaymentPasswordViewSet.as_view({'post': 'change_password'})),
    path('payment_password/status/<str:device_id>/', PaymentPasswordViewSet.as_view({'get': 'status'})),

    # 钱包相关的路由
    path('<int:pk>/show_private_key/', WalletViewSet.as_view({'post': 'show_private_key'})),
    path('<int:pk>/get_all_balances/', WalletViewSet.as_view({'get': 'get_all_balances'})),
    path('<int:pk>/token-management/', WalletViewSet.as_view({'get': 'token_management'})),
    path('<int:pk>/set-token-visibility/', WalletViewSet.as_view({'post': 'set_token_visibility'})),
    path('get_supported_chains/', WalletViewSet.as_view({'get': 'get_supported_chains'})),

    # 包含路由器的 URL
    path('', include(router.urls)),
]