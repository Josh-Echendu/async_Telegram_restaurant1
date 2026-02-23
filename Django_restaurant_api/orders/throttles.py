from rest_framework.throttling import ScopedRateThrottle

class TelegramScopedThrottle(ScopedRateThrottle):
    """
    Custom throttle that identifies users by telegram_id from the request.
    This ensures each Telegram user is counted individually.
    """
    def get_ident(self, request):

        # Try to get telegram_id from the incoming JSON payload
        telegram_id = request.data.get("telegram_id")
        
        if telegram_id:
            return str(telegram_id)  # Use Telegram ID as unique identifier
        
        # If telegram_id not provided, fallback to default behavior (IP)
        return super().get_ident(request)
