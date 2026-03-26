from django.contrib import admin
from .models import Restaurant

# Register your models here.

class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['rid', 'name', 'description', 'image']

admin.site.register(Restaurant, RestaurantAdmin)
