import pytz
from restaurants.models import RestaurantDeliveryOpeningHours
from django.utils import timezone



# 2. check delivery time
def is_delivery_available(restaurant):
    """
    Check if restaurant is currently accepting delivery orders
    based on their delivery opening hours.
    """

    # Get restaurant's timezone
    try:
        restaurant_tz = pytz.timezone(restaurant.timezone)
    except Exception:
        # Fallback to Nigeria time if timezone is invalid
        restaurant_tz = pytz.timezone('Africa/Lagos')

    # Get current time in restaurant's local timezone
    now_utc = timezone.now()
    now_local = now_utc.astimezone(restaurant_tz)

    current_day = now_local.weekday()  # Monday=0, Sunday=6
    current_time = now_local.time()
        
    # Get today's delivery hours
    try:
        today_hours = restaurant.delivery_opening_hours.get(
            day_of_week=current_day
        )
    except RestaurantDeliveryOpeningHours.DoesNotExist:
        return False, "🙏 We're closed for delivery today. See you tomorrow!"

    # Check if restaurant is closed today
    if today_hours.is_closed:
        return False, "🙏 We're closed for delivery today. See you tomorrow!"

    # Check if open_time and close_time exist
    if not today_hours.open_time or not today_hours.close_time:
        return False, "🙏 We're closed for delivery today. See you tomorrow!"

    # Handle overnight hours (e.g., 11pm to 2am)
    if today_hours.open_time <= today_hours.close_time:
        
        # Normal hours (e.g., 09:00 to 22:00)
        is_open = today_hours.open_time <= current_time <= today_hours.close_time
    else:
        
        # Overnight hours (e.g., 22:00 to 02:00)
        is_open = current_time >= today_hours.open_time or current_time <= today_hours.close_time

    if not is_open:
        
        # Format times in 12-hour format for user
        open_12hr = today_hours.open_time.strftime('%I:%M %p')
        close_12hr = today_hours.close_time.strftime('%I:%M %p')
        
        return False, f"🚚 Delivery available from {open_12hr} to {close_12hr} (Nigeria time)"

    return True, "Delivery available"