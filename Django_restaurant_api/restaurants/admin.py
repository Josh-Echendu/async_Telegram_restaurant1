from django.contrib import admin
from .models import Restaurant, RestaurantMembership

# Register your models here.

class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['rid', 'name', 'description', 'image']

class RestaurantMembershipAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'user', 'is_active', 'date_joined']

admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(RestaurantMembership, RestaurantMembershipAdmin)
