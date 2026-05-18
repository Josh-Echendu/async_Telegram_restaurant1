from calendar import weekday

from .throttles import TelegramWhatsappScopedThrottle
from .models import Restaurant, DineInOTPSession, RestaurantDeliveryOpeningHours, RestaurantMembership
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from orders.models import Category
from rest_framework import status
from django.shortcuts import get_object_or_404
import logging
from userAuths.models import TelegramUser
from django.db import IntegrityError, transaction, OperationalError
from rest_framework.views import APIView
from django.db.models import Q


logger = logging.getLogger(__name__)


@api_view(["GET"])
def get_restaurant_internal(request, platform, rid=None):

    # 🔐 INTERNAL SECURITY
    api_key = request.headers.get("X-INTERNAL-API-KEY")
    if api_key != settings.INTERNAL_API_KEY:
        return Response({"error": "unauthorized"}, status=403)
    
    phone_id = request.headers.get("X-PHONE-ID")        
    
    if not platform:
        return Response({"error": "Wrong data"}, status=404)
    
    platform = platform.lower()

    if platform == 'telegram':
        restaurant = Restaurant.objects.filter(rid=rid).first()
    elif platform == 'whatsapp':
        restaurant = Restaurant.objects.filter(whatsapp_phone_number_id=phone_id).first()

    # ✅ CHECK FIRST BEFORE ACCESSING
    if not restaurant:
        return Response({}, status=404)
    
    print('restaurant data: ', restaurant.rid)
    print('restaurant name: ', restaurant.name)
    print('restaurant username: ', restaurant.bot_username)
    print('restaurant data access token for whatsapp: ', restaurant.whatsapp_access_token)

    if not restaurant:
        return Response({}, status=404)
        
    # 👉 This returns an integer from 0 to 6
    day_of_week = timezone.now().weekday()  # Get current day of week (0=Monday, 6=Sunday)
    
    delivery_opening_hours = restaurant.delivery_opening_hours.filter(
        day_of_week=day_of_week
    ).first()

    open_time = delivery_opening_hours.open_time if delivery_opening_hours else None
    close_time = delivery_opening_hours.close_time if delivery_opening_hours else None


    return Response({

        # Telegram specific fields
        "rid": restaurant.rid,
        "bot_token": restaurant.get_bot_token(),  # ✅ REQUIRED
        "bot_name": restaurant.name,
        "webhook_secret_token": str(restaurant.webhook_secret_token),
        "is_bot_active": restaurant.is_bot_active,
        "is_accepting_orders": restaurant.is_accepting_orders,
        
        # General Fields
        "service_mode": restaurant.service_mode,
        "business_type": restaurant.business_type,
        "max_tables": restaurant.max_tables,
        "open_time": open_time,
        "close_time": close_time,
        "time_zone": restaurant.timezone,
        "is_closed": delivery_opening_hours.is_closed if delivery_opening_hours else None,

        # WhatsApp Specifics
        "wa_token": restaurant.whatsapp_access_token, # Your EncryptedField
        "wa_phone_id": restaurant.whatsapp_phone_number_id,
        "wa_waba_id": restaurant.whatsapp_business_account_id,
        "is_wa_active": restaurant.is_whatsapp_active,
    })


# 📅 Mapping (VERY IMPORTANT)

# timezone.now().weekday() returns:
# | Value | Day       |
# | ----- | --------- |
# | 0     | Monday    |
# | 1     | Tuesday   |
# | 2     | Wednesday |
# | 3     | Thursday  |
# | 4     | Friday    |
# | 5     | Saturday  |
# | 6     | Sunday    |



class GenerateOTPForTableAPIView(APIView):
    """
    Step 2: Waiter generates OTP for a table
    POST /api/dine-in/generate-otp/
    Called by PTB when waiter types /gencode 5
    """

    def post(self, request):
        waiter_telegram_id = request.data.get('waiter_telegram_id')
        restaurant_id = request.data.get('restaurant_id')
        table_number = request.data.get('table_number')
        waiter_username = request.data.get('waiter_username')

        if not all([waiter_username, waiter_telegram_id, restaurant_id, table_number]):
            return Response({
                "error": "Missing required fields"
            }, status=status.HTTP_400_BAD_REQUEST
        )
        
        restaurant = get_object_or_404(Restaurant, rid=restaurant_id)

        session = DineInOTPSession.create_session(
            restaurant=restaurant,
            table_number=table_number,
            waiter_telegram_id=waiter_telegram_id,
            waiter_username=waiter_username,
        )

        # Generate OTP()
        otp = session.generate_otp()

        logger.info(f"OTP generated for Table {table_number} by waiter {waiter_telegram_id}")

        return Response({
            "success": True,
            "session_id": session.session_id,
            "otp_code": otp,
            "expires_in": 300,  # 5 minutes in seconds
            "waiter_usernamr": session.waiter_username or "waiter",  # For PTB to send message
            "message": f"OTP {otp} generated for Table {table_number}"
        }, status=201)

class VerifyOTPAPIView(APIView):
    """
    Step 3: Customer verifies OTP
    POST /api/dine-in/verify-otp/
    """

    throttle_classes = [TelegramWhatsappScopedThrottle]
    throttle_scope = "kitchen_otp"

    def post(self, request):

        print("request otp: ", request)
        telegram_id = request.data.get('telegram_id')
        whatsapp_id = request.data.get('whatsapp_id')
        restaurant_id = request.data.get('restaurant_id')
        otp_code = request.data.get('otp_code')
        platform = request.data.get('platform')

        if not all([(telegram_id or whatsapp_id), restaurant_id, otp_code]):
            return Response({"error": "Missing required fields"}, status=400)

        print("user resolution")
        # ---------------- USER RESOLUTION ----------------
        if platform == "telegram":
            active_user = TelegramUser.objects.filter(telegram_id=telegram_id).first()
            print("telegram active user: ", active_user)
        elif platform == "whatsapp":
            active_user = TelegramUser.objects.filter(whatsapp_id=whatsapp_id).first()
            print("whatsapp active user: ", active_user)

        else:
            return Response({"error": "Invalid platform"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not active_user:
            return Response({"error": "User not registered"}, status=status.HTTP_404_NOT_FOUND)        

        # Check membership
        if not RestaurantMembership.objects.filter(
            user=active_user,
            restaurant__rid=restaurant_id
        ).exists():
            return Response({"error": "User not linked to this restaurant"}, status=status.HTTP_403_FORBIDDEN)
       
        print("i am a member.......")
        # ---------------- OTP VERIFICATION ----------------
        try:
            with transaction.atomic():

                session = (
                    DineInOTPSession.objects
                    .select_for_update()
                    .filter(
                        restaurant__rid=restaurant_id,
                        otp_code=otp_code,
                        status='pending',
                        otp_expires_at__gt=timezone.now()
                    )
                    .order_by('-created_at')
                    .first()
                )

                if not session:
                    return Response({"error": "Invalid or expired OTP"}, status=400)

                if session.status != "pending":
                    return Response({"error": "Session already used"}, status=400)

                # ---------------- VERIFY SESSION ----------------
                if session.user is not None:
                    return Response({"error": "This OTP has already being used"}, status=400)
                
                if session.waiter_telegram_id is None:
                    return Response({"error": "Invalid session"}, status=400)
                
                session.verify(active_user=active_user)  # uses your method (cleaner than manual update)

        except Exception:
            return Response({"error": "Server error"}, status=500)

        return Response({
            "success": True,
            "message": f"Verified! You are at Table {session.table_number}",
            "session_id": session.session_id,
            "table_number": session.table_number,
            "waiter_name": session.waiter_username or "waiter"
        })

verify_otp_api_view = VerifyOTPAPIView.as_view()


