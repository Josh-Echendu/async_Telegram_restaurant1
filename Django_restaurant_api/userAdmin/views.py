import datetime
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.db.models import Sum, OuterRef, Subquery
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages


from orders.models import KITCHEN_STATUS_CHOICES, OrderBatch, Product, Restaurant, OrderBatchItem
from userAuths.models import TelegramUser, AdminUser
from .forms import AddProductForm
from .decorators import admin_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.exceptions import PermissionDenied



def get_admin_restaurant(request, restaurant_id=None):

    # 1️⃣ Get restaurant_id from URL or session
    if restaurant_id:
        request.session['restaurant_id'] = restaurant_id
    else:
        restaurant_id = request.session.get('restaurant_id')

    if not restaurant_id:
        raise PermissionDenied("No restaurant selected.")

    restaurant = get_object_or_404(Restaurant, rid=restaurant_id)

    # 3️⃣ Validate admin ownership
    if not AdminUser.objects.filter(id=request.user.id, restaurant=restaurant).exists():
        messages.error(request, "You are not authorized for this restaurant.")
        request.session.pop('restaurant_id', None)
        raise PermissionDenied("Not authorized for this restaurant.")
    
    return restaurant

@admin_required
def dashboard(request, restaurant_id=None):
    """
    Admin dashboard view for a restaurant.
    Hybrid URL + session approach:
    - Try to get restaurant_id from URL first.
    - If missing, fallback to session.
    - Validate that logged-in admin owns the restaurant.
    """

    restaurant = get_admin_restaurant(request, restaurant_id)

    # 5️⃣ Calculate revenue
    revenue = (
        OrderBatch.objects.filter(restaurant=restaurant)
        .aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    )

    # 6️⃣ Total orders
    total_orders_count = OrderBatch.objects.filter(restaurant=restaurant).count()

    # 7️⃣ All products
    all_products = Product.objects.select_related('category').filter(restaurant=restaurant)

    # 8️⃣ New telegram customers
    new_customers = TelegramUser.objects.filter(restaurant=restaurant).order_by('-date_created')[:10]

    # 9️⃣ Latest orders
    latest_orders = OrderBatch.objects.filter(restaurant=restaurant).order_by('-date_created')[:10]

    # 🔟 Monthly revenue
    this_month = timezone.now().month    

    monthly_revenue = (
        OrderBatch.objects
        .filter(date_created__month=this_month, restaurant=restaurant)
        .aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    )

    context = {
        "revenue": revenue.quantize(Decimal('0.01')),
        "monthly_revenue": monthly_revenue.quantize(Decimal('0.01')),
        "total_orders_count": total_orders_count,
        "all_products": all_products,
        "new_customers": new_customers,
        "latest_orders": latest_orders,
        "restaurant_id": restaurant_id
    }

    return render(request, "useradmin/dashboard.html", context)

        # serializer = DashboardSerializer(data)
        # return Response(serializer.data, status=status.HTTP_200_OK)

@admin_required 
def products(request, restaurant_id=None):

    restaurant = get_admin_restaurant(request, restaurant_id)

    products = Product.objects.filter(restaurant=restaurant).order_by('-id')
    return render(request, "useradmin/products.html", {"products": products})


@admin_required
def add_product(request, restaurant_id=None):

    restaurant = get_admin_restaurant(request, restaurant_id)
    if restaurant:
        print("successfull Josh")

    if request.method == "POST":
        form = AddProductForm(request.POST, request.FILES)
        if form.is_valid():
            new_product = form.save(commit=False)
            new_product.restaurant = restaurant  # isolate here
            new_product.save()
            return redirect("useradmin:dashboard-products")
    else:
        form = AddProductForm()

    return render(request, "useradmin/add-products.html", {"form": form})

@admin_required
def edit_product(request, pid, restaurant_id=None):

    restaurant = get_admin_restaurant(request, restaurant_id)

    product = get_object_or_404(
        Product,
        pid=pid,
        restaurant=restaurant
    )

    if request.method == "POST":
        form = AddProductForm(
            request.POST,
            request.FILES,
            instance=product
        )
        if form.is_valid():
            updated_product = form.save(commit=False)
            updated_product.restaurant = restaurant  # enforce isolation
            updated_product.save()
            return redirect("useradmin:dashboard-products")
    else:
        form = AddProductForm(instance=product)

    return render(
        request,
        "useradmin/edit-products.html",
        {
            "form": form,
            "product": product,
        }
    )


@admin_required
@require_POST
def delete_product(request, pid, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    product = get_object_or_404(Product, pid=pid, restaurant=restaurant)
    product.delete()
    return redirect ("useradmin:dashboard-products")


@admin_required
def orders(request, restaurant_id=None):
    # Using timezone.now() is safer for Django's settings
    this_month = timezone.now().month
    current_year = timezone.now().year

    restaurant = get_admin_restaurant(request, restaurant_id)
    

    # 1. Define the subquery correctly
    # We filter by the 'batch' field matching the 'pk' of the OrderBatch from the outer query
    
    values = OrderBatchItem.objects.all().values('batch')
    print("values....: ", values)

    qty_subquery = OrderBatchItem.objects.filter(
        batch=OuterRef('pk')
    ).values('batch').annotate(
        total_qty=Sum('quantity')
    ).values('total_qty')

    # 2. Define the base queryset
    orders = (
        OrderBatch.objects
        .filter(
            date_created__year=current_year,
            date_created__month=this_month,
            restaurant=restaurant
        )
        .select_related('restaurant', 'telegram_user')
        .order_by('-id')
        .annotate(order_qty=Subquery(qty_subquery)) # Wrap it in Subquery
    )




    # 2. Reuse the queryset for the aggregation
    # This keeps your code DRY (Don't Repeat Yourself)
    quantity_data = orders.aggregate(total_qty=Sum('items__quantity'))
    quantity = quantity_data['total_qty'] or 0
    
    context = {
        "orders": orders,
        "quantity": quantity,
    }
    return render(request, "useradmin/orders.html", context)


@admin_required
def order_details(request, bid, restaurant_id=None):

    restaurant = get_admin_restaurant(request, restaurant_id)

    # 1. We get the specific order
    # 2. We prefetch the 'items' AND their 'product' in one go
    order = get_object_or_404(
        OrderBatch.objects.prefetch_related('items__product'), 
        bid=bid,
        restaurant=restaurant
    )
    
    # Because of prefetch_related, order.items.all() is now cached in memory
    order_items = order.items.all() 
        
    return render(request, "useradmin/order-details.html", {
        "order": order, 
        "order_items": order_items
    })


@admin_required
@require_POST
def change_order_status(request, bid, restaurant_id=None):

    restaurant = get_admin_restaurant(request, restaurant_id)

    if request.method == "POST":
        order = get_object_or_404(
            OrderBatch.objects.select_related('telegram_user'),
            bid=bid,
            restaurant=restaurant
        )

        new_status = request.POST.get("status")

        if new_status in dict(KITCHEN_STATUS_CHOICES):
            order.status = new_status
            order.save(update_fields=["status"])

            messages.success(
                request,
                f"Order status updated successfully to {new_status}."
            )
    else:
        messages.error(request, "Invalid status.")

    return redirect("useradmin:order-details", bid=bid)