import requests
import logging

logger = logging.getLogger(__name__)


def register_telegram_webhook(restaurant):
    token = restaurant.bot_token  # decrypted
    token_from_function = restaurant.get_bot_token()  # decrypted

    print("token: ", token)
    print("token_from_function: ", token_from_function)
    logger.info("token : %s", token)
    logger.info("token from function : %s", token_from_function)

    webhook_url = restaurant.get_webhook_url()

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