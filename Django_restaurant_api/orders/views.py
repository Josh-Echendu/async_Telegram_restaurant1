from datetime import timedelta
import time
from django.utils import timezone
from decimal import Decimal
from django.shortcuts import render
import uuid

import requests

from .redis_client import redis_client
from userAuths.models import TelegramUser
from rest_framework.generics import (
    CreateAPIView, ListAPIView, RetrieveAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
)
from rest_framework.response import Response  # ✅ CORRECT
from .serializers import CartSerializer, CategorySerializer, OrderBatchSerializer, ProductSerializer
from .models import KITCHEN_STATUS_CHOICES, Cart, Category, OrderBatch, OrderBatchItem, Product, Restaurant, CheckoutSession
from rest_framework.permissions import IsAuthenticated , AllowAny
import json
import httpx
from rest_framework.pagination import LimitOffsetPagination 
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db.models import OuterRef, Subquery, Sum, Value, F
from django.db.models.functions import Coalesce
from django.http import Http404
from rest_framework import status
from django.db import transaction, IntegrityError
from .tasks import send_order_notifications, process_squad_webhook, requery_transaction
from .throttles import TelegramScopedThrottle  # import the custom throttle
from .virtual_account import initiate_dynamic_virtual_account
from dateutil import parser
from .squad_signature_helper import verify_squad_signature


import logging
logger = logging.getLogger(__name__)

def restaurant_detail(request, restaurant_id):
    print("restaurant_id in view: ", restaurant_id)
    return render(request, 'restaurant/restaurant_detail.html')

class CategoryListApiView(ListAPIView):
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None  # No pagination, we want all categories

    def get_queryset(self):
        restaurant_id = self.kwargs.get("restaurant_id")
        if not restaurant_id:
            raise Http404("Category or restaurant ID missing")

        restaurant = get_object_or_404(Restaurant, rid=restaurant_id)
        return Category.objects.filter(restaurant=restaurant).select_related('restaurant')
    
category_list_api_view = CategoryListApiView.as_view()

# OuterRef → used inside a Subquery to refer to a field from the outer/main query.
# Subquery → lets you embed a query inside another query, basically “I want this small query’s result for each row of my main query.”

# Custom pagination for Telegram bot
class TelegramLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 9      # how many items per "page"
    max_limit = 9          # max items the bot can fetch at once

class CategoryProductsApiView(ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
            
    def list(self, request, *args, **kwargs):

        # Extract both restuarant_id and category_id from URL kwargs
        restaurant_id = self.kwargs.get("restaurant_id")
        category_id = self.kwargs.get("category_id")

        if not restaurant_id and not category_id:
            raise Http404("Category or restaurant ID missing")
        
        # get_object_or_404(Category, cid=category_id)
        # get_object_or_404(Restaurant, rid=restaurant_id)

        # Extract all products for a restaurant, ordered by newest first
        all_products = Product.objects.filter(
            restaurant__rid=restaurant_id
        ).order_by('-date')

        # serialize all products once for the "all" category
        all_data = ProductSerializer(all_products, many=True).data

        if category_id == "all":
            return Response({
                "category_products": all_data,
                "all": all_data
            })

        # Extract all products for the specific category
        category_products = all_products.filter(
            category__cid=category_id
        )

        # serialize category products 
        category_data = ProductSerializer(category_products, many=True).data
        print("category_data: ", category_data)

        return Response({
            "category_products": category_data,
            "all": all_data
        })
    
category_product_api_view = CategoryProductsApiView.as_view()
    

class AddToCartAPIView(APIView): 
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        try:
            print("requests: ", request)
            product_id = int(request.data.get("id"))
            telegram_id = int(request.data.get("telegram_id"))
        except (TypeError, ValueError):

            # ✅ Bad request if ID or quantity is invalid
            return Response(
                {"error": "Invalid product ID or quantity or telegram_id"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
        except TelegramUser.DoesNotExist:
            return Response(
                {"detail": "Telegram user does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # If exactly one row is found → returns it, If zero rows are found → raises Http404
            product = get_object_or_404(Product.objects.only('id', 'title', 'price'), pk=product_id, in_stock=True) # if Product exists but out of stock, Raises 404
        except Http404:
            Cart.objects.filter(product_id=product_id, telegram_user=telegram_user).delete()
            return Response(
                {"error": "Product not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # try:
        #     product = Product.objects.get(pk=product_id, in_stock=True)
        # except Product.DoesNotExist:
        #     Cart.objects.filter(product_id=product_id).delete()
        #     return Response(
        #         {"error": "Product no longer available and was removed from your cart."},
        #         status=410  # Gone
        #     )

        
        try:
            # 🚀 Atomic insert or update
            cart_item, created = Cart.objects.select_for_update().get_or_create( # Created: True if newly created, False if already existed
                product=product,
                telegram_user=telegram_user,
                defaults={'quantity': int(1)}, # 👉 defaults only applies when creating, not when fetching.
            )
            if not created: # if cart already exist
                
                # ⚡ Atomic DB-level increment (no race condition)
                Cart.objects.filter(pk=cart_item.pk, telegram_user=telegram_user).update(quantity=F("quantity") + int(1))# 🧠 What is F("quantity")?: "Use the current value of the quantity column."
                cart_item.refresh_from_db(fields=['quantity']) # “Reload the latest quantity from the database into cart_item.quantity.”
                print("already created")
        
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # ✅ Success → 201 CREATED if new, 200 OK if updated
        return Response(
            {
                "product_name": cart_item.product.title,
                "quantity": cart_item.quantity,
                'price': product.price,
                "total_price": cart_item.multiply_price(),
                "message": "Added to cart successfully!"
            },
            status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
add_to_cart_view = AddToCartAPIView.as_view()

# Cart.objects.select_related('product') → performs a SQL JOIN between Cart and Product.
# .only("id", "quantity", "price", "product__title") → fetches only these columns from both tables

# SELECT cart.id, cart.quantity, cart.price, product.title
# FROM cart
# JOIN product ON cart.product_id = product.id
# WHERE cart.id = 1;

class DecreaseCartAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            product_id = int(request.data.get("id"))
            telegram_id = int(request.data.get('telegram_id'))

        except (TypeError, ValueError):
            return Response({"error": "Invalid product ID or telegram_id"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
        except TelegramUser.DoesNotExist:
            return Response(
                {"detail": "Telegram user does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )
        try:
            # Fetches only needed columns → less memory usage
            get_object_or_404(Product.objects.only('id', 'title', 'price'), pk=product_id, in_stock=True)
        except Http404:
            Cart.objects.filter(product_id=product_id, telegram_user=telegram_user).delete()
            return Response(
                {"error": "Product not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # ⚡ Single fast query (JOIN product, fetch only needed fields)
        try:
            cart_item = get_object_or_404(
                Cart.objects.select_related("product").only(
                    "id", "quantity", "product__title", "product__price"
                ),
                telegram_user=telegram_user,
                product_id=product_id,
            )
        except Http404:
            return Response({"error": "Cart item not found"}, status=status.HTTP_200_OK)

        # 🚀 Atomic DB-level decrement
        updated = Cart.objects.filter(pk=cart_item.pk, quantity__gt=0, telegram_user=telegram_user).update(
            quantity=F("quantity") - 1
        )

        if not updated:
            return Response({"message": "Item already zero"}, status=status.HTTP_200_OK)

        # 🔄 Reload only quantity column
        cart_item.refresh_from_db(fields=["quantity"])

        # 🧹 Delete if quantity reached zero
        if cart_item.quantity == 0:
            product_title = cart_item.product.title
            product_price = cart_item.product.price
            cart_item.delete()
            return Response({
                "product_name": product_title,
                "quantity": 0,
                "price": product_price,
                "total_price": 0,
                "message": "Item removed from cart",
            },
            status=status.HTTP_200_OK
        )

        return Response({
            "product_name": cart_item.product.title,
            "quantity": cart_item.quantity,
            "price": cart_item.product.price,
            "total_price": cart_item.multiply_price(),
            "message": "Quantity decreased",

        },
        status=status.HTTP_200_OK
    )
remove_cart_view = DecreaseCartAPIView.as_view()

class CartListApiView(ListAPIView):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [AllowAny]
    pagination_class = None   # ✅ disables pagination for this view


    def get_queryset(self, *args, **kwargs):
        telegram_id = self.kwargs.get('telegram_id')
        
        try:
            telegram_id = int(telegram_id)
        except (TypeError, ValueError):
            raise Http404("Invalid telegram_id")

        telegram_user, created = TelegramUser.objects.get_or_create(
            telegram_id=telegram_id
        )
        cart_data = (
            Cart.objects
            .select_related('product')
            .filter(telegram_user=telegram_user)
            .only(
                'product__id', 
                'quantity', 
                'product__title', 
                'product__price', 
                'product__image'
            )
            .annotate(total_price=F('quantity') * F('product__price'))
        )
        print("cart_data in get_queryset: ", cart_data)
        return cart_data     
cart_list_api_view = CartListApiView.as_view()


import hashlib
import hmac
from urllib.parse import unquote
from django.conf import settings

BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN

def verify_telegram_init_data(init_data: str):
    """
    Verifies Telegram Web App init_data according to Telegram docs.
    Returns (is_valid, data_dict).
    """
    parsed_data = {}
    
    # Step 1: Parse key=value pairs
    for item in init_data.split("&"):
        key, value = item.split("=", 1)
        parsed_data[key] = value

    # Step 2: Extract Telegram's hash
    received_hash = parsed_data.pop("hash", None)
    if not received_hash:
        return False, {}

    # Step 3: Build the data_check_string with URL-decoded values
    data_check_string = "\n".join(
        f"{key}={unquote(value)}" for key, value in sorted(parsed_data.items())
    )

    # Step 4: First HMAC (key=WebAppData, message=BOT_TOKEN)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=BOT_TOKEN.encode(),
        digestmod=hashlib.sha256
    ).digest()

    # Step 5: Second HMAC (key=secret_key, message=data_check_string)
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    print("Received hash:", received_hash)
    print("Calculated hash:", calculated_hash)
    print("Data check string:", repr(data_check_string))
    print("Secret key (hex):", secret_key.hex())

    # Step 6: Return validation result
    return calculated_hash == received_hash, {
        key: unquote(value) for key, value in parsed_data.items()
    }


class OrderBatchListCreateAPIView(APIView):
    throttle_scope = "send_kitchen"            # Tells DRF which limit to use
    throttle_classes = [TelegramScopedThrottle]  # Use our custom Telegram ID throttle

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        Idempotent order creation.
        Same idempotency_key = same order forever.
        
        Create a new order batch along with OrderBatchItems.
        Uses transaction.atomic to ensure all-or-nothing behavior.
        """
        print("request data: ", request.data)

        try:
            restaurant_id = self.kwargs.get("restaurant_id")
            cart_items = request.data.get('cart_items')
            idempotency_key = str(request.data.get('idempotency_key'))
            init_data = request.data.get("init_data")

        except (TypeError, ValueError):
            return Response({"error": "Invalid cart_items ID or telegram_id or idempotency_key"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not cart_items: return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)
        if not idempotency_key: return Response({"error": "Missing idempotency key"}, status=status.HTTP_400_BAD_REQUEST)
        if not restaurant_id: return Response({"error": "Missing restaurant ID"}, status=status.HTTP_400_BAD_REQUEST)
        if not init_data: return Response({"error": "data"}, status=status.HTTP_400_BAD_REQUEST)
        print("cart_items: ", request.data)

        is_valid, data = verify_telegram_init_data(init_data)

        print("data : ", data)
        print("is valid : ", is_valid)

        if not is_valid:
            return Response({"error": "Invalid Telegram data"}, status=403)

        user_data = json.loads(data["user"])

        telegram_id = user_data["id"]
        print("tel_id: ", telegram_id)

        try: restaurant = Restaurant.objects.get(rid=restaurant_id)
        except Restaurant.DoesNotExist: return Response({"error": "Restaurant not found"}, status=status.HTTP_400_BAD_REQUEST)
        
        # 2️⃣ Get telegram User
        try: telegram_user = TelegramUser.objects.get(telegram_id=telegram_id, restaurant=restaurant)
        except TelegramUser.DoesNotExist: return Response({"error": "User not found"}, status=status.HTTP_400_BAD_REQUEST)

        # 🔒 Lock existing order if already created
        existing_batch = (
            OrderBatch.objects
            .filter(telegram_user=telegram_user, idempotency_key=idempotency_key, restaurant=restaurant)
            .first()
        )

        if existing_batch:
            serializer = OrderBatchSerializer(existing_batch)
            existing_data = {
                "success": "order batch created successfully",
                "data": serializer.data
            }
            return Response(existing_data, status=status.HTTP_201_CREATED)

        product_pids = [item.get("pid") for item in cart_items]
        print("product_pids: ", product_pids)

        print("joshua.....")
        
        # 1️⃣ Auto-remove out-of-stock items from cart DB
        invalid_items = (
            Product.objects
            .filter(in_stock=False, pid__in=product_pids, restaurant=restaurant)
            .only('pid', 'title')
        ) # Fetch only product title for removed items log

        removed_cart_items = list(invalid_items.values_list('title', flat=True))
        pids = list(invalid_items.values_list('pid', flat=True))

        print("Echendu........")

        if invalid_items:
            print("Anuoluwapo.........")
            invalid_response = {
                "success": False,
                "out_of_stock": True,
                "message": "Some items were out of stock and removed from your cart",
                "removed_items": removed_cart_items,
                'product_ids': pids
            }
            return Response(invalid_response, status=status.HTTP_200_OK)
        
        try:

            # It tells the database: “Lock these rows while I’m working with them.”
            products = (
                Product.objects
                .filter(pid__in=product_pids, in_stock=True, restaurant=restaurant)
                # .select_related('category', 'restaurant')
            )
            
            # {5: <Product object 5>, 8: <Product object 8>, 12: <Product object 12>}
            product_map = { p.pid: p for p in products}
            print("product_map: ", product_map)

            if not product_map:
                return Response({
                    "success": False,
                    "out_of_stock": True,
                    "message": "All selected products are unavailable",
                    "product_ids": product_pids,
                }, status=status.HTTP_200_OK)
            
            # 3️⃣ Rebuild cart_items safely from DB truth
            safe_items = [ item for item in cart_items if item.get('pid') in product_map ]
            print("safe_items: ", safe_items)

            # 4️⃣ Calculate total price from DB prices
            total_price = Decimal('0.00')
            for item in safe_items:
                product = product_map.get(item.get('pid'))
                qty = int(item.get("quantity", 1))
                price = product.price
                total_price += price * qty

            session = (
                CheckoutSession.objects.filter(
                    restaurant=restaurant,
                    telegram_user=telegram_user,
                    is_active=True
                )
                .order_by('-date_created')
                .first()
            )

            if not session:
                CheckoutSession.objects.create(
                    restaurant=restaurant,
                    telegram_user=telegram_user,
                    is_active=True,
                    merchant_reference=None,
                    # expires_at=timezone.now() + timedelta(hours=3)  # expires in 3 hours

                )

            # CheckoutSession (ses8F21)
                # ├── OrderBatch A91X2
                # ├── OrderBatch B72JK
                # └── OrderBatch K91PQ
            # 5️⃣ 🔥 Idempotent create
            order_batch = OrderBatch.objects.create(
                checkout_session=session,
                restaurant=restaurant,
                removed_cart_items=removed_cart_items,
                idempotency_key=idempotency_key,
                telegram_user=telegram_user,
                total_price=total_price,
                status='pending', # kitchen status
                payment_status='unpaid'  # payment workflow
            )

            # 6️⃣ Create OrderBatchItems
            batch_items = [
                OrderBatchItem(
                    batch=order_batch,
                    product=product_map.get(item.get('pid')),
                    quantity=int(item.get("quantity", 1)),
                    price=product_map[item.get("pid")].price  # price per item
                )
                for item in safe_items
            ]
            OrderBatchItem.objects.bulk_create(batch_items)

            # .delay() → Redis (stored) → Celery worker → runs function
            send_order_notifications.delay(restaurant.rid, order_batch.bid, order_batch.telegram_user.telegram_id)

            serializer = OrderBatchSerializer(order_batch)
            
            data = {
                "success": True,
                "message": "Order batch created successfully", 
                "batch_id": order_batch.bid,
                "removed_items": removed_cart_items,
                "order_batch": serializer.data,
                "safe_cart_items": safe_items
            }
            return Response(data, status=status.HTTP_201_CREATED)
        
        except IntegrityError as e:
            # Race condition: someone else already created it
            batch = OrderBatch.objects.get(telegram_user=telegram_user, idempotency_key=idempotency_key, restaurant=restaurant)
            serializer = OrderBatchSerializer(batch)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Unexpected error creating order batch for user {telegram_user.id}: {e}")
            return Response(
                {"detail": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
# session = CheckoutSession.objects.get(session_id=session_id)
# session.is_active = False
# session.payment_confirmed = True
# session.save()

# # Update all OrderBatches under this session
# OrderBatch.objects.filter(checkout_session=session).update(payment_status='paid')




# 4️⃣ Optional Cleanup Task

# You can also create a periodic Celery task to automatically close expired sessions:

# from django.utils import timezone

# expired_sessions = CheckoutSession.objects.filter(
#     is_closed=False,
#     expires_at__lte=timezone.now()
# )
# expired_sessions.update(is_closed=True)

# This is optional but keeps your DB clean.

# Prevents old abandoned sessions from piling up.
orderbatch_list_create_view =  OrderBatchListCreateAPIView.as_view()



class DynamicVirtualAccountAPIView(APIView):

    """
    Create a Dynamic Virtual Account for a user checkout session
    """
    # throttle_scope = "squad_dva"

    def post(self, request, *args, **kwargs):
        print("kwargs: ", kwargs)
        print("request.data: ", request.data)

        try:
            telegram_id = int(request.data.get("user_id"))
            restaurant_id = str(request.data.get("restaurant_id"))
        except (TypeError, ValueError):
            return Response({"error": "telegram_id or idempotency_key"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not telegram_id and not restaurant_id:
            return Response({"message": "telegram_id or restuarant_id is missing......"}, status=status.HTTP_400_BAD_REQUEST)
        
        restaurant = get_object_or_404(Restaurant, rid=restaurant_id)
        print("resturant....: ", restaurant)
        try: telegram_user = TelegramUser.objects.get(telegram_id=telegram_id, restaurant=restaurant)
        except TelegramUser.DoesNotExist: return Response({"error": "User not found"}, status=status.HTTP_400_BAD_REQUEST)

        key = f"{uuid.uuid4().hex}"

        session = (
            CheckoutSession.objects
            .filter(
                restaurant=restaurant,
                telegram_user=telegram_user,
                is_active=True
            )
            .order_by('-date_created')  # <--- Added .order_by here
            .first()
        )

        if not session:
            return Response({
                "success": False,
                "error": "Session not found",
                "message": "You havent ordered an item, order some items",
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the VA is still valid (not expired)
        if session.va_expiry and session.va_expiry > timezone.now():
            print("time...zone")
            # VA is still valid → reuse it
            return Response({
                "success": True,
                "data": {
                    "account_number": session.va_acct_number,
                    "bank": session.va_bank,
                    "merchant_reference": session.merchant_reference,
                },
                "message": "You already have a valid VA assigned for this session."
            })

        orders = OrderBatch.objects.filter(
            telegram_user=telegram_user,
            restaurant=restaurant,
            checkout_session=session
        )

        vat = int(100)
        price_data = int(orders.aggregate(total_price=Sum('total_price'))['total_price'] or 0) + vat
        total_price = int(price_data * 100)        
        print("total_price: ", total_price)

        merchant_reference = f"REF-{key}-{telegram_id}"

        result = initiate_dynamic_virtual_account(amount=total_price, merchant_reference=merchant_reference, duration=60, email='echendujosh@gmail.com')
        print("result....: ", result)

        if result['success']:
            result = result.get('data')
            
            # parse Squad's expires_at string into datetime
            expires_at = parser.isoparse(result['expires_at'])  # parser.isoparse(result['expires_at']) converts that string into a Python datetime object.

            expected_amount = int(Decimal(result['expected_amount']))
            session.expected_amount = expected_amount
            session.merchant_reference = result['transaction_reference']
            session.va_acct_number = result['account_number']
            session.va_bank = result['bank']
            session.va_expiry = expires_at
            session.save() 

            requery_transaction.apply_async(countdown=1)
            requery_transaction.apply_async(countdown=60)
            requery_transaction.apply_async(countdown=120)
            requery_transaction.apply_async(countdown=240)
            requery_transaction.apply_async(countdown=300)
        
            return Response(
                {
                    "success": True,
                    "data": result,
                    "messages": "successfully created a VA number"
                }
            )
        return Response(
            {
                "success": False,
                "data": result,
                "messages": "Failed to create a VA number"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

dynamic_virtual_account_view = DynamicVirtualAccountAPIView.as_view()   


# Handle each case

# SUCCESS → The payment was successful.

# Mark the order as paid in your DB.

# Generate a receipt automatically and send it to the user. ✅

# MISMATCH → User sent the wrong amount.

# Notify the user: funds are being reversed.

# Optionally, generate a new VA for them to retry payment. ⚠️

# EXPIRED → User didn’t pay in time.

# Notify the user: VA expired and funds (if any) are refunded.

# Optionally, create a new VA so they can retry. ⏰


class SimulatepaymentAPIView(APIView):

    pagination_class = None

    def post(self, request, *args, **kwargs):
        print("DEBUG Response:", Response)

        va_acct_number = str(request.data.get('account_number'))
        amount = str(request.data.get("amount"))

        PAYMENT_ENDPOINT = "https://sandbox-api-d.squadco.com/virtual-account/simulate/payment"
        API_SECRET_KEY = "sandbox_sk_1446c0d02f3e20570f47a6c9297a3c149fc635c5946a"

        payload = {
            "virtual_account_number": va_acct_number,
            "amount": amount,
            "dva": True
        }
        print("payload: ", payload)

        headers = {
            "Authorization": f"Bearer {API_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    PAYMENT_ENDPOINT,
                    headers=headers,
                    json=payload,
                    timeout=10
                )
                
                response.raise_for_status()

                data = response.json()
                print("data...: ", data)

                if data.get("success"):
                    return Response({
                        "success": True,
                        "data": data["data"]
                    },
                    status=status.HTTP_200_OK
                    )
                else:
                    return Response({
                        "success": False,
                        "error": data.get("message", "Unknown error")
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            except requests.exceptions.HTTPError as http_err:

                # retry only on server errors
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    print(f"Server error, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                return Response({
                    "success": False,
                    "error": f"HTTP error: {http_err}",
                    "response": response.text
                },
                status=status.HTTP_400_BAD_REQUEST
            )

            except requests.exceptions.RequestException as req_err:

                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    print(f"Request failed, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                return Response({
                    "success": False,
                    "error": f"Request error after retries: {req_err}"
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

            except Exception as e:

                return Response({
                    "success": False,
                    "error": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            "success": False,
            "error": "Max retries exceeded"
        }, 
        status=status.HTTP_400_BAD_REQUEST
        )

simulate_payment_api_view = SimulatepaymentAPIView.as_view()


# ip = request.META.get("REMOTE_ADDR")
# print("WEBHOOK RECEIVED IP:", ip)

# class SquadWebhookAPIView(APIView):

#     authentication_classes = []
#     permission_classes = []

#     @transaction.atomic
#     def post(self, request):

#         payload = request.data
#         logger.info("Squad webhook received %s", payload)
        
#         # Extract the encrypted body
#         signature = request.headers.get("x-squad-encrypted-body")

#         # if no signature return
#         if not signature:
#             return Response({"error": "Missing signature"}, status=400)

#         # verify/validate squad signature
#         is_valid = verify_squad_signature(payload, signature)

#         # if signature is not valid
#         if not is_valid:
#             logger.warning("Invalid webhook signature: %s", payload)
#             return Response({"error": "Invalid signature"}, status=403)
        
#         required_fields = [
#             "merchant_reference",
#             "amount_received",
#             "transaction_status",
#             "date",
#         ]

#         for field in required_fields:
#             if field not in payload:
#                 logger.warning("Missing field %s in webhook", field)
#                 return Response({"error": f"Missing {field}"}, status=400)
        
#         # convert transaction status to lowercase
#         status = payload.get("transaction_status", "").lower()

#         # if status is mismatch
#         if status == "mismatch":
#             logger.info("Payment mismatch for %s", payload.get("merchant_reference"))
#             return Response({"message": "mismatch"}, status=200)
        
#         # if status is expired
#         if status == "expired":
#             logger.info("Payment exipred for %s", payload.get("merchant_reference"))
#             return Response({"message": "expired"}, status=200)

#         merchant_ref = payload.get("merchant_reference")

#         try:
#             session = CheckoutSession.objects.select_for_update().get(
#                 merchant_reference=merchant_ref,
#             )
#         except CheckoutSession.DoesNotExist:
#             return Response({"message": "session not found"}, status=200)

#         amount_received = int(Decimal(payload.get("amount_received")))

#         if amount_received != session.expected_amount:
#             print("amount_received: ", amount_received)
#             print("expected_amount: ", session.expected_amount)
#             logger.warning("Amount mismatch: %s vs %s", amount_received, session.expected_amount)

#             return Response({"message": "amount mismatch"}, status=200)

#         # prevent duplicate processing
#         if session.payment_status == "paid":
#             print("already paid")
#             logger.info("Amount already processed %s and %s ", session.payment_status, session.amount_received)
#             return Response({"message": "already processed"}, status=200)

#         paid_date = parser.isoparse(payload.get("date"))

#         session.payment_status = "paid"
#         session.amount_received = amount_received
#         session.paid_at = paid_date
#         session.is_active = False
#         session.webhook_payload = payload
#         session.save()
        
#         return Response({"message": "payment recorded"}, status=200)

# squad_webhook_api_view = SquadWebhookAPIView.as_view()


class SquadWebhookAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request):

        payload = request.data
        logger.info("Squad webhook received %s", payload)
        
        # Extract the encrypted body
        signature = request.headers.get("x-squad-encrypted-body")

        # if no signature return
        if not signature:
            return Response({"error": "Missing signature"}, status=400)

        # verify/validate squad signature
        is_valid = verify_squad_signature(payload, signature)

        # if signature is not valid
        if not is_valid:
            logger.warning("Invalid webhook signature: %s", payload)
            return Response({"error": "Invalid signature"}, status=403)
        
        logger.info("signature verification is valid......")
        required_fields = [
            "merchant_reference",
            "amount_received",
            "transaction_status",
            "date",
        ]

        for field in required_fields:
            if field not in payload:
                logger.warning("Missing field %s in webhook", field)
                return Response({"error": f"Missing {field}"}, status=400)
        
        # send to celery
        process_squad_webhook.delay(payload)
        return Response({"message": "Webhook received"}, status=status.HTTP_200_OK)

squad_webhook_api_view = SquadWebhookAPIView.as_view()



class UpdateBatchStatusAPIView(APIView):
    permission_classes = [AllowAny]

    def patch(self, request, *args, **kwargs):
        batch_id = str(request.data.get("batch_id", ""))
        new_status = str(request.data.get("status", ""))
        rid = str(request.data.get("restaurant_id", ""))
        print("rid baby: ", rid)
        print("batch_id baby: ", batch_id)

        # ✅ Basic validation
        if not batch_id or not new_status or not rid:
            return Response({"error": "restaurant_id, batch_id and status are required"}, status=status.HTTP_400_BAD_REQUEST)

        if new_status not in dict(KITCHEN_STATUS_CHOICES):
            return Response({"error": "Invalid status value"}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Lock the row to avoid race conditions
        with transaction.atomic():
            try:
                order = OrderBatch.objects.get(bid=batch_id, restaurant__rid=rid)
            except OrderBatch.DoesNotExist:
                return Response({"error": "Batch not found"}, status=status.HTTP_404_NOT_FOUND)
            
            print("order baby: ", order)
            
            # 🔹 Handle network retry / repeated clicks safely first
            if new_status == "processing" and order.status == "processing":
                return Response({
                    "batch_id": order.bid,
                    "status": order.status,
                    "message": f"Duplicate processing update ignored for {order.bid}"
                }, status=status.HTTP_200_OK)

            # 🔹 Handle duplicate Celery sends next
            if new_status == "processing" and order.status != "pending":
                # Log duplicate click for audit
                logger.warning(f"Duplicate processing attempt for batch {batch_id} (current status: {order.status})")

                # Optional: store last click in Redis
                redis_client.set(f"batch:{batch_id}:duplicate_click", 1, ex=60)  # expires in 60 sec

                # Return 409 Conflict instead of 400
                return Response(
                    {"error": f"Cannot move from {order.status} to {new_status}"},
                    status=status.HTTP_409_CONFLICT
                )

            # ✅ Safe status update
            order.status = new_status
            order.save(update_fields=["status"])

        logger.info(f"Batch {batch_id} updated successfully to {new_status}")

        return Response({
            "batch_id": order.bid,
            "status": order.status,
            "message": f"Order status updated to {new_status}"
        })

update_batch_status_api_view = UpdateBatchStatusAPIView.as_view()

class UserOrderBatchesAPIView(APIView):
    def get(self, request, *args, **kwargs):
        telegram_id = kwargs.get('telegram_id')
        restaurant_id = kwargs.get('restaurant_id')

        if telegram_id is None:
            return Response({"error": "Missing telegram_id in path"}, status=400)
        if restaurant_id is None:
            return Response({"error": "Missing restaurant_id in path"}, status=400)

        try:
            telegram_id = int(telegram_id)
            rid = str(restaurant_id)
        except (TypeError, ValueError):
            return Response({"error": "Invalid telegram_id"}, status=400)

        try:
            restaurant = Restaurant.objects.get(rid=rid)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant not found"}, status=404)

        user = TelegramUser.objects.filter(telegram_id=telegram_id, restaurant=restaurant).first()
        if not user:
            return Response({"error": "User for this restaurant not found"}, status=404)

        # session_batches → all OrderBatch
        # items → all OrderItem
        # product → all Product
        session = (
            CheckoutSession.objects
            .select_related("restaurant")
            .filter(telegram_user=user, restaurant=restaurant, is_active=True)
            # 1️⃣ session_batches: Load all OrderBatch objects connected to the session. 2️⃣ items: Inside each batch, load its OrderItems.
            # 3️⃣ product For each item, load the Product details.
            .prefetch_related(
                "session_batches__items__product" # “Load the session, its batches, the items in those batches, and the products for those items in advance so the database isn’t queried repeatedly.”
            )
            .order_by('-date_created')            
            .first()
        )

        if not session:
            return Response({
                "error": "Session not found",
                "message": "You have no active session, please order some items."
            }, status=404)

        data = []
        for order in session.session_batches.all():
            items = [
                {
                    "quantity": item.quantity,
                    "price": int(item.price),
                    "product_title": item.product.title
                }
                for item in order.items.all()
            ]
            data.append({
                "bid": order.bid,
                "total_price": order.total_price,
                "items": items,
                "restaurant": session.restaurant.name
            })

        return Response(data)
    
batch_list_api_view = UserOrderBatchesAPIView.as_view()


# Break it into layers:

# Layer 1: Your restaurant ordering + batching system (already done).

# Layer 2: Payment collection via DVAs (Squad/GTCO integration).

# Layer 3: Settlement to restaurants (your ledger + payouts).

# Test each layer in isolation

# Use sandbox for DVAs → simulate payments → check webhooks.

# Once that works, only then connect to your live merchant account.

# Think like a ledger

# All incoming money = tracked per order.

# Settlement = calculated from ledger → transfer.

# That way, you always know who’s owed what.


# How disbursement to restaurants works

# Since the restaurants are using your bot as a service, your bot controls the backend tracking of orders and payments.

# You can implement your own payout logic, for example:

# At the end of the day / week / month, calculate how much money each restaurant is owed based on their orders.

# Initiate transfers from your GTB merchant account to each restaurant’s individual account (could be GTB or any other bank).

# Optionally, keep a ledger or “settlement table” in your database for transparency, showing:

# | Restaurant | Amount Received | Amount Paid | Pending Balance |
# | ---------- | --------------- | ----------- | --------------- |
# | A          | 50,000          | 50,000      | 0               |
# | B          | 35,000          | 35,000      | 0               |
