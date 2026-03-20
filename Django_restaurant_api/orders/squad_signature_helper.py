import json
import hmac
import hashlib

SQUAD_SECRET_KEY = "sandbox_sk_1446c0d02f3e20570f47a6c9297a3c149fc635c5946a"


def verify_squad_signature(payload, received_signature):

    data = {
        "transaction_reference": payload.get("transaction_reference"),
        "amount_received": payload.get("amount_received"),
        "merchant_reference": payload.get("merchant_reference"),
    }

    json_string = json.dumps(data, separators=(",", ":"))

    generated_hash = hmac.new(
        SQUAD_SECRET_KEY.encode(),
        json_string.encode(),
        hashlib.sha512
    ).hexdigest()

    return hmac.compare_digest(generated_hash, received_signature)