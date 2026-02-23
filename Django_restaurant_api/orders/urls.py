from django.urls import path
from .views import (
    category_list_api_view, category_product_api_view,remove_cart_view, add_to_cart_view, cart_list_api_view, orderbatch_list_create_view,
    update_batch_status_api_view, batch_list_api_view
    )

urlpatterns = [
    path('products/<str:cat>/<int:telegram_id>/', category_product_api_view),
    path('restaurant/<str:restaurant_id>/menu/', category_list_api_view, name='restaurant-menu'),
    path('add-to-cart/', add_to_cart_view),
    path('remove-cart/', remove_cart_view),
    path('cart_list/<int:telegram_id>/', cart_list_api_view),
    path('order_batches/', orderbatch_list_create_view),
    path('update_batch_status/', update_batch_status_api_view),
    path('user_batch_list/<int:telegram_id>/', batch_list_api_view),
] 
