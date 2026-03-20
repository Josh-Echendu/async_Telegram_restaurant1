import requests
import json
import time

SQUAD_SANDBOX_BASE_URL = "https://sandbox-api-d.squadco.com"

API_SECRET_KEY = "sandbox_sk_1446c0d02f3e20570f47a6c9297a3c149fc635c5946a"


def virtual_account_requery_transaction(transaction_ref, max_retries=5):
    print("re-querying dva transactions...")

    headers = {
        "Authorization": f"Bearer {API_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    REQUERY_TRANSACTION_ENDPOINT = f"{SQUAD_SANDBOX_BASE_URL}/virtual-account/get-dynamic-virtual-account-transactions/{transaction_ref}"

    for attempt in range(max_retries):
        try:
            response = requests.get(
                REQUERY_TRANSACTION_ENDPOINT,
                headers=headers,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            if data.get("success"):
                print()
                print("data....: ", data['data']['rows'])
                return {
                    "success": True,
                    "requery_data": data["data"]['rows']
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



# @shared_task(bind=True, soft_time_limit=200, max_retries=None)
# def handle_retry_query_external_api(self, merchant_reference):
#     try:
#         missed_webhook = prefetch_webhooks(merchant_reference)
#         payload = missed_webhook.get('payload')
#         status = payload.get('transaction_status').lower()
#         session = CheckoutSession.objects.select_for_update().filter(merchant_reference=merchant_reference).first()

#         if not session:
#             return
        
#         if status == "success":
#             logger.info(f"{merchant_reference} success")
#             handle_success(session, payload)
        
#         if status == 'expired':
#             logger.info(f"{merchant_reference} expired")
#             handle_expired(session, payload)

#         if status == 'mismatch':
#             logger.info(f"{merchant_reference} mismatch")
#             handle_mismatch(session, payload)

#     except SoftTimeLimitExceeded:
#         logger.warning(f"Soft time limit exceeded to handle requery for merchant_reference: {merchant_reference}, retrying...")
#         raise self.retry(exc=SoftTimeLimitExceeded(), countdown=1)

#     except Exception as exc:
#         logger.error(f"Failed to handle requery for merchant_reference : {merchant_reference}: {exc}")
#         raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 3600))





