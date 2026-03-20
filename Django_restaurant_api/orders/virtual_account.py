import requests
import json
import time

SQUAD_SANDBOX_BASE_URL = "https://sandbox-api-d.squadco.com"

INITIATE_DVA_ENDPOINT = f"{SQUAD_SANDBOX_BASE_URL}/virtual-account/initiate-dynamic-virtual-account"

API_SECRET_KEY = "sandbox_sk_1446c0d02f3e20570f47a6c9297a3c149fc635c5946a"


def initiate_dynamic_virtual_account(amount, merchant_reference, duration, email, max_retries=5):
    print("initiating dva...")

    payload = {
        "amount": amount,
        "transaction_ref": merchant_reference,
        "duration": duration,
        "email": email
    }

    headers = {
        "Authorization": f"Bearer {API_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                INITIATE_DVA_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            if data.get("success"):
                return {
                    "success": True,
                    "data": data["data"]
                }
            else:
                return {
                    "success": False,
                    "error": data.get("message", "Unknown error")
                }

        except requests.exceptions.HTTPError as http_err:

            # retry only on server errors
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"Server error, retrying in {wait}s...")
                time.sleep(wait)
                continue

            return {
                "success": False,
                "error": f"HTTP error: {http_err}",
                "response": response.text
            }

        except requests.exceptions.RequestException as req_err:

            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"Request failed, retrying in {wait}s...")
                time.sleep(wait)
                continue

            return {
                "success": False,
                "error": f"Request error after retries: {req_err}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    return {
        "success": False,
        "error": "Max retries exceeded"
    }


# resp = initiate_dynamic_virtual_account(
#     amount=500000,
#     transaction_ref="transaction_ref_1",
#     duration=600,
#     email="test@email.com"
# )

# print(resp)