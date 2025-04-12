from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WalletViewSet, PaymentPasswordViewSet

# 创建路由器
router = DefaultRouter()
router.register(r'', WalletViewSet, basename='wallet')

# URL 配置
urlpatterns = [
    # 支付密码相关的路由
    path('set_password/', PaymentPasswordViewSet.as_view({'post': 'set_password'})),
    path('verify_password/', PaymentPasswordViewSet.as_view({'post': 'verify'})),
    path('change_password/', PaymentPasswordViewSet.as_view({'post': 'change_password'})),
    path('payment_password/status/<str:device_id>/', PaymentPasswordViewSet.as_view({'get': 'status'})),
    
    # 钱包相关的路由
    path('<int:pk>/show_private_key/', WalletViewSet.as_view({'post': 'show_private_key'})),
    path('', include(router.urls)),
] 