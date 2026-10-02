from django.urls import path
from .views import get_restaurant_internal, sse_join_status, respond_to_join_api_view, request_to_join_table_api_view, check_join_status_api_view, GenerateOTPForTableAPIView, verify_otp_api_view, join_landing_redirect

app_name = "restaurants"

urlpatterns = [
    path("internal/<str:platform>/", get_restaurant_internal),
    path("internal/<str:platform>/<str:rid>/", get_restaurant_internal),
    path("dine-in/generate-otp/", GenerateOTPForTableAPIView.as_view()),
    path("dine-in/verify-otp/", verify_otp_api_view),
    path("join/<str:session_token>/", join_landing_redirect),
    path("dine-in/request-join/", request_to_join_table_api_view),
    path("dine-in/respond-join/", respond_to_join_api_view),
    
    path("dine-in/join-status/<int:participant_id>/", check_join_status_api_view),
    
    path(
        'sse/join-status/<str:restaurant_id>/<str:platform>/<str:user_id>/',
        sse_join_status,
        name='sse_join_status'
    ),


]