from django.urls import path
from .views import change_order_status, dashboard, edit_product, order_details, orders, products, add_product, delete_product

app_name = "useradmin"

urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("products/", products, name="dashboard-products"),
    path("add_product/", add_product, name="dashboard-add-products"),
    path("edit_product/<str:pid>/", edit_product, name="edit-products"),
    path("delete_product/<str:pid>/", delete_product, name="delete-products"),
    path("orders/", orders, name="dashboard-orders"),
    path("order_details/<str:bid>/", order_details, name="order-details"),
    path("change_status/<str:bid>/", change_order_status, name="order-change-status"),
]