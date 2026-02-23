from django.urls import path
from .views import admin_login_view, admin_logout_view, telegram_user_create_api_view, telegram_list_api_view

app_name = "userauths"

urlpatterns = [
    path("register_user/", telegram_user_create_api_view),
    path('users/', telegram_list_api_view),
    path('admin_login/', admin_login_view, name='admin_login'),
    path('admin_logout/', admin_logout_view, name='admin_logout'),
]