from celery import shared_task
from .services import sync_terminal_address

def get_restaurant_model():
    from .models import Restaurant
    return Restaurant

@shared_task(bind=True, max_retries=5, default_retry_delay=5)
def create_or_update_restaurant_terminal_address(self, restaurant_id, **kwargs):

    try:
        success, msg, data = sync_terminal_address(**kwargs)

        if not success:
            raise Exception(msg)

        address_id = data.get("address_id")

        if restaurant_id and address_id:
            Restaurant = get_restaurant_model()
            Restaurant.objects.filter(rid=restaurant_id).update(
                pick_up_address_id=address_id
            )

        return True

    except Exception as e:
        raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 60))


# from celery import shared_task
# from typing import Dict, Optional, Any, Tuple
# from django.conf import settings
# import logging
# import requests
# import time

# logger = logging.getLogger(__name__)


# @shared_task(bind=True, max_retries=5, default_retry_delay=5)
# def create_or_update_restaurant_terminal_address(
#     self,
#     city: str,
#     country: str,
#     state: str,
#     first_name: Optional[str] = None,
#     last_name: Optional[str] = None,
#     phone: Optional[str] = None,
#     line1: Optional[str] = None,
#     is_residential: bool = True,
#     address_id: Optional[str] = None,
#     restaurant_id: Optional[int] = None
# ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:

#     BASE_URL = "https://sandbox.terminal.africa/v1"

#     CREATE_URL = f"{BASE_URL}/addresses"
#     UPDATE_URL = f"{BASE_URL}/addresses/{address_id}" if address_id else None

#     headers = {
#         "Authorization": f"Bearer {settings.TERMINAL_SECRET_KEY}",
#         "Content-Type": "application/json",
#         "Accept": "application/json"
#     }

#     payload = {
#         "city": city,
#         "country": country,
#         "state": state,
#         "is_residential": is_residential
#     }

#     if first_name:
#         payload["first_name"] = first_name.strip()
#     if last_name:
#         payload["last_name"] = last_name.strip()
#     if phone:
#         payload["phone"] = phone.strip()
#     if line1:
#         payload["line1"] = line1.strip()

#     if first_name or last_name:
#         payload["name"] = f"{first_name or ''} {last_name or ''}".strip()

#     try:
#         # =========================
#         # 1. CREATE OR UPDATE LOGIC
#         # =========================
#         if not address_id:
#             response = requests.post(
#                 CREATE_URL,
#                 headers=headers,
#                 json=payload,
#                 timeout=30
#             )
#         else:
#             response = requests.put(
#                 UPDATE_URL,
#                 headers=headers,
#                 json=payload,
#                 timeout=30
#             )

#         response.raise_for_status()
#         response_data = response.json()

#         new_address_id = response_data.get("address_id")

#         # =========================
#         # 2. SAVE TO DB (SAFE UPDATE)
#         # =========================
#         if restaurant_id and new_address_id:
#             Restaurant = get_restaurant_model()
#             Restaurant.objects.filter(rid=restaurant_id).update(
#                 pick_up_address_id=new_address_id
#             )

#         logger.info(f"Terminal address synced successfully: {new_address_id}")

#         return True, "Address synced successfully", response_data

#     except requests.exceptions.Timeout as e:
#         logger.error(f"timeout error: {str(e)}")
#         raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 60))  # Exponential backoff with max delay of 60 seconds

#     except requests.exceptions.ConnectionError as e:
#         logger.error(f"connection error: {str(e)}")
#         raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 60))  # Exponential backoff with max delay of 60 seconds

#     except requests.exceptions.RequestException as e:
#         logger.error(f"Terminal API error: {str(e)}")
#         raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 60))  # Exponential backoff with max delay of 60 seconds

#     except Exception as e:
#         logger.error(f"Unexpected error: {str(e)}")
#         raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 60))  # Exponential backoff with max delay of 60 seconds