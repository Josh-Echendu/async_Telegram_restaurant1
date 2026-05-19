
import requests
import time
from typing import Dict, Optional, Any, Tuple
import logging
logger = logging.getLogger(__name__)

TERMINAL_SECRET_KEY="sk_test_j9hlrdxullIUbwnZ1FqNDpVGWYTdwzDx"

def restaurant_terminal_address(
    city: str,
    country: str,
    state: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    line1: Optional[str] = None,
    is_residential: bool = True,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Create an address for getting rates or arranging pickup and delivery.
    
    Args:
        city: Address city (required)
        country: ISO 2 country code for address (required)
        state: Address state (required)
        first_name: First name of person at address
        last_name: Last name of person at address
        phone: Phone number of person at address
        line1: Street address
        is_residential: Indicates if address is residential (defaults to True)
        name: Full name of person at address
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

        
        name → John Doe
        first_name → John
        last_name → Doe
        phone → 08012345678
        line1 → 25 Admiralty Way
        city → Lagos
        state → Lagos
        country → NG
        is_residential → true
        
    Returns:
        Tuple of (success: bool, message: str, data: Optional[Dict])
    """
    BASE_URL =  "https://sandbox.terminal.africa/v1"
    ADDRESSES_ENDPOINT = f"{BASE_URL}/addresses"
    REQUEST_TIMEOUT=30 # 30 seconds
    
    headers = {
        "Authorization": f"Bearer {TERMINAL_SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "city": city,
        "country": country,
        "state": state,
        "is_residential": is_residential
    }

    # https://nominatim.openstreetmap.org/?utm_source=chatgpt.com
    # https://nominatim.openstreetmap.org/?utm_source=chatgpt.com

    # Add optional fields only if they are provided and not empty
    if first_name:
        payload["first_name"] = first_name.strip()
    if last_name:
        payload["last_name"] = last_name.strip()
    if phone:
        payload["phone"] = phone.strip()
    if line1:
        payload["line1"] = line1.strip()

    if first_name or last_name:
        payload["name"] = f"{first_name} {last_name}".strip()
    
    # Retry logic for transient errors
    last_exception = None
    for attempt in range(max_retries):
        try:
            logger.info(f"Creating address (attempt {attempt + 1}/{max_retries})")

            response = requests.post(
                ADDRESSES_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()

            # Handle different status codes
            if response.status_code in (200, 201):
                response_data = response.json()
                logger.info(f"Address created successfully: {response_data}")
                return True, "Address created successfully", response_data
            
        except requests.exceptions.Timeout:
            last_exception = "Request timed out"
            if attempt < max_retries - 1:
                logger.warning(f"Timeout occurred. Retrying...")
                time.sleep(retry_delay)
                continue
                
        except requests.exceptions.ConnectionError:
            last_exception = "Connection error occurred"
            if attempt < max_retries - 1:
                logger.warning(f"Connection error. Retrying...")
                time.sleep(retry_delay)
                continue
                
        except requests.exceptions.RequestException as e:
            last_exception = str(e)
            if attempt < max_retries - 1:
                logger.warning(f"Request failed: {e}. Retrying...")
                time.sleep(retry_delay)
                continue

        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            logger.error(f"Response data for: {response.text if 'response' in locals() else 'No response'}")

            last_exception = str(e)
            if attempt < max_retries - 1:
                logger.warning(f"Request failed: {e}. Retrying...")
                time.sleep(retry_delay)
                continue
    
    # If we've exhausted all retries
    logger.error(f"Failed to create address after {max_retries} attempts")
    logger.error(f"Response data for: {response.text if 'response' in locals() else 'No response'}")
    return False, f"Failed after {max_retries} attempts. Last error: {last_exception}", None



if __name__ == "__main__":
    # Example usage
    success, message, data = restaurant_terminal_address(
        city="Lagos",
        country="NG",
        state="Lagos",
        first_name="John",
        last_name="Doe",
        phone="+2348012345678",
        line1="25 Admiralty Way"
    )
    print(success, message, data)