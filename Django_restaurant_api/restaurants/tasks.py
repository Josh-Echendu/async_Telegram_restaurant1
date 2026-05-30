import logging

from celery import shared_task
from .services import get_coords
from .services import sync_terminal_address

logger = logging.getLogger(__name__)

def get_restaurant_model():
    from .models import Restaurant
    return Restaurant

@shared_task(bind=True, max_retries=5, default_retry_delay=5)
def create_or_update_restaurant_terminal_address(self, restaurant_id, **kwargs):

    try:
        success, msg, data = sync_terminal_address(**kwargs)

        if not success:
            raise Exception(msg)

        logger.info(f"Terminal address synced successfully for restaurant {restaurant_id}: {data}")
        address_id = data.get("data", {}).get("address_id")
        
        if restaurant_id and address_id:
            Restaurant = get_restaurant_model()
            Restaurant.objects.filter(rid=restaurant_id).update(
                pick_up_address_id=address_id
            )

        return True

    except Exception as e:
        raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 60))




@shared_task(bind=True, max_retries=5, default_retry_delay=5)
def get_coordinates_for_address(self, restaurant_id, **kwargs):

    try:
        success, msg, coords = get_coords(**kwargs)
        
        if not success:
            raise Exception(f"Failed to get coordinates: {msg}")

        restaurant_func = get_restaurant_model()
        restaurant_func.objects.filter(rid=restaurant_id).update(
            latitude=coords.get("lat"),
            longitude=coords.get("lng")
        )

        logger.info(f"Coordinates obtained for restaurant {restaurant_id}: {coords}")
        
        # Here you can save the coordinates to the database if needed

        return True

    except Exception as e:
        raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 60))