import datetime
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.db.models import Sum
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages


from orders.models import KITCHEN_STATUS_CHOICES, OrderBatch, Product
from userAuths.models import TelegramUser
from .forms import AddProductForm
from .decorators import admin_required
from django.views.decorators.http import require_POST
from django.contrib import messages


@admin_required
def dashboard(request):
    revenue = (
        OrderBatch.objects
        .aggregate(total=Sum('total_price'))['total'] or 0
    )
    print("revenue: ", revenue.quantize(Decimal('0.01')))

    total_orders_count = OrderBatch.objects.count()

    all_products = Product.objects.select_related('category').all()

    new_customers = TelegramUser.objects.order_by('-date_created')[:10]

    latest_orders = OrderBatch.objects.order_by('-date_created')[:10]

    this_month = datetime.datetime.now().month
    monthly_revenue = (
        OrderBatch.objects
        .filter(date_created__month=this_month)
        .aggregate(total=Sum('total_price'))['total'] or 0
    )

    context = {
        "revenue": revenue,
        "monthly_revenue": monthly_revenue,
        "total_orders_count": total_orders_count,
        "all_products": all_products,
        "new_customers": new_customers,
        "latest_orders": latest_orders,
    }

    return render(request, "useradmin/dashboard.html", context)

        # serializer = DashboardSerializer(data)
        # return Response(serializer.data, status=status.HTTP_200_OK)

@admin_required 
def products(request):
    products = Product.objects.all().order_by('-id')
    return render(request, "useradmin/products.html", {"products": products})

@admin_required
def add_product(request):
    if request.method == "POST":
        form = AddProductForm(request.POST, request.FILES) # request.FILES: to accept images
        if form.is_valid():
            new_form = form.save(commit=False)
            # new_form.user = request.user
            new_form.save()
            # form.save_m2m() # to save many-to-many relationships if any
            return redirect ("useradmin:dashboard-products") # redirect to dashboard after adding product
    
    else:
        form = AddProductForm()

    context = {
        "form": form
    }

    return render(request, "useradmin/add-products.html", context) 

@admin_required
def edit_product(request, pid):
    product = Product.objects.get(pid=pid)
    if request.method == "POST":
        form = AddProductForm(request.POST, request.FILES, instance=product) # request.FILES: to accept images
        if form.is_valid():
            new_form = form.save(commit=False)
            # new_form.user = request.user
            new_form.save()
            # form.save_m2m() # to save many-to-many relationships if any
            return redirect ("useradmin:dashboard-products") # redirect to dashboard after adding product
    
    else:
        form = AddProductForm(instance=product)

    context = {
        "form": form,
        "product": product,
    }

    return render(request, "useradmin/edit-products.html", context) 

@admin_required
def delete_product(request, pid):
    product = Product.objects.get(pid=pid)
    product.delete()
    return redirect ("useradmin:dashboard-products")


@admin_required
def orders(request):
    this_month = datetime.datetime.now().month
    orders = OrderBatch.objects.filter(date_created__month=this_month).order_by('-id')
    print("orders: ", orders.count())

    quantity = (
        OrderBatch.objects
        .filter(date_created__month=this_month)
        .prefetch_related('items')
        .aggregate(quantity=Sum('items__quantity'))
    )['quantity'] or 0
    
    context = {
        "orders": orders,
        "quantity": quantity,
    }
    return render(request, "useradmin/orders.html", context)

@admin_required
def order_details(request, bid):
    order = OrderBatch.objects.get(bid=bid)
    order_items = order.items.all() # Assuming you have a related name 'items' for the products in the order
        
    return render(request, "useradmin/order-details.html", {"order": order, "order_items": order_items})


@admin_required
@require_POST
def change_order_status(request, bid):
    if request.method == "POST":
        order = get_object_or_404(
            OrderBatch.objects.select_related('telegram_user'),
            bid=bid
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