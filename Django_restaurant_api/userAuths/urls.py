from django.urls import path
from .views import admin_login_view, admin_logout_view, whatsapp_callback_view, whatsapp_login, whatsapp_callback_view, whatsapp_init_session_api_view, whatsapp_user_create_api_view, telegram_user_create_api_view, telegram_list_api_view

app_name = "userauths"

urlpatterns = [
    path("register_user/restaurant/telegram/", telegram_user_create_api_view),
    path("register_user/restaurant/whatsapp/", whatsapp_user_create_api_view),
    
    path("whatsapp/init_session/", whatsapp_init_session_api_view),
    path("whatsapp/callback/<str:restaurant_id>/", whatsapp_callback_view),
    path("whatsapp/login/<str:restaurant_id>/", whatsapp_login),



    path('users/', telegram_list_api_view),
    path('admin_login/restaurant/<str:restaurant_id>/', admin_login_view, name='admin_login'),
    path('admin_logout/', admin_logout_view, name='admin_logout'),
]