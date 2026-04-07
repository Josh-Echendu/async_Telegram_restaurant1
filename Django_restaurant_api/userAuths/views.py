from django.shortcuts import render, redirect
from .serializers import TelegramUserSerializer
from .models import TelegramUser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.db import transaction, IntegrityError
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from restaurants.models import Restaurant, RestaurantMembership


# Create your views here.
class TelegramUserCreateAPIView(APIView):
    """
    Production-grade endpoint:
    - Idempotent
    - Concurrency-safe
    - Zero duplicate records
    - Handles race conditions automatically
    """
    """
    Indempodent: An operation is idempotent if: You can run it once or many times, and the result is always the same.
        First request → creates user ✅
        Second request → updates same user ✅
        Third request → still same user ✅

        No duplicates. No errors. Same final state.
    """

    @transaction.atomic
    def post(self, request):
        data = request.data

        try:
            restaurant = Restaurant.objects.get(rid=data.get('restaurant_id'))
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with id {data.get('restaurant_id')} not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        telegram_id = data.get("telegram_id")
        defaults = {
            "first_name": data.get("first_name", ""),
            "username": data.get("username", ""),
        }

        try:
            # Look for user with this telegram_id
            # If found → update it
            # If not found → create it
            user, created = TelegramUser.objects.update_or_create(
                telegram_id=telegram_id,
                defaults=defaults,
            )

            # 2️⃣ Link USER ↔ RESTAURANT
            RestaurantMembership.objects.get_or_create(
                user=user,
                restaurant=restaurant
            )
            
            return Response(
                {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "created": created,
                    "restaurant": restaurant.name
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except IntegrityError:
            # Another request created it at the same time → fetch the existing one
            user = TelegramUser.objects.get(telegram_id=telegram_id)
            
            return Response(
                {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "created": False,
                    "restaurant": restaurant.name
                },
                status=status.HTTP_200_OK,
            )

telegram_user_create_api_view = TelegramUserCreateAPIView.as_view()


class TelegramUserListAPIView(ListAPIView):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer
    permission_classes = [AllowAny]

    def get_queryset(self, *args, **kwargs):
        return TelegramUser.objects.all()
    
    # DRF will take the queryset returned by get_queryset(), pass it to the serializer, and then automatically generate the Response in the list() method.
    def list(self, request, *args, **kwargs): # Override list() to ensure JSON + 200 status
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

telegram_list_api_view = TelegramUserListAPIView.as_view()


def admin_login_view(request, restaurant_id):

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is not None and user.is_staff:
            login(request, user)

            # ✅ STORE IN SESSION
            request.session["restaurant_id"] = restaurant_id

            return redirect("useradmin:dashboard")

        else:
            messages.error(request, "Invalid login credentials.")
            return redirect("userauths:admin_login", restaurant_id=restaurant_id)

    return render(request, "userauths/admin_login.html", {"restaurant_id": restaurant_id})


def admin_logout_view(request):
    restaurant_id = request.session.get('restaurant_id')
    if not restaurant_id:
        return redirect("userauths:admin_login", restaurant_id='')

    request.session.pop("restaurant_id", None)
    logout(request)
    return redirect("userauths:admin_login", restaurant_id=restaurant_id)

# what do you mean here: Optional Enhancements

# Make the link unique per user session → avoids conflicts if multiple users are ordering at the same time.

# Send a dynamic receipt PDF via WhatsApp after checkout.

# Use shortened links or QR codes in the restaurant to reduce typing friction.

# Track click-through → order conversion for analytics.