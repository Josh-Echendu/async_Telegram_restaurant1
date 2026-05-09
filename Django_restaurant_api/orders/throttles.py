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


class TelegramWhatsappScopedThrottle(ScopedRateThrottle):

    def get_cache_key(self, request, view):

        restaurant_id = view.kwargs.get("restaurant_id")
        whatsapp_id = request.data.get("user_id") or request.data.get("whatsapp_id")        
        init_data = request.data.get("init_data")

        telegram_id = None

        # Extract telegram_id
        if init_data:
            try:
                parsed = dict(urllib.parse.parse_qsl(init_data))
                user = parsed.get("user")

                if user:
                    user_data = json.loads(urllib.parse.unquote(user))
                    telegram_id = user_data.get("id")

            except Exception:
                telegram_id = None  # don't kill flow

        # Must have restaurant
        if not restaurant_id:
            return None

        # Build ident
        if telegram_id:
            ident = f"tg_{telegram_id}_rest_{restaurant_id}"
        elif whatsapp_id:
            ident = f"wa_{whatsapp_id}_rest_{restaurant_id}"
        else:
            ident = f"anon_rest_{restaurant_id}"            
            
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
