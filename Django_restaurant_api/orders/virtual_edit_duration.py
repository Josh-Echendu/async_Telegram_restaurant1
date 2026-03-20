import requests
import json
import time

SQUAD_SANDBOX_BASE_URL = "https://sandbox-api-d.squadco.com"

EDIT_AMOUNT_DURATION_ENDPOINT = f"{SQUAD_SANDBOX_BASE_URL}/virtual-account/update-dynamic-virtual-account-time-and-amount"

API_SECRET_KEY = "sandbox_sk_1446c0d02f3e20570f47a6c9297a3c149fc635c5946a"

# make sure u update this field after updating virtual account duration and amount
# session.va_expiry = timezone.now() + timedelta(seconds=3600)
# session.save(update_fields=["va_expiry", "total_price"])

def virtual_account_edit_amount_duration(new_amount, transaction_ref, new_duration, max_retries=3):
    print("editing dva duration and amount...")

    payload = {
        "amount": new_amount,
        "transaction_ref": transaction_ref,
        "duration": new_duration,
    }

    headers = {
        "Authorization": f"Bearer {API_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    for attempt in range(max_retries):
        try:
            response = requests.patch(
                EDIT_AMOUNT_DURATION_ENDPOINT,
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

