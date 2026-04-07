# from rest_framework.throttling import ScopedRateThrottle


# class TelegramScopedThrottle(ScopedRateThrottle):

#     def get_cache_key(self, request, view):

#         # 1. Get telegram_id from request body
#         telegram_id = request.data.get("init_data", {})
#         print('telegram_id_throttle: ', telegram_id)

#         # 2. Get restaurant_id from URL (VERY IMPORTANT)
#         restaurant_id = view.kwargs.get("restaurant_id")
#         print('restaurant_id_throttle: ', restaurant_id)

#         # 3. If anything is missing → don't throttle
#         if not telegram_id or not restaurant_id:
#             print("Missing telegram_id or restaurant_id, skipping throttle.")
#             return None

#         # 4. Combine both into ONE unique key
#         ident = f"tg_{telegram_id}_rest_{restaurant_id}"
#         print("indent_throttle: ", ident)

#         # 5. Return final key used by DRF
#         return self.cache_format % {
#             "scope": self.scope,
#             "ident": ident,
#         }



import json
import urllib.parse
from rest_framework.throttling import ScopedRateThrottle


class TelegramScopedThrottle(ScopedRateThrottle):

    def get_cache_key(self, request, view):

        # 1. restaurant_id comes from URL
        restaurant_id = view.kwargs.get("restaurant_id")

        # 2. init_data comes from request body
        init_data = request.data.get("init_data")

        telegram_id = None

        # 3. Extract telegram_id from init_data
        if init_data:
            try:
                parsed = dict(urllib.parse.parse_qsl(init_data))
                user = parsed.get("user")

                if user:
                    user_data = json.loads(urllib.parse.unquote(user))
                    telegram_id = user_data.get("id")
                    print("throttle user_data: ", user_data)

            except Exception:
                return None  # if parsing fails, skip throttle

        # 4. If missing data → skip throttle (safe fallback)
        if not telegram_id or not restaurant_id:
            return None

        # 5. Unique key per user per restaurant
        ident = f"tg_{telegram_id}_rest_{restaurant_id}"
        print("ident_throttle: ", ident)

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


# class TelegramScopedThrottle(ScopedRateThrottle):
#     """
#     Custom throttle that identifies users by telegram_id from the request.
#     This ensures each Telegram user is counted individually.
#     """
#     def get_ident(self, request):

#         # Try to get telegram_id from the incoming JSON payload
#         telegram_id = request.data.get("telegram_id")

#         restaurant_id = request.data.get('restaurant_id')
#         print('telegram_id: ', telegram_id)
#         print('restaurant_id: ', restaurant_id)
        
#         if telegram_id and restaurant_id:
#             return f"tg_{telegram_id}_rest_{restaurant_id}"  # Use Telegram ID and restaurant_id as unique identifier
        
#         if telegram_id:
#             return str(telegram_id)
        
#         # If telegram_id not provided, fallback to default behavior (IP)
#         return super().get_ident(request)
