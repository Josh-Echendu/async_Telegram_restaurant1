from django.urls import path
from .views import get_restaurant_internal, GenerateOTPForTableAPIView, verify_otp_api_view

app_name = "restaurants"

urlpatterns = [
    path("internal/<str:platform>/", get_restaurant_internal),
    path("internal/<str:platform>/<str:rid>/", get_restaurant_internal),
    path("dine-in/generate-otp/", GenerateOTPForTableAPIView.as_view()),
    path("dine-in/verify-otp/", verify_otp_api_view),
]