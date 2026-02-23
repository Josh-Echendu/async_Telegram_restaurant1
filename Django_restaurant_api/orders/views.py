from decimal import Decimal
from django.shortcuts import render
from .redis_client import redis_client
from userAuths.models import TelegramUser
from rest_framework.generics import (
    CreateAPIView, ListAPIView, RetrieveAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
)
from rest_framework.response import Response
from .serializers import CartSerializer, CategorySerializer, OrderBatchSerializer, ProductSerializer
from .models import KITCHEN_STATUS_CHOICES, Cart, Category, OrderBatch, OrderBatchItem, Product
from rest_framework.permissions import IsAuthenticated , AllowAny
import json
import httpx
from rest_framework.pagination import LimitOffsetPagination 
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db.models import OuterRef, Subquery, Value, F
from django.db.models.functions import Coalesce
from django.http import Http404
from rest_framework import status
from django.db import transaction, IntegrityError
from .tasks import send_order_notifications
from .throttles import TelegramScopedThrottle  # import the custom throttle


import logging
logger = logging.getLogger(__name__)


# OuterRef → used inside a Subquery to refer to a field from the outer/main query.
# Subquery → lets you embed a query inside another query, basically “I want this small query’s result for each row of my main query.”

# Custom pagination for Telegram bot
class TelegramLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 3      # how many items per "page"
    max_limit = 3          # max items the bot can fetch at once

class CategoryProductsApiView(ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    pagination_class = TelegramLimitOffsetPagination

    def get_queryset(self, *args, **kwargs):
        cat = self.kwargs.get("cat")
        telegram_id = self.kwargs.get('telegram_id')
        print("cat:", cat)
        print("telegram:", telegram_id)

        telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
        print("type: ", type(telegram_user))

        cart_subquery = Cart.objects.filter(product=OuterRef('pk'), telegram_user=telegram_user).values('quantity')[:1]
        cart_subquery = Coalesce(Subquery(cart_subquery), Value(0))

        # 🚀 Ultra-fast DB query (indexed fields only)
        return (
            Product.objects
            .filter(category__title=cat, in_stock=True) # no iexact = faster
            .only("id", "title", "price", "image")  # fetch only needed fields
            .annotate(cart_quantity=(cart_subquery)) # Annotate each product with its cart quantity
        )
    
    def list(self, request, *args, **kwargs):
        """Override to add product_ids mapping in response"""

        # 🧩 NORMAL DRF FLOW
        response = super().list(request, *args, **kwargs) # This method controls what response is sent to the client.
        print("response data:", response.data)
        results = response.data['results'] # response.data['results'] contains serialized products
        
        # ⚡ O(n) dict build — unavoidable but tiny
        product_ids = { p['title'].lower(): p['id'] for p in results }
        
        # Include in response
        final_data = {
            "products": response.data['results'],
            "count": response.data['count'],
            "next": response.data['next'],
            "previous": response.data['previous'],
            "product_ids": product_ids
        }
        return Response(final_data, status=status.HTTP_200_OK)
    
category_product_api_view = CategoryProductsApiView.as_view()


class CategoryListApiView(ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self, *args, **kwargs):
        restaurant_id = self.kwargs.get("restaurant_id")
        print("restaurant_id: ", restaurant_id)
        return Category.objects.select_related('restaurant').filter(restaurant__rid=restaurant_id).only('cid', 'title', 'image')

category_list_api_view = CategoryListApiView.as_view() 

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

        try:
            cart_items = request.data.get('cart_items')
            idempotency_key = str(request.data.get('idempotency_key'))
            telegram_id = int(request.data.get('telegram_id'))

        except (TypeError, ValueError):
            return Response({"error": "Invalid cart_items ID or telegram_id or idempotency_key"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not cart_items: return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)
        if not idempotency_key: return Response({"error": "Missing idempotency key"}, status=status.HTTP_400_BAD_REQUEST)
        if not telegram_id: return Response({"error": "Missing Telegram key"}, status=status.HTTP_400_BAD_REQUEST)
        print("cart_items: ", cart_items)

        # 2️⃣ Get telegram User
        try: telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
        except TelegramUser.DoesNotExist: return Response({"error": "User not found"}, status=404)
        
        # 🔒 Lock existing order if already created
        existing_batch = (
            OrderBatch.objects
            .select_for_update()
            .filter(telegram_user=telegram_user, idempotency_key=idempotency_key)
            .first()
        )

        if existing_batch:
            serializer = OrderBatchSerializer(existing_batch)
            return Response(serializer.data, status=status.HTTP_200_OK)

        product_ids = [item.get("product_id") for item in cart_items]
        print("product_ids: ", product_ids)
        
        # 1️⃣ Auto-remove out-of-stock items from cart DB
        invalid_items = Cart.objects.select_related('product').filter(
            telegram_user=telegram_user,
            product__in_stock=False,
            product_id__in=product_ids
        ).only('product__title') # Fetch only product title for removed items log

        removed_cart_items = list(
            invalid_items.values_list('product__title', flat=True)
        )
        invalid_items.delete()  # Remove invalid items from cart
        
        try:

            # It tells the database: “Lock these rows while I’m working with them.”
            products = (
                Product.objects
                .select_for_update()
                .filter(id__in=product_ids, in_stock=True)
                .only('id', 'title', 'price') # Fetch only needed fields
            )
            
            # {5: <Product object 5>, 8: <Product object 8>, 12: <Product object 12>}
            product_map = { p.id: p for p in products}
            print("product_map: ", product_map)

            if not product_map:
                return Response(
                    {"error": "All selected products are unavailable"},
                    status=status.HTTP_400_BAD_REQUEST
                ) 
            
            # 3️⃣ Rebuild cart_items safely from DB truth
            safe_items = [ item for item in cart_items if item.get('product_id') in product_map ]
            print("safe_items: ", safe_items)

            # 4️⃣ Calculate total price from DB prices
            total_price = Decimal('0.00')
            for item in safe_items:
                product = product_map.get(item.get('product_id'))
                qty = int(item.get("quantity", 1))
                price = product.price
                total_price += price * qty

            # 5️⃣ 🔥 Idempotent create
            order_batch = OrderBatch.objects.create(
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
                    product=product_map.get(item.get('product_id')),
                    quantity=int(item.get("quantity", 1)),
                    price=product_map[item.get("product_id")].price  # price per item
                )
                for item in safe_items
            ]
            OrderBatchItem.objects.bulk_create(batch_items)

            # ✅ 7️⃣ CLEAR CART (atomic, safe)
            Cart.objects.filter(telegram_user=telegram_user, product_id__in=product_map.keys()).delete()
            
            # .delay() → Redis (stored) → Celery worker → runs function
            send_order_notifications.delay(order_batch.bid, order_batch.telegram_user.telegram_id)

            serializer = OrderBatchSerializer(order_batch)
            
            data = {
                "message": "Order batch created successfully", 
                "batch_id": order_batch.bid,
                "removed_items": removed_cart_items,
                "order_batch": serializer.data,
                "safe_cart_items": safe_items
            }
            return Response(data, status=status.HTTP_201_CREATED)
        
        except IntegrityError as e:
            # Race condition: someone else already created it
            batch = OrderBatch.objects.get(telegram_user=telegram_user, idempotency_key=idempotency_key)
            serializer = OrderBatchSerializer(batch)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Unexpected error creating order batch for user {telegram_user.id}: {e}")
            return Response(
                {"detail": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

orderbatch_list_create_view =  OrderBatchListCreateAPIView.as_view()


class UpdateBatchStatusAPIView(APIView):
    permission_classes = [AllowAny]

    def patch(self, request, *args, **kwargs):
        batch_id = str(request.data.get("batch_id", ""))
        new_status = str(request.data.get("status", ""))

        # ✅ Basic validation
        if not batch_id or not new_status:
            return Response({"error": "batch_id and status are required"}, status=status.HTTP_400_BAD_REQUEST)

        if new_status not in dict(KITCHEN_STATUS_CHOICES):
            return Response({"error": "Invalid status value"}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Lock the row to avoid race conditions
        with transaction.atomic():
            try:
                order = OrderBatch.objects.select_for_update().get(bid=batch_id)
            except OrderBatch.DoesNotExist:
                return Response({"error": "Batch not found"}, status=status.HTTP_404_NOT_FOUND)

            # ✅ Prevent duplicate processing
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
        
        if telegram_id is None: return Response({"error": "Missing telegram_id in path"}, status=status.HTTP_400_BAD_REQUEST)

        try: telegram_id = int(telegram_id)
        except (TypeError, ValueError): return Response({"error": "Invalid telegram_id"}, status=status.HTTP_400_BAD_REQUEST)

        user = TelegramUser.objects.filter(telegram_id=telegram_id).first()
        if not user: return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        order_batches = (
            OrderBatch.objects
            .filter(telegram_user=user)
            .order_by('date_created')
            .prefetch_related("items__product")
            .only('bid', 'total_price')
        )

        data = []
        for order in order_batches:

            # append a dict to the list
            data.append({
                "bid": order.bid,
                "total_price": order.total_price,
                "items": list(order.items.values(
                    "quantity", 'price', 'product__title'
                ))
            })        
        return Response(data)

batch_list_api_view = UserOrderBatchesAPIView.as_view()
