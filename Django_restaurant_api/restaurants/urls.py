from django.urls import path
from .views import get_restaurant_internal

app_name = "restaurants"

urlpatterns = [
    path("internal/<str:rid>/", get_restaurant_internal),

]