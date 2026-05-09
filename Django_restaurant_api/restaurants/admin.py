from django.contrib import admin
from .models import Restaurant, RestaurantDeliveryOpeningHours, RestaurantMembership, DineInOTPSession


class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['rid', 'name', 'description', 'image', 'business_type', 'service_mode']
    
class RestaurantDeliveryOpeningHoursAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'day_of_week', 'open_time', 'close_time', 'is_closed']

class RestaurantMembershipAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'user', 'is_active', 'date_joined']

class DineInOTPSessionAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'user__username', 'table_number', 'waiter_username']


admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(RestaurantDeliveryOpeningHours, RestaurantDeliveryOpeningHoursAdmin)
admin.site.register(RestaurantMembership, RestaurantMembershipAdmin)
admin.site.register(DineInOTPSession, DineInOTPSessionAdmin)
