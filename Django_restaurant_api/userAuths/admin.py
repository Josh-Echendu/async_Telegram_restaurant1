from django.contrib import admin
from .models import AdminUser, TelegramUser, AuthToken

# Register your models here.


class telegramUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'first_name', 'username', 'is_active', 'date_created')
    search_fields = ('telegram_id', 'first_name', 'username')
    list_filter = ('is_active', 'date_created')
    
class adminUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'user_name', 'is_staff', 'is_active', 'is_superuser', 'date_created', 'last_login')
    search_fields = ('email', 'user_name')
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'date_created')

class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ('token', 'user_id')
    search_fields = ('token', 'user_id')

admin.site.register(AdminUser)
admin.site.register(TelegramUser)
admin.site.register(AuthToken, AuthTokenAdmin)
