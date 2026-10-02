import logging

from celery import shared_task
from .services import get_coords
from .services import sync_terminal_address
import requests
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
    

def notify_host_whatsapp(recipient_id, text, participant_id, session):

    url = f"https://graph.facebook.com/v19.0/{session.restaurant.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {session.restaurant.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"join_accept_{participant_id}", "title": "Accept"}},
                    {"type": "reply", "reply": {"id": f"join_decline_{participant_id}", "title": "Decline"}},
                ]
            }
        }
    }
    response = requests.post(url, json=payload, headers=headers, timeout=7)
    response.raise_for_status()
    return response.json()



def notify_host_telegram(chat_id, text, participant_id, session):
    url = f"https://api.telegram.org/bot{session.restaurant.bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "Accept", "callback_data": f"join_accept_{participant_id}"},
                {"text": "Decline", "callback_data": f"join_decline_{participant_id}"},
            ]]
        }
    }
    response = requests.post(url, json=payload, timeout=7)
    response.raise_for_status()
    return response.json()


@shared_task(bind=True, max_retries=3)
def retry_join_notification(self, participant_id, session_id, user_id, platform):
    """Retry sending join notification to host"""
    try:
        from restaurants.models import DineInOTPSession, DineInSessionParticipant
        from userAuths.models import TelegramUser
        
        participant = DineInSessionParticipant.objects.get(id=participant_id)
        session = DineInOTPSession.objects.get(id=session_id)
        active_user = TelegramUser.objects.get(id=user_id)
        
        # Check if already processed (host responded)
        if participant.status != 'pending':
            logger.info(f"Participant {participant_id} already {participant.status}, skipping retry")
            return
        
        # Send notification
        if session.platform == "telegram":
            notify_host_telegram(
                chat_id=session.user.telegram_id,
                text=f"{active_user.username} wants to be verified at Table {session.table_number}",
                participant_id=participant.id,
                session=session,
            )
        elif session.platform == "whatsapp":
            notify_host_whatsapp(
                recipient_id=session.user.whatsapp_id,
                text=f"{active_user.username} wants to be verified at Table {session.table_number}",
                participant_id=participant.id,
                session=session,
            )
        
        logger.info(f"Retry notification sent for participant {participant_id}")
        
    except Exception as e:
        # Retry with exponential backoff
        logger.error(f"Retry notification failed: {e}")
        raise self.retry(countdown=60 * (2 ** self.request.retries))