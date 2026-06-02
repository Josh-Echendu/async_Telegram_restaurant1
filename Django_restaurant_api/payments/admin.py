from django.contrib import admin

# Register your models here.

from .models import POSConfig

class POSConfigAdmin(admin.ModelAdmin):
    list_display = ('restaurant__name', 'brand', 'terminal_identifier', 'is_active', 'created_at')
    list_filter = ('brand', 'is_active', 'created_at')
    search_fields = ('restaurant__name', 'terminal_identifier')
    ordering = ('-created_at',)

admin.site.register(POSConfig, POSConfigAdmin)
