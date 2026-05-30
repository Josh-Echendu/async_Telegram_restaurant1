import requests
import logging
import logging
from typing import Dict, Optional, Any, Tuple
from django.conf import settings
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import json


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


def error_response(e):
    if hasattr(e, 'response') and e.response is not None:
        try:
            error_data = e.response.json()
            return {
                "status_code": e.response.status_code,
                "message": error_data.get("message", "No message"),
                "errors": error_data.get("errors", error_data),
                "full_response": error_data
            }
        except Exception:
            return {
                "status_code": e.response.status_code,
                "raw": e.response.text[:500]
            }
    return {"error": str(e)}



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
    zip_code: Optional[str] = None,
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

    if zip_code:
        print("Zip code provided: ", zip_code)
        payload["zip"] = zip_code.strip()
        
    logger.info("Payload field now: %s", payload)
    print("Payload field now", payload)
    # +1 (555) 630-5006
    logger.info("Payload before optional fields: %s, %s, %s, %s", phone, line1, first_name, last_name)
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
        logger.info("Terminal API address response: %s", data)

        return True, "success", data

    except requests.RequestException as e:
        err = error_response(e)
        logger.error(f"Terminal address error: {json.dumps(err, indent=2)}")
        return False, str(e.response.text), None
    


geolocator = Nominatim(user_agent="fork-and-co-app", timeout=20)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.0)

def get_coords(lga=None, state=None, country="Nigeria", max_retries=2):
    """
    Get coordinates for an LGA + State combination.
    Falls back to shorter LGA name if full name fails.
    """
    if not lga or not state:
        return False, "LGA and state are required", None

    # Try list: full name first, then fallback to first part (for hyphenated names like Ifako-Ijaiye)
    lga_variations = [lga]
    if '-' in lga:
        lga_variations.append(lga.split('-')[0])  # "Ifako-Ijaiye" → "Ifako"
        lga_variations.append(lga.split('-')[1])  # "Ifako-Ijaiye" → "Ijaiye"

    for lga_name in lga_variations:
        for attempt in range(max_retries):
            try:
                address = f"{lga_name}, {state}, {country}"
                print(f"Geopy attempting: {address}")
                location = geocode(address)
                
                if location:
                    data = {
                        "lat": location.latitude,
                        "lng": location.longitude,
                        "source": "geopy",
                        "address": location.address
                    }
                    logger.info(f"Geocoded: {address} → ({data['lat']}, {data['lng']})")
                    return True, "success", data
                
                print(f"Geopy returned None for: {address}")
                
            except Exception as e:
                err = error_response(e)
                logger.error(f"Geopy error for attempt {attempt + 1}/{max_retries}: {json.dumps(err, indent=2)}")

                if attempt == max_retries - 1:
                    print(f"geopy failed: {e}")
    
    # # --- Fallback: distance.to API (city-level) ---
    if lga and state:
        for attempt in range(max_retries):
            try:
                url = f"https://www.distance.to/api?from={lga},{state},{country}"
                response = requests.get(url, timeout=10)
                data = response.json()
                
                if "from_coords" in data:
                    data = {
                        "lat": data["from_coords"]["lat"],
                        "lng": data["from_coords"]["lng"],
                        "source": "distance.to"
                    }
                    logger.info(f"Distance.to geocoding successful for address: {lga}, {state}, {country} - {data}")
                    return True, "success", data
                
            except Exception as e:
                err = error_response(e)
                logger.error(f"Distance.to error for attempt {attempt + 1}/{max_retries}: {json.dumps(err, indent=2)}")
                    
                if attempt == max_retries - 1:
                    print(f"distance.to failed: {e}")

    return False, "failed", None