import requests
import logging
import logging
from typing import Dict, Optional, Any, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)




logger = logging.getLogger(__name__)

def register_telegram_webhook(restaurant):
    token = restaurant.bot_token  # decrypted
    token_from_function = restaurant.get_bot_token()  # decrypted

    print("token: ", token)
    print("token_from_function: ", token_from_function)
    logger.info("token : %s", token)
    logger.info("token from function : %s", token_from_function)

    webhook_url = restaurant.get_telegram_webhook_url()

    url = f"https://api.telegram.org/bot{token}/setWebhook"

    payload = {
        "url": webhook_url,
        "secret_token": restaurant.webhook_secret_token,
        "drop_pending_updates": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        # django_restaurant_api  | response data:  {'ok': True, 'result': True, 'description': 'Webhook was set'}
        print("response data: ", response.json())
        return response.json()
    except requests.RequestException as e:
        print(f"Webhook setup failed: {e}")
        return None


def delete_webhook(restaurant):
    
    token_from_function = restaurant.get_bot_token()  # decrypted

    # telegram set webhook api
    url = f"https://api.telegram.org/bot{token_from_function}/deleteWebhook"

    response = requests.get(url)
    return response.json()




def sync_terminal_address(
    city: str,
    country: str,
    state: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    line1: Optional[str] = None,
    is_residential: bool = True,
    address_id: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:

    BASE_URL = "https://sandbox.terminal.africa/v1"

    create_url = f"{BASE_URL}/addresses"
    update_url = f"{BASE_URL}/addresses/{address_id}" if address_id else None

    headers = {
        "Authorization": f"Bearer {settings.TERMINAL_SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "city": city,
        "country": country,
        "state": state,
        "is_residential": is_residential,
    }

    if first_name:
        payload["first_name"] = first_name.strip()
    if last_name:
        payload["last_name"] = last_name.strip()
    if phone:
        payload["phone"] = phone.strip()
    if line1:
        payload["line1"] = line1.strip()

    if first_name or last_name:
        payload["name"] = f"{first_name or ''} {last_name or ''}".strip()

    try:
        if not address_id:
            response = requests.post(create_url, headers=headers, json=payload, timeout=30)
        else:
            response = requests.put(update_url, headers=headers, json=payload, timeout=30)

        response.raise_for_status()
        data = response.json()

        return True, "success", data

    except requests.RequestException as e:
        logger.error(f"Terminal address error: {str(e)}")
        return False, str(e), None