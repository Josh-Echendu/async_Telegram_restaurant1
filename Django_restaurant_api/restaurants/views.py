from .models import Restaurant
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings


@api_view(["GET"])
def get_restaurant_internal(request, rid):

    # 🔐 INTERNAL SECURITY
    api_key = request.headers.get("X-INTERNAL-API-KEY")
    if api_key != settings.INTERNAL_API_KEY:
        return Response({"error": "unauthorized"}, status=403)

    try:
        restaurant = Restaurant.objects.get(rid=rid)
    except Restaurant.DoesNotExist:
        return Response({}, status=404)

    return Response({
        "bot_token": restaurant.get_bot_token(),  # ✅ REQUIRED
        "bot_name": restaurant.name,
        "webhook_secret_token": str(restaurant.webhook_secret_token),
        "is_bot_active": restaurant.is_bot_active,
        "is_accepting_orders": restaurant.is_accepting_orders,
        "kitchen_chat_id": restaurant.kitchen_chat_id,
    })