import json
import urllib.parse
from rest_framework.throttling import ScopedRateThrottle



class TelegramWhatsappScopedThrottle(ScopedRateThrottle):

    def get_cache_key(self, request, view):

        restaurant_id = request.data.get("restaurant_id")
        whatsapp_id = request.data.get("whatsapp_id")
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