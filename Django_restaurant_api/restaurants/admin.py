from django.contrib import admin
from .models import Restaurant, RestaurantDeliveryOpeningHours, RestaurantMembership
# Register your models here.

class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['rid', 'name', 'description', 'image']
    
class RestaurantDeliveryOpeningHoursAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'day_of_week', 'open_time', 'close_time', 'is_closed']

class RestaurantMembershipAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'user', 'is_active', 'date_joined']

admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(RestaurantDeliveryOpeningHours, RestaurantDeliveryOpeningHoursAdmin)
admin.site.register(RestaurantMembership, RestaurantMembershipAdmin)
