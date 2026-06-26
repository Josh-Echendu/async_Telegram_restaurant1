from django.urls import path
from .views import (change_order_status, categories, add_category, 
                    edit_category, delete_category, dashboard,
                    edit_product, products, add_product, delete_product,
                    delivery_hours, update_delivery_hours, dine_in_orders, delivery_orders,
                    dine_in_order_details, delivery_order_details, pos_config, shop_settings,
                    update_shop_settings, get_whatsapp_pairing_code, metaoauthhandshake_api_view
                    
)

app_name = "useradmin"

urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),

    path("products/", products, name="dashboard-products"),
    path("add_product/", add_product, name="dashboard-add-products"),

    path("categories/", categories, name="dashboard-categories"),
    path("add-category/", add_category, name="dashboard-add-category"),
    path("edit-category/<str:cid>/", edit_category, name="edit-category"),
    path("delete-category/<str:cid>/", delete_category, name="delete-category"),

    path("edit_product/<str:pid>/", edit_product, name="edit-products"),
    path("delete_product/<str:pid>/", delete_product, name="delete-products"),

    path("delivery-hours/", delivery_hours, name="delivery-hours"),
    path("delivery-hours/update/", update_delivery_hours, name="update-delivery-hours"),

    path("dine_orders/", dine_in_orders, name="dashboard-dine_in-orders"),
    path("delivery_orders/", delivery_orders, name="dashboard-delivery-orders"),

    path("orders/dine-in/<str:session_id>/", dine_in_order_details, name="dine-in-order-details"),
    path("orders/delivery/<str:session_id>/", delivery_order_details, name="delivery-order-details"),

    # meta callback
    path('api/v1/auth/meta-callback/', metaoauthhandshake_api_view, name='meta-callback'),

    path("pos-config/", pos_config, name="pos-config"),
    path("shop-settings/", shop_settings, name="shop-settings"),
    path("shop-settings/update/", update_shop_settings, name="update-shop-settings"),
    path("whatsapp-pairing-code/", get_whatsapp_pairing_code, name="whatsapp-pairing-code"),



    path("change_status/<str:bid>/", change_order_status, name="order-change-status"),
]