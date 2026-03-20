import requests
import json

SQUAD_SANDBOX_BASE_URL = "https://sandbox-api-d.squadco.com"

INITIATE_DVA_ENDPOINT = f"{SQUAD_SANDBOX_BASE_URL}/virtual-account/initiate-dynamic-virtual-account"

API_SECRET_KEY = "sandbox_sk_1446c0d02f3e20570f47a6c9297a3c149fc635c5946a"


def initiate_dynamic_virtual_account(amount, transaction_ref, duration, email):
    print("initiating dva...")

    payload = {
        "amount": amount,                # amount in kobo
        "transaction_ref": transaction_ref,
        "duration": duration,            # seconds
        "email": email
    }

    headers = {
        "Authorization": f"Bearer {API_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            INITIATE_DVA_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        print("DVA response:", data)

        return {
            "success": True,
            "data": data
        }

    except requests.exceptions.HTTPError as http_err:

        return {
            "success": False,
            "error": f"HTTP error: {http_err}",
            "response": response.text
        }

    except requests.exceptions.RequestException as req_err:

        return {
            "success": False,
            "error": f"Request error: {req_err}"
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


resp = initiate_dynamic_virtual_account(
    amount=500000,
    transaction_ref="transaction_ref_3",
    duration=600,
    email="test@email.com"
)

print(resp)