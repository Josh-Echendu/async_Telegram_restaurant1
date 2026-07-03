from django.urls import path

from .views import vpay_webhook_api_view, dine_in_paymentview, create_payment_session, handle_payment_selection


urlpatterns = [
    path('webhook/vpay/', vpay_webhook_api_view, name='vpay-webhook'),
    path('<str:restaurant_id>/<str:platform>/<str:session_id>/', dine_in_paymentview, name='create-payment'),
    path('api/create-payment-session/', create_payment_session, name='create-payment-session'),
    path('api/handle-payment-selection/', handle_payment_selection, name='handle-payment-selection'),
]