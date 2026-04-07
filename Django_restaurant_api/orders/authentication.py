import hashlib
import hmac
from urllib.parse import unquote
from django.conf import settings
from restaurants.models import Restaurant
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


class TelegramAuthentication(BaseAuthentication):
    def authenticate(self, request):

        init_data = request.data.get("init_data")
        restaurant_id = request.parser_context["kwargs"].get("restaurant_id")

        is_valid, data = verify_telegram_init_data(init_data, restaurant_id)
        print("Telegram init_data valid:", is_valid)
        print("data: ", data)

        if not is_valid:
            raise AuthenticationFailed("Invalid Telegram data")

        telegram_id = json.loads(data["user"]).get("id")

        if not telegram_id:
            raise AuthenticationFailed("Telegram user not found")

        # ✅ attach trusted user
        request.telegram_user_id = telegram_id
        print("Attached Telegram user ID:", request.telegram_user_id)

        # DRF expects : (user, auth) tuple, but we don't have a User object here since we're using Telegram IDs directly.
        return (telegram_id, None)