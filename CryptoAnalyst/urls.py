from django.urls import path
from .views import TechnicalIndicatorsAPIView, TokenDataAPIView

urlpatterns = [
    path('technical-indicators/<str:symbol>/', TechnicalIndicatorsAPIView.as_view(), name='technical-indicators'),
    path('token-data/<str:token_id>/', TokenDataAPIView.as_view(), name='token-data'),
] 