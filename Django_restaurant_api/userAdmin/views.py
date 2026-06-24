from datetime import date, timedelta, time  # For TimeField defaults
from django.db.models.functions import TruncDate
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.db.models import Sum, OuterRef, Subquery, Count
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
import math
import redis
from django.conf import settings
from orders.models import KITCHEN_STATUS_CHOICES, OrderBatch, Product, OrderBatchItem, Category, CheckoutSession
from userAuths.models import TelegramUser, AdminUser
from .forms import AddProductForm, AddCategoryForm
from .decorators import admin_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from restaurants.models import Restaurant, RestaurantDeliveryOpeningHours
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.db.models import Count, Q
import json



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

    # 5️⃣ All-time revenue (paid only)
    revenue = (
        OrderBatch.objects.filter(
            checkout_session__restaurant=restaurant,
            payment_status='paid'
        ).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    )

    # 6️⃣ Total orders (all batches)
    total_orders_count = OrderBatch.objects.filter(
        checkout_session__restaurant=restaurant
    ).count()

    # 7️⃣ All products
    all_products = Product.objects.select_related('category').filter(restaurant=restaurant)

    # 8️⃣ New customers this month
    new_customers = TelegramUser.objects.filter(
        users__restaurant=restaurant,
        users__is_active=True
    ).order_by('-date_created')[:10]

    # Latest checkout sessions (not batches)
    latest_orders = (
        CheckoutSession.objects
        .filter(restaurant=restaurant)
        .select_related('telegram_user')
        .annotate(
            total_batch_price=Sum('session_batches__total_price')
        )
        .order_by('-date_created')[:10]
    )
 
    # 🔟 Monthly revenue
    today = date.today()
    this_month = today.month
    this_year = today.year

    print("this_month: ", this_month)
    print("this_year: ", this_year)
    print("timezone.now(): ", timezone.now())

    monthly_revenue = (
        OrderBatch.objects.filter(
            checkout_session__restaurant=restaurant,
            checkout_session__date_created__month=this_month,
            checkout_session__date_created__year=this_year,
            payment_status='paid'
        ).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    )

    print("monthly_revenue: ", monthly_revenue)

    context = {
        "revenue": revenue.quantize(Decimal('0.01')),
        "monthly_revenue": monthly_revenue.quantize(Decimal('0.01')),
        "total_orders_count": total_orders_count,
        "all_products": all_products,
        "new_customers": new_customers,
        "latest_orders": latest_orders,
        "restaurant_id": restaurant_id,
        "restaurant": restaurant,
    }

    return render(request, "useradmin/dashboard.html", context)

        # serializer = DashboardSerializer(data)
        # return Response(serializer.data, status=status.HTTP_200_OK)



@admin_required 
def products(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)

    products_list = Product.objects.filter(restaurant=restaurant).order_by('-id')
    
    # Filter by stock status
    status = request.GET.get('status', 'all')
    if status == 'in_stock':
        products_list = products_list.filter(in_stock=True)
    elif status == 'out_of_stock':
        products_list = products_list.filter(in_stock=False)
    
    paginator = Paginator(products_list, 5)
    page = request.GET.get('page')
    products = paginator.get_page(page)
    
    context = {
        'products': products,
        'current_status': status,
    }
    return render(request, "useradmin/products.html", context)

@admin_required
def add_product(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)

    if request.method == "POST":
        form = AddProductForm(request.POST, request.FILES, restaurant=restaurant)
        if form.is_valid():
            new_product = form.save(commit=False)
            new_product.restaurant = restaurant
            new_product.save()
            return redirect("useradmin:dashboard-products")
    else:
        form = AddProductForm(restaurant=restaurant)

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
            instance=product,
            restaurant=restaurant,  # filter category dropdown
        )
        if form.is_valid():
            updated_product = form.save(commit=False)
            updated_product.restaurant = restaurant
            updated_product.save()
            return redirect("useradmin:dashboard-products")
    else:
        form = AddProductForm(
            instance=product,
            restaurant=restaurant,  # filter category dropdown
        )

    return render(
        request,
        "useradmin/edit-products.html",
        {
            "form": form,
            "product": product,
        }
    )


@admin_required
def add_category(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    business_type = restaurant.business_type  # 'restaurant', 'vendor', or 'hotel'

    if request.method == 'POST':
        form = AddCategoryForm(
            request.POST,
            request.FILES,
            restaurant=restaurant,
            business_type=business_type,
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('useradmin:dashboard-categories')
    else:
        form = AddCategoryForm(
            restaurant=restaurant,
            business_type=business_type,
        )

    context = {
        'form': form,
        'business_type': business_type,
    }
    return render(request, 'useradmin/add-category.html', context)


@admin_required
def categories(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    categories_list = Category.objects.filter(restaurant=restaurant).order_by('title')
    paginator = Paginator(categories_list, 5)
    page = request.GET.get('page')
    categories = paginator.get_page(page)
    return render(request, "useradmin/categories.html", {"categories": categories})


@admin_required
def edit_category(request, cid, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)

    category = get_object_or_404(
        Category,
        cid=cid,
        restaurant=restaurant
    )

    if request.method == "POST":
        form = AddCategoryForm(
            request.POST,
            request.FILES,
            instance=category,
            restaurant=restaurant,
            business_type=restaurant.business_type,
        )
        if form.is_valid():
            form.save()
            return redirect("useradmin:dashboard-categories")
    else:
        form = AddCategoryForm(
            instance=category,
            restaurant=restaurant,
            business_type=restaurant.business_type,
        )

    return render(
        request,
        "useradmin/edit-category.html",
        {
            "form": form,
            "category": category,
            "business_type": restaurant.business_type,
        }
    )


def delete_category(request, cid, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    category = get_object_or_404(Category, cid=cid, restaurant=restaurant)
    category.delete()
    return redirect ("useradmin:dashboard-categories")


@admin_required
@require_POST
def delete_product(request, pid, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    product = get_object_or_404(Product, pid=pid, restaurant=restaurant)
    product.delete()
    return redirect ("useradmin:dashboard-products")


# @admin_required
# def orders(request, restaurant_id=None):
#     # Using timezone.now() is safer for Django's settings
#     this_month = timezone.now().month
#     current_year = timezone.now().year

#     restaurant = get_admin_restaurant(request, restaurant_id)
    
#     # 1. Define the subquery correctly
#     # We filter by the 'batch' field matching the 'pk' of the OrderBatch from the outer query
    
#     values = OrderBatchItem.objects.all().values('batch')
#     print("values....: ", values)

#     qty_subquery = OrderBatchItem.objects.filter(
#         batch=OuterRef('pk')
#     ).values('batch').annotate(
#         total_qty=Sum('quantity')
#     ).values('total_qty')

#     # 2. Define the base queryset
#     orders = (
#         OrderBatch.objects
#         .filter(
#             date_created__year=current_year,
#             date_created__month=this_month,
#             restaurant=restaurant
#         )
#         .select_related('restaurant', 'telegram_user')
#         .order_by('-id')
#         .annotate(order_qty=Subquery(qty_subquery)) # Wrap it in Subquery
#     )

#     # 2. Reuse the queryset for the aggregation
#     # This keeps your code DRY (Don't Repeat Yourself)
#     quantity_data = orders.aggregate(total_qty=Sum('items__quantity'))
#     quantity = quantity_data['total_qty'] or 0
    
#     context = {
#         "orders": orders,
#         "quantity": quantity,
#     }
#     return render(request, "useradmin/orders.html", context)



from datetime import date, timedelta
from django.db.models import Sum
from django.core.paginator import Paginator



@admin_required
def dine_in_orders(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    
    sessions = (
        CheckoutSession.objects
        .select_related('restaurant', 'telegram_user')
        .filter(restaurant=restaurant, service_mode='dine_in')
        .prefetch_related('session_batches__items__product')
        .annotate(
            total_batch_price=Sum('session_batches__total_price'),
        )
        .order_by('-date_created')
    )

    
    if restaurant.business_type == 'hotel':
        sessions = sessions.filter(payment_status='paid')
    
    # Status filter — only for restaurant
    status = 'all'
    if restaurant.business_type == 'restaurant':
        status = request.GET.get('status', 'all').lower()
        if status == 'paid':
            sessions = sessions.filter(payment_status='paid')
        elif status == 'unpaid':
            sessions = sessions.filter(payment_status='unpaid')
    
    # Date filter
    selected_date = request.GET.get('date', '')
    if selected_date:
        if selected_date == 'this_week':
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())
            sessions = sessions.filter(date_created__date__gte=start_of_week)
        else:
            sessions = sessions.filter(date_created__date=selected_date)

    # Stats — from filtered sessions
    session_ids = sessions.values_list('id', flat=True)

    # total_batches = OrderBatch.objects.filter(checkout_session__id__in=session_ids).count()
    # paid_batches = OrderBatch.objects.filter(checkout_session__id__in=session_ids, payment_status='paid').count()
    # unpaid_batches = OrderBatch.objects.filter(checkout_session__id__in=session_ids, payment_status='unpaid').count()
    # total_revenue = OrderBatch.objects.filter(checkout_session__id__in=session_ids, payment_status='paid').aggregate(total=Sum('total_price'))['total'] or 0


    stats = OrderBatch.objects.filter(
        checkout_session__id__in=session_ids,
    ).aggregate(
        total_batches=Count('id'),
        paid_batches=Count('id', filter=Q(payment_status='paid')),
        unpaid_batches=Count('id', filter=Q(payment_status='unpaid')),
        total_revenue=Sum('total_price', filter=Q(payment_status='paid')),
    )

    total_batches = stats['total_batches']
    paid_batches = stats['paid_batches']
    unpaid_batches = stats['unpaid_batches']
    total_revenue = stats['total_revenue'] or 0

    total_vat_price=sessions.aggregate(vat=Sum('vat_amount'))['vat'] or 0
    paginator = Paginator(sessions, 20)
    page = request.GET.get('page')
    orders = paginator.get_page(page)

    today = date.today()
    yesterday = today - timedelta(days=1)
    
    context = {
        'orders': orders,
        'current_mode': 'dine_in',
        'current_status': status,
        'restaurant': restaurant,
        "total_vat_price": total_vat_price,
        'total_orders': total_batches,
        'paid_orders': paid_batches,
        'unpaid_orders': unpaid_batches,
        'total_revenue': total_revenue,
        'selected_date': selected_date,
        'today_str': today.isoformat(),
        'yesterday_str': yesterday.isoformat(),
    }

    return render(request, 'useradmin/dine_in_orders.html', context)


@admin_required
def delivery_orders(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    
    sessions = (
        CheckoutSession.objects
        .select_related('restaurant', 'telegram_user')
        .filter(restaurant=restaurant, service_mode='delivery', payment_status='paid')
        .prefetch_related('session_batches__items__product')
        .annotate(
            total_batch_price=Sum('session_batches__total_price'),
        )
        .order_by('-date_created')
    )
    
    # Date filter
    selected_date = request.GET.get('date', '')
    if selected_date:
        if selected_date == 'this_week':
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())
            sessions = sessions.filter(date_created__date__gte=start_of_week)
        else:
            sessions = sessions.filter(date_created__date=selected_date)
            

    # # Stats — from filtered sessions
    # session_ids = sessions.values_list('id', flat=True)
    # total_batches = OrderBatch.objects.filter(checkout_session__id__in=session_ids).count()
    # paid_batches = OrderBatch.objects.filter(checkout_session__id__in=session_ids, payment_status='paid').count()
    # unpaid_batches = OrderBatch.objects.filter(checkout_session__id__in=session_ids, payment_status='unpaid').count()
    # total_revenue = OrderBatch.objects.filter(checkout_session__id__in=session_ids, payment_status='paid').aggregate(total=Sum('total_price'))['total'] or 0
    

    session_ids = sessions.values_list('id', flat=True)

    stats = OrderBatch.objects.filter(
        checkout_session__id__in=session_ids,
    ).aggregate(
        total_batches=Count('id'),
        paid_batches=Count('id', filter=Q(payment_status='paid')),
        unpaid_batches=Count('id', filter=Q(payment_status='unpaid')),
        total_revenue=Sum('total_price', filter=Q(payment_status='paid'))
    )

    total_batches = stats['total_batches']
    paid_batches = stats['paid_batches']
    unpaid_batches = stats['unpaid_batches']
    total_revenue = stats['total_revenue'] or 0

    
    total_vat_price=sessions.aggregate(vat=Sum('vat_amount'))['vat'] or 0
    paginator = Paginator(sessions, 20)
    page = request.GET.get('page')
    orders = paginator.get_page(page)

    today = date.today()
    yesterday = today - timedelta(days=1)
    
    context = {
        'orders': orders,
        'current_mode': 'delivery',
        'current_status': 'paid',
        "total_vat_price": total_vat_price,
        'restaurant': restaurant,
        'total_orders': total_batches,
        'paid_orders': paid_batches,
        'unpaid_orders': unpaid_batches,
        'total_revenue': total_revenue,
        'selected_date': selected_date,
        'today_str': today.isoformat(),
        'yesterday_str': yesterday.isoformat(),
    }

    return render(request, 'useradmin/delivery_orders.html', context)



@admin_required
def dine_in_order_details(request, session_id, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    
    session = get_object_or_404(
        CheckoutSession.objects
        .select_related('telegram_user', 'restaurant', 'dine_session')
        .prefetch_related('session_batches__items__product')
        .annotate(
            total_batch_price=Sum('session_batches__total_price')
        ),
        session_id=session_id,
        restaurant=restaurant,
        service_mode='dine_in'
    )
    
    batches = []
    for batch in session.session_batches.all():
        items = []
        for item in batch.items.all():

            items.append({
                'product': item.product,
                'price': item.price,
                'quantity': item.quantity,
                'multiply_price': item.price * item.quantity,
            })
        batches.append({
            'bid': batch.bid,
            'items': items,
            'total_price': batch.total_price,
            'status': batch.status,
            'payment_status': batch.payment_status,
            'notified_kitchen': batch.notified_kitchen,
            'notified_user': batch.notified_user,
            'bank_charges': session.bank_fee
        })
    
    print("batches: ", batches)
    context = {
        'order': session,
        'batches': batches,
        'vat_amount': session.vat_amount or 0,
    }
    return render(request, 'useradmin/dine_in_order_details.html', context)


@admin_required
def delivery_order_details(request, session_id, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    
    session = get_object_or_404(
        CheckoutSession.objects
        .select_related('telegram_user', 'restaurant')
        .prefetch_related('session_batches__items__product')
        .annotate(
            total_batch_price=Sum('session_batches__total_price')
        ),
        session_id=session_id,
        restaurant=restaurant,
        service_mode='delivery',
        payment_status='paid'
    )
    
    order_items = []
    for batch in session.session_batches.all():
        for item in batch.items.all():
            order_items.append({
                'product': item.product,
                'price': item.price,
                'quantity': item.quantity,
                'multiply_price': item.price * item.quantity,
            })
    
    context = {
        'order': session,
        'order_items': order_items,
        'vat_amount': session.vat_amount or 0,
    }
    return render(request, 'useradmin/delivery_order_details.html', context)




@admin_required
def pos_config(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    return render(request, 'useradmin/pos_config.html', {'restaurant': restaurant})

# Bot: "Order confirmed! 🍽️
#       Jollof Rice - ₦2,000
#       Chicken - ₦1,500
#       Total: ₦3,500
      
#       Reply STOP to opt out of messages"

# Actually honor "STOP" messages. If a customer opts out, flag them. Don't send confirmations to opted-out numbers. 
# This is a WhatsApp requirement, not optional.

# Don't send identical message templates. Add slight variations — timestamps, order IDs, restaurant names.
# Identical messages across multiple bots look like a bot farm.


@admin_required
def shop_settings(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    return render(request, 'useradmin/settings.html', {'restaurant': restaurant})



# [providers.models."custom:http://localhost:11434"]
# base_url = "http://localhost:11434"
# max_tokens = 4096
# temperature = 0.8
# timeout_secs = 600
# wire_api = "chat_completions"

@require_POST
@admin_required
def update_shop_settings(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    
    # ---- business_type ----
    if 'business_type' in request.POST:
        if restaurant.business_type:
            return JsonResponse({'error': 'Business type cannot be changed after registration.'}, status=400)
        value = (request.POST['business_type'] or "").lower()
        if value not in ('restaurant', 'vendor', 'hotel'):
            return JsonResponse({'error': 'Invalid business type.'}, status=400)
        restaurant.business_type = value
        if value == 'vendor':
            restaurant.service_mode = 'delivery'
        elif value == 'hotel':
            restaurant.service_mode = 'dine_in'

    # ---- vendor_type ----
    if 'vendor_type' in request.POST:
        if restaurant.vendor_type:
            return JsonResponse({'error': 'Vendor type cannot be changed after registration.'}, status=400)
        value = request.POST['vendor_type']
        if value not in ('cooked_food', 'goods'):
            return JsonResponse({'error': 'Invalid vendor type.'}, status=400)
        restaurant.vendor_type = value

    # ---- all other fields ----
    updatable_fields = [
        'first_name', 'last_name', 'phone_number',
        'name', 'description', 'state', 'lga', 'address',
        'service_mode', 'delivery_fee',
        'max_tables', 'timezone', 'is_accepting_orders',
        'bank_account_name', 'bank_account_number',
        'bot_username', 'bot_token', 'is_bot_active',
        'whatsapp_business_phone', 'whatsapp_business_account_id',
        'whatsapp_phone_number_id', 'whatsapp_access_token', 'is_whatsapp_active',
    ]
    
    for field in updatable_fields:
        if field in request.POST:
            value = request.POST[field]
            if value == 'true':
                value = True
            elif value == 'false':
                value = False
            setattr(restaurant, field, value)

    if 'image' in request.FILES:
        restaurant.image = request.FILES['image']

    restaurant.save()

    # After save, register in Redis for baileys
    if restaurant.whatsapp_business_phone:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.hset('whatsapp:restaurants', restaurant.rid, restaurant.whatsapp_business_phone)
        # Worker.js will pick this up within 5 seconds and generate pairing code

    
    

    return JsonResponse({'success': True})



def get_whatsapp_pairing_code(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    
    import redis, json
    r = redis.Redis.from_url(settings.REDIS_URL)
    data = r.hget('whatsapp:setup', restaurant.rid)
    
    if data:
        setup = json.loads(data)
        return JsonResponse({
            'code': setup.get('pairingCode'),
            'qr': setup.get('qr'),
        })
    
    return JsonResponse({'error': 'No pairing code available'}, status=404)




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



@ensure_csrf_cookie
@admin_required
def delivery_hours(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)

    # Block non-delivery restaurants
    if restaurant.business_type not in ('restaurant', 'vendor'):
        messages.error(request, "Delivery hours are only available for restaurants and vendors.")
        return redirect('useradmin:dashboard')
    
    if restaurant.business_type == 'restaurant' and restaurant.service_mode not in ('delivery', 'both'):
        messages.error(request, "Your restaurant does not offer delivery. Update your service mode first.")
        return redirect('useradmin:dashboard')
    
    for day in range(7):
        # Sunday = both None (closed), Mon-Sat = 9-5
        if day == 6:
            defaults = {'open_time': None, 'close_time': None}
        else:
            defaults = {'open_time': time(9, 0), 'close_time': time(17, 0)}
        
        RestaurantDeliveryOpeningHours.objects.get_or_create(
            restaurant=restaurant,
            day_of_week=day,
            defaults=defaults,
        )
    
    hours = RestaurantDeliveryOpeningHours.objects.filter(
        restaurant=restaurant
    ).order_by('day_of_week')
    
    context = {
        'hours': hours,
        'restaurant': restaurant,
    }
    return render(request, 'useradmin/delivery-hours.html', context)


@require_POST
@admin_required
def update_delivery_hours(request, restaurant_id=None):
    restaurant = get_admin_restaurant(request, restaurant_id)
    
    day = int(request.POST.get('day_of_week'))
    open_time = request.POST.get('open_time') or None
    close_time = request.POST.get('close_time') or None
    print("request data: ", request.POST)
    
    hour, _ = RestaurantDeliveryOpeningHours.objects.get_or_create(
        restaurant=restaurant,
        day_of_week=day,
    )
    
    # Both empty = closed. Both filled = open.
    if open_time and close_time:
        hour.open_time = open_time
        hour.close_time = close_time
    else:
        hour.open_time = None
        hour.close_time = None
    
    hour.save()
    
    return JsonResponse({'success': True})
