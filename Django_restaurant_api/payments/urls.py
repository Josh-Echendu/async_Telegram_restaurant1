from django.urls import path
from .views import vpay_webhook_api_view



urlpatterns = [
    path('webhook/vpay/', vpay_webhook_api_view, name='vpay-webhook'),
]