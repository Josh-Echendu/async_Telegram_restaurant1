import hashlib
import hmac
from urllib.parse import unquote
from django.conf import settings
from restaurants.models import Restaurant, DineInOTPSession
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response  # ✅ CORRECT
from rest_framework import status
import json




def verify_telegram_init_data(init_data: str, restaurant_id: str):
    """
    Verifies Telegram Web App init_data according to Telegram docs.
    Returns (is_valid, data_dict).
    """
    try: 
        # Optimized: Only fetches the ID and bot_token from the DB
        restaurant = Restaurant.objects.only('bot_token').get(rid=restaurant_id)
    except Restaurant.DoesNotExist: return False, {}

    if not init_data:
        return False, {}
    
    try:
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
            msg=restaurant.get_bot_token().encode(),
            digestmod=hashlib.sha256
        ).digest()

        # Step 5: Second HMAC (key=secret_key, message=data_check_string)
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if calculated_hash != received_hash:
            return False, {}

        # print("Received hash:", received_hash)
        # print("Calculated hash:", calculated_hash)
        # print("Data check string:", repr(data_check_string))
        # print("Secret key (hex):", secret_key.hex())

        # Step 6: Return validation result
        return calculated_hash == received_hash, {
            key: unquote(value) for key, value in parsed_data.items()
        }
    except Exception as e:
        return False, {}

class TelegramWhatsappAuthentication(BaseAuthentication):

    def authenticate(self, request):
        session_id = request.data.get('session_id')
        restaurant_id = request.parser_context["kwargs"].get("restaurant_id")
        platform = request.data.get('platform')
        whatsapp_id = request.data.get("user_id")
        mode = request.data.get('mode')

        if not all([restaurant_id, platform, mode]):
            raise AuthenticationFailed("Missing session authentication data")

        platform = platform.lower()

        if platform == 'whatsapp':
            if mode and mode.lower() == 'dine_in' and session_id:
                session = DineInOTPSession.objects.filter(
                    user__whatsapp_id=whatsapp_id,
                    status='verified',
                    session_id=session_id,
                    restaurant__rid=restaurant_id,
                ).select_related('user', 'restaurant').first()

                if not session:
                    raise AuthenticationFailed("Invalid session")

            # Optional: also validate Django session consistency
            if not (
                request.session.get("user_id") == whatsapp_id and
                request.session.get("restaurant_id") == restaurant_id and
                request.session.get("mode") == mode
            ):
                raise AuthenticationFailed("Session mismatch")

            request.whatsapp_user_id = whatsapp_id
            return (whatsapp_id, None)

        if platform == 'telegram':
            init_data = request.data.get("init_data")
            is_valid, data = verify_telegram_init_data(init_data, restaurant_id)
            if not is_valid:
                raise AuthenticationFailed("Invalid Telegram data")

            user_data = json.loads(data["user"])
            telegram_id = user_data.get("id")
            if not telegram_id:
                raise AuthenticationFailed("Telegram user not found")

            if mode and mode.lower() == 'dine_in' and session_id:
                session = DineInOTPSession.objects.filter(
                    user__telegram_id=telegram_id,
                    status='verified',
                    session_id=session_id,
                    restaurant__rid=restaurant_id,
                ).first()

                if not session:
                    raise AuthenticationFailed("Invalid session")

            # DRF expects : (user, auth) tuple, but we don't have a User object here since we're using Telegram IDs directly
            request.telegram_user_id = telegram_id
            return (telegram_id, None)

        raise AuthenticationFailed("Unsupported platform")