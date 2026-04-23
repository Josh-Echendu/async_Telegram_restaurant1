from calendar import weekday

from .models import Restaurant, RestaurantDeliveryOpeningHours
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone



# from django.utils import timezone

# @api_view(["GET"])
# def get_restaurant_internal(request, rid):

#     api_key = request.headers.get("X-INTERNAL-API-KEY")
#     if api_key != settings.INTERNAL_API_KEY:
#         return Response({"error": "unauthorized"}, status=403)

#     try:
#         restaurant = Restaurant.objects.get(rid=rid)
#     except Restaurant.DoesNotExist:
#         return Response({}, status=404)

#     day_of_week = timezone.now().weekday()

#     opening_hours = restaurant.delivery_opening_hours.filter(
#         day_of_week=day_of_week
#     ).first()

#     open_time = opening_hours.open_time if opening_hours else None
#     close_time = opening_hours.close_time if opening_hours else None

#     # 🧠 DELIVERY STATUS
#     is_delivery_supported = restaurant.service_mode in ["delivery", "both"]
#     is_delivery_open = False

#     if is_delivery_supported and open_time:
#         now = timezone.now().time()

#         if open_time <= now <= close_time:
#             is_delivery_open = True

#     # 🧠 DINE-IN STATUS
#     is_dine_in_supported = restaurant.service_mode in ["dine_in", "both"]

#     return Response({
#         "rid": restaurant.rid,
#         "bot_token": restaurant.get_bot_token(),
#         "bot_name": restaurant.name,
#         "webhook_secret_token": str(restaurant.webhook_secret_token),

#         "is_bot_active": restaurant.is_bot_active,
#         "is_accepting_orders": restaurant.is_accepting_orders,

#         "service_mode": restaurant.service_mode,
#         "max_tables": restaurant.max_tables,

#         # 🟢 DELIVERY INFO
#         "delivery": {
#             "supported": is_delivery_supported,
#             "open": is_delivery_open,
#             "open_time": open_time,
#             "close_time": close_time,
#         },

#         # 🟢 DINE-IN INFO
#         "dine_in": {
#             "supported": is_dine_in_supported
#         }
#     })


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
    

    # 👉 This returns an integer from 0 to 6
    day_of_week = timezone.now().weekday()  # Get current day of week (0=Monday, 6=Sunday)
    
    delivery_opening_hours = restaurant.delivery_opening_hours.filter(
        day_of_week=day_of_week
    ).first()

    open_time = delivery_opening_hours.open_time if delivery_opening_hours else None
    close_time = delivery_opening_hours.close_time if delivery_opening_hours else None


    return Response({
        "rid": restaurant.rid,
        "bot_token": restaurant.get_bot_token(),  # ✅ REQUIRED
        "bot_name": restaurant.name,
        "webhook_secret_token": str(restaurant.webhook_secret_token),
        "is_bot_active": restaurant.is_bot_active,
        "is_accepting_orders": restaurant.is_accepting_orders,
        
        "service_mode": restaurant.service_mode,
        "business_type": restaurant.business_type,
        "max_tables": restaurant.max_tables,
        "open_time": open_time,
        "close_time": close_time,
        "time_zone": restaurant.timezone,
        "is_closed": delivery_opening_hours.is_closed if delivery_opening_hours else None
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
