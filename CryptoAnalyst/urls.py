from django.urls import path
from .views import (
    TechnicalIndicatorsAPIView,
    TechnicalIndicatorsDataAPIView,
    TokenDataAPIView,
    SendVerificationCodeView,
    RegisterView,
    LoginView,
    UserProfileView,
    GenerateInvitationCodeView,
    TokenRefreshView,
    PriceHistoryAPIView
)

urlpatterns = [
    # 技术指标数据
    path('crypto/technical-indicators-data/<str:symbol>/', TechnicalIndicatorsDataAPIView.as_view(), name='technical_indicators_data'),
    path('crypto/technical-indicators/<str:symbol>/', TechnicalIndicatorsAPIView.as_view(), name='technical_indicators'),
    path('crypto/technical-indicators/<str:symbol>/force-refresh/', TechnicalIndicatorsAPIView.as_view(), name='technical_indicators_force_refresh'),

    # 用户相关
    path('auth/send-code/', SendVerificationCodeView.as_view(), name='send_verification_code'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/profile/', UserProfileView.as_view(), name='profile'),
    path('auth/refresh-token/', TokenRefreshView.as_view(), name='refresh_token'),
    path('auth/generate-invitation-code/', GenerateInvitationCodeView.as_view(), name='generate_invitation_code'),

    # 代币数据
    path('crypto/token-data/<str:token_id>/', TokenDataAPIView.as_view(), name='token_data'),

    # 价格历史数据
    path('crypto/price-history/<str:symbol>/', PriceHistoryAPIView.as_view(), name='price_history'),
]