from django.urls import path
from .views import TechnicalIndicatorsAPIView, TokenDataAPIView, TechnicalIndicatorsDataAPIView

urlpatterns = [
    path('technical-indicators/<str:symbol>/', TechnicalIndicatorsAPIView.as_view(), name='technical-indicators'),
    path('token-data/<str:token_id>/', TokenDataAPIView.as_view(), name='token-data'),
    path('technical-indicators-data/<str:symbol>/', TechnicalIndicatorsDataAPIView.as_view(), name='technical-indicators-data'),
] 