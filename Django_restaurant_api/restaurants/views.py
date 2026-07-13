from calendar import weekday

from .throttles import TelegramWhatsappScopedThrottle
from .models import DineInSessionParticipant, Restaurant, DineInOTPSession, RestaurantDeliveryOpeningHours, RestaurantMembership
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
    page_id = request.headers.get("X-PAGE-ID")
    ig_business_id = request.headers.get("X-IG-BUSINESS-ID")

    if not platform:
        return Response({"error": "Wrong data"}, status=404)
    
    platform = platform.lower()

    if platform in ['telegram', 'whatsapp2']:
        restaurant = Restaurant.objects.filter(rid=rid).first()
    elif platform == 'whatsapp':
        restaurant = Restaurant.objects.filter(whatsapp_phone_number_id=phone_id).first()
    elif platform == "facebook":
        restaurant = Restaurant.objects.filter(facebook_page_id=page_id).first()
    else:
        return Response({"error": "platform not found"}, status=404)
    
    # elif platform == "instagram":
    #     restaurant = Restaurant.objects.filter(instagram_business_account_id=ig_business_id).first()

    # ✅ CHECK FIRST BEFORE ACCESSING
    if not restaurant:
        return Response({}, status=404)
    
    print('restaurant data: ', restaurant.rid)
    print('restaurant name: ', restaurant.name)

    if not restaurant:
        return Response({}, status=404)
        
    # 👉 This returns an integer from 0 to 6
    day_of_week = timezone.now().weekday()  # Get current day of week (0=Monday, 6=Sunday)
    
    delivery_opening_hours = restaurant.delivery_opening_hours.filter(
        day_of_week=day_of_week
    ).first()

    open_time = delivery_opening_hours.open_time if delivery_opening_hours else None
    close_time = delivery_opening_hours.close_time if delivery_opening_hours else None

    data = {

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
        "vendor_type": restaurant.vendor_type,
        "hotel_service_type": restaurant.hotel_service_type,
        "is_closed": delivery_opening_hours.is_closed if delivery_opening_hours else None,
        'kitchen_chat_id': restaurant.kitchen_chat_id,

        # WhatsApp Specifics
        "wa_token": restaurant.whatsapp_access_token, # Your EncryptedField
        "wa_phone_id": restaurant.whatsapp_phone_number_id,
        "wa_waba_id": restaurant.whatsapp_business_account_id,
        "is_wa_active": restaurant.is_whatsapp_active,

        # Facebook
        "fb_token": restaurant.facebook_page_access_token,
        "fb_page_id": restaurant.facebook_page_id,
        "is_fb_active": restaurant.is_facebook_active,

        # # Instagram
        # "ig_token": restaurant.instagram_access_token,
        # "ig_business_id": restaurant.instagram_business_account_id,
        # "ig_username": restaurant.instagram_username,
        # "is_ig_active": restaurant.is_instagram_active,
    }

    return Response({
        "data": data
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
            "expires_in": 60,  # 1 minutes in seconds
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

        print("request otp: ", request.data)
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
                    DineInOTPSession.objects.select_related('restaurant')
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

        # Send the table session link to the host user
        try:
            join_link = f"{settings.NGROK_DJANGO}/join/{session.session_token}/"

            message = (
                f"You're verified at Table {session.table_number}, {session.restaurant.name}.\n\n"
                f"Share this link with your friends so they can join:\n{join_link}"
            )
            if platform == "telegram":
                send_telegram_message(chat_id=telegram_id, session=session, message=message)
            elif platform == "whatsapp":
                send_whatsapp_message(recipient_id=whatsapp_id, session=session, message=message)
        except Exception:
            logger.warning(f"Failed to send join link for session {session.session_id}", exc_info=True)
            # don't fail the request — customer is still verified, just missed the link message

        return Response({
            "success": True,
            "message": f"Verified! You are at Table {session.table_number}",
            "session_id": session.session_id,
            "table_number": session.table_number,
            "waiter_name": session.waiter_username or "waiter"
        })

verify_otp_api_view = VerifyOTPAPIView.as_view()


import requests
from django.conf import settings


def send_telegram_message(chat_id, session, message):

    url = f"https://api.telegram.org/bot{session.restaurant.bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_whatsapp_message(recipient_id, session, message):

    url = f"https://graph.facebook.com/v19.0/{session.restaurant.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {session.restaurant.whatsapp_access_token}"}
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "text",
        "text": {
            "body": message
        }
    }
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()



from django.shortcuts import render


def join_landing_redirect(request, session_token):

    """
    GET /join/<session_token>/
    Renders a simple page with two buttons — no auth needed here, just routing.
    """

    session = get_object_or_404(DineInOTPSession, session_token=session_token, status='verified')

    context =  {
        'table_number': session.table_number,
        'restaurant_name': session.restaurant.name,
        'whatsapp_link': f"https://wa.me/{session.restaurant.whatsapp_business_phone}?text=join_{session_token}",
        'telegram_link': f"https://t.me/{session.restaurant.bot_username}?start=join_{session_token}",
    }

    return render(request, 'join_landing.html', context)





class RequestJoinTableAPIView(APIView):
    """
    POST /api/dine-in/request-join/
    Called when Sandra/Tunde/Emma taps the host's shared link
    """
    throttle_classes = [TelegramWhatsappScopedThrottle]
    throttle_scope = "join_request"  # rate-limit here: e.g. 2/hour per user

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        whatsapp_id = request.data.get('whatsapp_id')

        session_token = request.data.get('session_token')
        platform = request.data.get('platform')

        if not all([(telegram_id or whatsapp_id), session_token, platform]):
            return Response({"error": "Missing required fields"}, status=400)

        if platform == "telegram":
            active_user = TelegramUser.objects.filter(telegram_id=telegram_id).first()
        elif platform == "whatsapp":
            active_user = TelegramUser.objects.filter(whatsapp_id=whatsapp_id).first()
        else:
            return Response({"error": "Invalid platform"}, status=400)

        if not active_user:
            return Response({"error": "User not registered"}, status=404)

        try:
            with transaction.atomic():
                session = get_object_or_404(
                    DineInOTPSession.objects.select_for_update(),
                    session_token=session_token,
                    status='verified'  # table must already be open, host already verified
                )

                if session.user_id == active_user.id:
                    return Response({"error": "You are already the host of this table"}, status=400)

                if DineInSessionParticipant.objects.filter(
                    session=session, user=active_user, status='pending'
                ).exists():
                    return Response({"error": "Request already pending"}, status=400)

                if DineInSessionParticipant.objects.filter(
                    session=session, user=active_user, status='accepted'
                ).exists():
                    return Response({"error": "You are already part of this table"}, status=400)

                participant = DineInSessionParticipant.objects.create(
                    session=session, user=active_user, status='pending'
                )

        except Exception:
            return Response({"error": "Server error"}, status=500)

        # trigger notification to host — send via PTB/pywa: "Sandra wants to join. Accept/Decline"
        # (call your existing bot-messaging util here, e.g. notify_host_of_join_request.delay(...))

        try:
            if session.platform == "telegram":
                notify_host_telegram(
                    chat_id=session.user.telegram_id,  # or whoever the "host" contact is
                    text=f"{active_user.username} verified at Table {session.table_number}",
                    request_id=participant.id,
                    session=session, 
                    user_id=telegram_id
                )

            elif session.platform == "whatsapp":
                notify_host_whatsapp(
                    recipient_id=session.user.whatsapp_id,
                    text=f"{active_user.username} verified at Table {session.table_number}",
                    request_id=participant.id,
                    session=session,
                    user_id=whatsapp_id
                )

        except Exception:
            logger.warning(f"Failed to send join link for session {session.session_id}", exc_info=True)
            # don't fail the request — customer is still verified, just missed the link message

        return Response({
            "success": True,
            "request_id": participant.id,
            "message": "Request sent. Waiting for host to accept.",
            "table_number": session.table_number,
        }, status=201)
    

def notify_host_whatsapp(recipient_id, text, request_id, session, user_id):

    url = f"https://graph.facebook.com/v19.0/{session.restaurant.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {session.restaurant.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"join_accept:{request_id}:{user_id}", "title": "Accept"}},
                    {"type": "reply", "reply": {"id": f"join_decline:{request_id}:{user_id}", "title": "Decline"}},
                ]
            }
        }
    }
    response = requests.post(url, json=payload, headers=headers, timeout=5)
    response.raise_for_status()
    return response.json()


def notify_host_telegram(chat_id, text, request_id, session, user_id):
    url = f"https://api.telegram.org/bot{session.restaurant.bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "Accept", "callback_data": f"join_accept:{request_id}:{user_id}"},
                {"text": "Decline", "callback_data": f"join_decline:{request_id}:{user_id}"},
            ]]
        }
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()




class RespondToJoinRequestAPIView(APIView):
    """
    POST /api/dine-in/respond-join-request/
    Called when host taps Accept/Decline button from PTB/pywa callback
    """
    def post(self, request):

        host_telegram_id = request.data.get('host_telegram_id')
        request_id = request.data.get('request_id')
        action = (request.data.get('action') or "").lower()  # "accept" or "decline"
        restaurant_id = request.data.get('restaurant_id')
        user_id = request.data.get('user_id')
        platform = (request.data.get('platform') or "").lower()

        if not all([host_telegram_id, request_id, action]):
            return Response({"error": "Missing required fields"}, status=400)
        
        if platform == "telegram":
            active_user = TelegramUser.objects.filter(telegram_id=user_id).first()
            print("telegram active user: ", active_user)
        elif platform == "whatsapp":
            active_user = TelegramUser.objects.filter(whatsapp_id=user_id).first()
            print("whatsapp active user: ", active_user)

        restaurant = get_object_or_404(Restaurant, rid=restaurant_id)
        try:
            with transaction.atomic():

                participant = get_object_or_404(
                    DineInSessionParticipant.objects.select_for_update().select_related('session', 'user'),
                    id=request_id,
                    status='pending',
                    session__restaurant=restaurant,
                    user=active_user
                )
                
                session = participant.session

                # confirm the person responding is actually the host
                if session.user.telegram_id != int(host_telegram_id):
                    return Response({"error": "Only the host can respond to this request"}, status=403)

                if action == 'accept':
                    participant.accept()
                elif action == 'decline':
                    participant.decline()
                else:
                    return Response({"error": "Invalid action"}, status=400)

        except Exception:
            return Response({"error": "Server error"}, status=500)

        # notify the requester of the outcome — bot message + websocket push if you're using one
        # notify_requester_of_decision.delay(participant.user_id, participant.status, session.table_number)

        return Response({
            "success": True,
            "status": participant.status,
            "user": participant.user.username or participant.user.telegram_id,
        })