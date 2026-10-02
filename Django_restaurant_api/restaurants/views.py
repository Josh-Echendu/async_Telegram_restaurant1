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
from django.shortcuts import render
from django.db import IntegrityError, transaction, OperationalError
from rest_framework.views import APIView
from django.db.models import Q
import redis
from .tasks import retry_join_notification, notify_host_whatsapp, notify_host_telegram

logger = logging.getLogger(__name__)
redis_client = redis.Redis.from_url(settings.REDIS_URL)


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

    print("data: ", data)

    return Response(data)


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
        platform = (request.data.get('platform') or "").lower()

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
                
                session.verify(active_user=active_user, platform=platform)  # uses your method (cleaner than manual update)

        except Exception:
            return Response({"error": "Server error"}, status=500)

        # Send the table session link to the host user
        try:
            join_link = f"{settings.NGROK_DJANGO}/restaurants/join/{session.session_token}/"

            message = (
                f"You're verified at Table {session.table_number}, {session.restaurant.name}.\n\n"
                f"Share this link with your friends so they can join:\n{join_link}"
            )
            if platform == "telegram":
                send_host_telegram_message(chat_id=telegram_id, session=session, message=message)
            elif platform == "whatsapp":
                send_host_whatsapp_message(recipient_id=whatsapp_id, session=session, message=message)
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


def send_host_telegram_message(chat_id, session, message):

    url = f"https://api.telegram.org/bot{session.restaurant.bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_host_whatsapp_message(recipient_id, session, message):

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


def join_landing_redirect(request, session_token):
    session = get_object_or_404(DineInOTPSession, session_token=session_token, status='verified')
    
    # Remove @ if it exists
    bot_username = session.restaurant.bot_username
    if bot_username and bot_username.startswith('@'):
        bot_username = bot_username[1:]  # Remove the @
    
    context = {
        'table_number': session.table_number,
        'restaurant_name': session.restaurant.name,
        'whatsapp_link': f"https://wa.me/{session.restaurant.whatsapp_business_phone}?text=join_{session_token}",
        'telegram_link': f"https://t.me/{bot_username}?start=join_{session_token}",
    }
    
    return render(request, 'restaurant/join_landing.html', context)


# class RequestJoinTableAPIView(APIView):
#     """
#     POST /restaurant/dine-in/request-join/
#     Called when Sandra/Tunde/Emma taps the host's shared link
#     """
#     # throttle_classes = [TelegramWhatsappScopedThrottle]
#     # throttle_scope = "join_request"  # rate-limit here: e.g. 2/hour per user

#     def post(self, request):

#         user_id = request.data.get('user_id')
#         restaurant_id = request.data.get('restaurant_id')
#         session_token = request.data.get('session_token')
#         platform = (request.data.get('platform') or "").lower()

#         # 🔥 SMART FALLBACK: If no token in request, get from Redis
#         if session_token is None:
#             session_token = redis_client.get(f"user_session_token:{restaurant_id}:{user_id}")

#         else:
#             # 🔐 INTERNAL SECURITY
#             api_key = request.headers.get("X-INTERNAL-API-KEY")
#             if api_key != settings.INTERNAL_API_KEY:
#                 return Response({"error": "unauthorized"}, status=403)

#         if not all([user_id, session_token, platform, restaurant_id]):
#             return Response({"error": "Missing required fields"}, status=400)

#         if platform == "telegram":
#             active_user = TelegramUser.objects.filter(telegram_id=user_id).first()
#         elif platform == "whatsapp":
#             active_user = TelegramUser.objects.filter(whatsapp_id=user_id).first()
#         else:
#             return Response({"error": "Invalid platform"}, status=400)

#         if not active_user:
#             return Response({"error": "User not registered"}, status=404)

#         restaurant = get_object_or_404(Restaurant, rid=restaurant_id)
        
#         try:
#             with transaction.atomic():
#                 session = get_object_or_404(
#                     DineInOTPSession.objects.select_related('restaurant').select_for_update(),
#                     session_token=session_token,
#                     restaurant=restaurant,
#                     status='verified'  # table must already be open, host already verified
#                 )
#                 print("session already verified by host: ")

#                 if session.user_id == active_user.id:
#                     logger.info("You are already the host of this table")
#                     print("You are already the host of this table")
#                     return Response({
#                         "success": True,
#                         "status": "accepted",
#                         "message": "You are already the host of this table"
#                     }, status=200)

#                 if DineInSessionParticipant.objects.filter(
#                     session=session, user=active_user, status='pending'
#                 ).exists():
#                     logger.info("Request already pending")
#                     print("Request already pending")
#                     return Response({
#                         "success": True,
#                         "status": "pending",
#                         "message": "Request already pending"
#                     }, status=200)

#                 if DineInSessionParticipant.objects.filter(
#                     session=session, user=active_user, status='accepted'
#                 ).exists():
#                     logger.info("You are already part of this table")
#                     print("You are already part of this table")
#                     return Response({
#                         "success": True,
#                         "status": "accepted",
#                         "message": "You are already part of this table"
#                     }, status=200)
                
#                 participant = DineInSessionParticipant.objects.create(
#                     session=session, user=active_user, status='pending'
#                 )
#                 redis_client.set(f"join_status:{participant.id}", "pending", ex=86400)
#                 redis_client.set(f"join_id:{session.restaurant.rid}:{platform}:{user_id}", participant.id, ex=86400)

#         except Exception:
#             return Response({"error": "Server error"}, status=500)

#         # trigger notification to host — send via PTB/pywa: "Sandra wants to join. Accept/Decline"
#         # (call your existing bot-messaging util here, e.g. notify_host_of_join_request.delay(...))


#         try:
#             if session.platform == "telegram":
#                 notify_host_telegram(
#                     chat_id=session.user.telegram_id,  # or whoever the "host" contact is
#                     text=f"{active_user.username} wants to be verified at Table {session.table_number} \n\n platform: {platform}",
#                     participant_id=participant.id,
#                     session=session, 
#                 )

#             elif session.platform == "whatsapp":
#                 notify_host_whatsapp(
#                     recipient_id=session.user.whatsapp_id,
#                     text=f"{active_user.username} wants to be verified at Table {session.table_number} \n\n platform: {platform}",
#                     participant_id=participant.id,
#                     session=session,
#                 )

#         except Exception:
#             logger.warning(f"Failed to send join link for session {session.session_id}", exc_info=True)
#             # don't fail the request — customer is still verified, just missed the link message

#         return Response({
#             "success": True,
#             "participant_id": participant.id,
#             "message": "Request sent. Waiting for host to accept.",
#             "table_number": session.table_number,
#         }, status=201)
    
# request_to_join_table_api_view = RequestJoinTableAPIView.as_view()



class RequestJoinTableAPIView(APIView):
    """
    POST /restaurant/dine-in/request-join/
    Called when Sandra/Tunde/Emma taps the host's shared link
    """

    def post(self, request):

        user_id = request.data.get('user_id')
        restaurant_id = request.data.get('restaurant_id')
        session_token = request.data.get('session_token')
        platform = (request.data.get('platform') or "").lower()
        idempotency_key = request.data.get('idempotency_key')  # ✅ ADD THIS

        # 🔥 SMART FALLBACK: If no token in request, get from Redis
        if session_token is None:
            session_token = redis_client.get(f"user_session_token:{restaurant_id}:{user_id}")

        else:
            # 🔐 INTERNAL SECURITY
            api_key = request.headers.get("X-INTERNAL-API-KEY")
            if api_key != settings.INTERNAL_API_KEY:
                return Response({"error": "unauthorized"}, status=403)

        if not all([user_id, session_token, platform, restaurant_id]):
            return Response({"error": "Missing required fields"}, status=400)

        if platform == "telegram":
            active_user = TelegramUser.objects.filter(telegram_id=user_id).first()
        elif platform == "whatsapp":
            active_user = TelegramUser.objects.filter(whatsapp_id=user_id).first()
        else:
            return Response({"error": "Invalid platform"}, status=400)

        if not active_user:
            return Response({"error": "User not registered"}, status=404)

        restaurant = get_object_or_404(Restaurant, rid=restaurant_id)
        
        # ✅ CHECK IDEMPOTENCY FIRST
        if idempotency_key:
            idempotent_result = redis_client.get(f"join_idempotent:{idempotency_key}")
            if idempotent_result:

                # Already processed - return previous result
                return Response(json.loads(idempotent_result), status=200)
        
        try:
            with transaction.atomic():

                #  Extract the Host session
                session = get_object_or_404(
                    DineInOTPSession.objects.select_related('restaurant').select_for_update(),
                    session_token=session_token,
                    restaurant=restaurant,
                    status='verified'
                )
                print("session already verified by host: ")

                if session.user == active_user:
                    logger.info("You are already the host of this table")
                    print("You are already the host of this table")
                    return Response({
                        "success": True,
                        "status": "accepted",
                        "message": "You are already the host of this table"
                    }, status=200)

                if DineInSessionParticipant.objects.filter(
                    session=session, user=active_user, status='pending'
                ).exists():
                    logger.info("Request already pending")
                    return Response({
                        "success": True,
                        "status": "pending",
                        "message": "Request already pending"
                    }, status=200)

                if DineInSessionParticipant.objects.filter(
                    session=session, user=active_user, status='accepted'
                ).exists():
                    logger.info("You are already part of this table")
                    return Response({
                        "success": True,
                        "status": "accepted",
                        "message": "You are already part of this table"
                    }, status=200)
                
                participant = DineInSessionParticipant.objects.create(
                    session=session, user=active_user, status='pending'
                )
                redis_client.set(f"join_status:{participant.id}", "pending", ex=86400)
                redis_client.set(f"join_id:{session.restaurant.rid}:{platform}:{user_id}", participant.id, ex=86400)

                print(f"Participant {participant.id} created for session {session.session_id} by user {active_user.id}")

                # ✅ SEND NOTIFICATION WITH RETRY
                notification_sent = self._send_notification_with_retry(
                    session=session,
                    participant=participant,
                    active_user=active_user,
                    platform=platform,
                    max_retries=3
                )

                print(f"Notification sent: {notification_sent} for participant {participant.id} in session {session.session_id}")

                if not notification_sent:

                    retry_join_notification.delay(participant.id, session.id, active_user.id, platform)
                    
                    # Still return success to user
                    # They will get notification when host responds
                    logger.warning(f"Notification failed for participant {participant.id}, queued for retry")

        except Exception as e:
            logger.exception(f"Error processing join request: {e}")
            return Response({"error": "Server error"}, status=500)

        response_data = {
            "success": True,
            "participant_id": participant.id,
            "message": "Request sent. Waiting for host to accept.",
            "table_number": session.table_number,
        }
        
        # ✅ STORE IDEMPOTENCY RESULT
        if idempotency_key:
            redis_client.setex(
                f"join_idempotent:{idempotency_key}",
                3600,  # 1 hour expiry
                json.dumps(response_data)
            )
        
        return Response(response_data, status=201)


    def _send_notification_with_retry(self, session, participant, active_user, platform, max_retries=3):
        """Send notification with retry logic"""
        
        for attempt in range(max_retries):
            try:
                if platform == "telegram":
                    notify_host_telegram(
                        chat_id=session.user.telegram_id,
                        text=f"{active_user.username} wants to be verified at Table {session.table_number} \n\n platform: {platform}",
                        participant_id=participant.id,
                        session=session,
                    )
                elif platform == "whatsapp":
                    notify_host_whatsapp(
                        recipient_id=session.user.whatsapp_id,
                        text=f"{active_user.username} wants to be verified at Table {session.table_number} \n\n platform: {platform}",
                        participant_id=participant.id,
                        session=session,
                    )
                logger.info(f"Notification sent successfully (attempt {attempt+1})")
                return True
                
            except Exception as e:
                logger.warning(f"Notification attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                else:
                    return False
        return False

request_to_join_table_api_view = RequestJoinTableAPIView.as_view()



class RespondToJoinRequestAPIView(APIView):
    """
    POST /api/dine-in/respond-join-request/
    Called when host taps Accept/Decline button from PTB/pywa callback
    """

    @transaction.atomic
    def post(self, request):
        host_user_id = request.data.get('host_user_id')
        participant_id = request.data.get('participant_id')
        action = (request.data.get('action') or "").lower()
        platform = (request.data.get('platform') or "").lower()  # fixed: was reading 'action'

        if not all([host_user_id, participant_id, action]):
            return Response({"error": "Missing required fields"}, status=400)

        try:
            with transaction.atomic():
                participant = get_object_or_404(
                    DineInSessionParticipant.objects.select_for_update().select_related('session', 'user'),
                    id=participant_id,
                    status='pending',
                )
                session = participant.session

                # check only the field relevant to this platform, not both
                is_host = False
                if platform == 'telegram':
                    is_host = session.user.telegram_id == int(host_user_id)
                elif platform == 'whatsapp':
                    is_host = session.user.whatsapp_id == str(host_user_id)
                else:
                    return Response({"error": "Invalid platform"}, status=400)

                if not is_host:
                    logger.info("Only the host can respond to this request")
                    return Response({"error": "Only the host can respond to this request"}, status=403)


                if action == 'accept':
                    
                    participant.accept()

                    redis_client.set(
                        f"join:{participant.id}",
                        json.dumps({
                            "status": "accepted",
                            "session_id": session.session_id,
                            "table_number": session.table_number,
                        }),
                        ex=86400
                    )

                elif action == 'decline':
                    
                    participant.decline()
                    
                    redis_client.set(
                        f"join:{participant.id}",
                        json.dumps({
                            "status": "declined",
                            "session_id": None,
                            "table_number": session.table_number,
                        }),
                        ex=86400
                    )
                else:
                    return Response({"error": "Invalid action"}, status=400)

        except Exception:
            return Response({"error": "Server error"}, status=500)

        return Response({
            "success": True,
            "status": participant.status,
            "user": participant.user.username or participant.user.telegram_id,
        })
        
respond_to_join_api_view = RespondToJoinRequestAPIView.as_view()



# views.py
from django.http import StreamingHttpResponse
import json
import time


def sse_join_status(request, restaurant_id, platform, user_id):
    def event_stream():
        last_status = None
        
        while True:
            try:
                # 1. Get participant_id
                participant_id_bytes = redis_client.get(f"join_id:{restaurant_id}:{platform}:{user_id}")
                
                if participant_id_bytes is None:
                    yield f"data: {json.dumps({'participant': None, 'error': 'No join request found'})}\n\n"
                    break
                
                participant_id = participant_id_bytes.decode()
                
                # 2. Get the ONE key (status + session_id + table_number)
                join_data_bytes = redis_client.get(f"join:{participant_id}")
                
                if join_data_bytes is None:
                    yield f"data: {json.dumps({'status': None, 'error': 'Status not found or expired'})}\n\n"
                    break
                
                join_data = json.loads(join_data_bytes.decode())
                status = join_data.get('status')
                
                # 3. Only send if status changed
                if status != last_status:
                    last_status = status
                    
                    # Send full payload — status + session_id + table_number
                    yield f"data: {json.dumps({
                        'status': status,
                        'participant_id': participant_id,
                        'session_id': join_data.get('session_id'),
                        'table_number': join_data.get('table_number'),
                    })}\n\n"
                    
                    if status in ['accepted', 'declined']:
                        break
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"SSE error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


class CheckJoinStatusByUserAPIView(APIView):
    """
    GET /restaurants/dine-in/join-status-by-user/<str:restaurant_id>/<str:platform>/<str:user_id>/
    Mini-app calls this using telegram_id (no participant_id needed)
    """
    def get(self, request, restaurant_id, platform, user_id):
        participant_id_bytes = redis_client.get(f"join_id:{restaurant_id}:{platform}:{user_id}")

        if participant_id_bytes is None:
            return Response({"found": False, "error": "No join request found for this user"}, status=404)

        participant_id = participant_id_bytes.decode()

        status_bytes = redis_client.get(f"join_status:{participant_id}")
        if status_bytes is None:
            return Response({"status": False, "error": "Status not found or expired"}, status=404)

        return Response({
            "status": status_bytes.decode(),
            "participant_id": participant_id  # handy if mini-app wants it for the "request again" call
        })

check_join_status_api_view = CheckJoinStatusByUserAPIView.as_view()


# Yes — that's exactly right, and it's genuinely simple stated that way. L
# et me just confirm each piece matches what we built, so you can hold this as the final picture without second-guessing it:

# **Friend clicks link** → request goes to host in the background, friend can freely browse the bot menu (Order Food, Dining, etc.) — nothing blocks him here.

# **Friend clicks mini-app button** → this is the one checkp oint. If the host hasn't accepted yet, a modal shows: "Not accepted yet — ask your host to approve you," nothing else, no ordering screen behind it.

# **Host accepts** → your WebSocket pushes the update straight to the friend's open mini-app screen, modal disappears, menu unlocks — no polling delay, no refresh needed, since he's already connected.

# **Host mistakenly declines** → friend sees a "Request again" button right there in the same modal, taps it, new request goes to host, same as the first time.

# That's the whole thing. Nothing missing, nothing overbuilt. This is a clean, shippable version of the feature — you can stop redesigning it now and just build exactly this.