import requests
import json

SQUAD_SANDBOX_BASE_URL = "https://sandbox-api-d.squadco.com"
CREATE_DVA_ENDPOINT = f"{SQUAD_SANDBOX_BASE_URL}/virtual-account/create-dynamic-virtual-account"
API_SECRET_KEY = "sandbox_sk_1446c0d02f3e20570f47a6c9297a3c149fc635c5946a"

def create_dynamic_virtual_account(first_name=None, last_name=None, beneficiary_account=None):
    """
    Functional API client to create a Dynamic Virtual Account in Sandbox
    """
    payload = {}
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if beneficiary_account:
        payload["beneficiary_account"] = beneficiary_account

    headers = {
        "Authorization": f"Bearer {API_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(CREATE_DVA_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()  # Raises HTTPError for 4xx/5xx

        data = response.json()
        return {"success": True, "data": data}

    except requests.exceptions.HTTPError as http_err:
        return {"success": False, "error": f"HTTP error: {http_err}", "response": response.text}
    except requests.exceptions.RequestException as req_err:
        return {"success": False, "error": f"Request exception: {req_err}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    
print(create_dynamic_virtual_account())