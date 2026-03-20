from django.urls import path
from .views import (
    restaurant_detail, category_list_api_view, category_product_api_view,remove_cart_view, add_to_cart_view, cart_list_api_view, orderbatch_list_create_view,
    update_batch_status_api_view, batch_list_api_view, dynamic_virtual_account_view, simulate_payment_api_view, squad_webhook_api_view
    )

urlpatterns = [

    # Frontend page
    path('restaurant/<str:restaurant_id>/menu/', restaurant_detail, name='restaurant-detail'),
    
    # Frontend page
    path('restaurant/<str:restaurant_id>/categories/', category_list_api_view, name='category-list-api'),
    
    path('restaurant/<str:restaurant_id>/products/<str:category_id>/', category_product_api_view),
    path('add-to-cart/', add_to_cart_view),
    path('remove-cart/', remove_cart_view),
    path('cart_list/<int:telegram_id>/', cart_list_api_view),
    path('order_batches/<str:restaurant_id>/', orderbatch_list_create_view),
    path('update_batch_status/restaurant/', update_batch_status_api_view),

    path('dva/', dynamic_virtual_account_view),
    path('dva/payment/', simulate_payment_api_view),
    path("payments/squad/webhook/", squad_webhook_api_view),

    path('user_batch_list/<int:telegram_id>/<str:restaurant_id>/', batch_list_api_view),
] 
