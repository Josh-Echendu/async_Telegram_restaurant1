from django.shortcuts import get_object_or_404, render, redirect
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
from .models import AuthToken
from django.http import HttpResponse, JsonResponse
from django.conf import settings 
from django.shortcuts import redirect
from django.http import HttpResponse





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



class WhatsAppUserCreateAPIView(APIView):
    """
    WhatsApp version of user registration.
    Required fields: whatsapp_id, phone_number, first_name, restaurant_id
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

        whatsapp_id = data.get("whatsapp_id")
        phone_number = data.get("phone_number")
        
        # WhatsApp requires phone number
        if not phone_number:
            return Response(
                {"error": "phone_number is required for WhatsApp users"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        defaults = {
            "first_name": data.get("first_name", ""),
            "username": data.get("username", ""),
            "phone_number": phone_number,
        }

        try:
            user, created = TelegramUser.objects.update_or_create(
                whatsapp_id=whatsapp_id,
                defaults=defaults,
            )

            RestaurantMembership.objects.get_or_create(
                user=user,
                restaurant=restaurant
            )
            
            return Response(
                {
                    "id": user.id,
                    "whatsapp_id": user.whatsapp_id,
                    "phone_number": user.phone_number,
                    "username": user.username,
                    "created": created,
                    "restaurant": restaurant.name
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except IntegrityError:
            user = TelegramUser.objects.get(whatsapp_id=whatsapp_id)
            
            return Response(
                {
                    "id": user.id,
                    "whatsapp_id": user.whatsapp_id,
                    "phone_number": user.phone_number,
                    "username": user.username,
                    "created": False,
                    "restaurant": restaurant.name
                },
                status=status.HTTP_200_OK,
            )

whatsapp_user_create_api_view = WhatsAppUserCreateAPIView.as_view()


class CreateAuthTokenAPIView(APIView):

    def post(self, request):
        user_id = request.data.get("user_id")
        platform = request.data.get("platform")
        restaurant_id = request.data.get("restaurant_id")

        restaurant = get_object_or_404(Restaurant, rid=restaurant_id)

        token = AuthToken.generate(
            user_id=user_id,
            platform=platform,
            restaurant=restaurant,
            mode=request.data.get("mode"),
            table_number=request.data.get("table_number"),
        )

        url = f"{settings.NGROK_DJANGO}/whatsapp/callback/{restaurant_id}/?token={token.token}"
        
        return Response({
            "token": token.token,
            "url": url
        })
    
whatsapp_init_session_api_view = CreateAuthTokenAPIView.as_view()



def whatsapp_callback_view(request, restaurant_id):

    token = request.GET.get("token")

    # ✅ 1. reuse ONLY if same restaurant
    if (
        request.session.get("user_id") and
        request.session.get("restaurant_id") == restaurant_id
    ):
        return redirect(f"/menu/{restaurant_id}/")

    # ❌ require token otherwise
    if not token:
        return HttpResponse("Missing token", status=400)

    try:
        auth = AuthToken.objects.get(
            token=token,
            restaurant__rid=restaurant_id
        )
    except AuthToken.DoesNotExist:
        return HttpResponse("Invalid token", status=400)

    if not auth.is_valid():
        return HttpResponse("Token expired", status=400)

    # 🔥 2. RESET if different user or restaurant
    if (
        request.session.get("user_id") != auth.user_id or
        request.session.get("restaurant_id") != restaurant_id
    ):
        request.session.flush()

    # ✅ 3. CREATE NEW SESSION
    request.session["user_id"] = auth.user_id
    request.session["platform"] = auth.platform
    request.session["restaurant_id"] = restaurant_id
    request.session["mode"] = auth.mode
    request.session["table_number"] = auth.table_number

    auth.use()

    return redirect(f"/menu/{restaurant_id}/")


def whatsapp_login(request):
    restaurant_id = request.GET.get('restaurant_id')
    
    context = {
        'restaurant_id': restaurant_id,
        'message': 'Please scan the WhatsApp QR code to continue ordering.'
    }
    return render(request, 'restaurant/whatsapp_login.html', context)