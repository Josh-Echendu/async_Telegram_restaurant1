# payments/services/vpay.py

import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_client: Optional[httpx.Client] = None


def _get_config() -> dict:
    return settings.VPAY_CONFIG


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        config = _get_config()
        _client = httpx.Client(timeout=config["REQUEST_TIMEOUT"])
    return _client


def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None


def invalidate_access_token():
    config = _get_config()
    cache.delete(config["ACCESS_TOKEN_CACHE_KEY"])

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _get_access_token() -> str:
    """Get a cached VPay access token or fetch a new one."""
    config = _get_config()
    cache_key = config["ACCESS_TOKEN_CACHE_KEY"]
    
    token = cache.get(cache_key)
    if token:
        logger.debug("VPay: Using cached access token")
        return token

    logger.info("VPay: Fetching new access token")
    
    url = f"{config['BASE_URL'].rstrip('/')}/api/service/v1/query/merchant/login"
    headers = {
        "Content-Type": "application/json",
        "publicKey": config["PUBLIC_KEY"],
    }
    body = {
        "username": config["USERNAME"],
        "password": config["PASSWORD"],
    }

    response = _request_with_retry(method="POST", url=url, headers=headers, json=body)
    data = response.json()
    print("auth data: ", data)
    logger.info("auth data: ", data)
    access_token = data.get("token")

    if not access_token:
        raise Exception(f"VPay login failed: {data}")

    cache.set(cache_key, access_token, timeout=None)  # Keep until 401 forces refresh
    logger.info(f"VPay: Access token cached for vpay amount of seconds")
    
    return access_token


# ---------------------------------------------------------------------------
# HTTP Helpers
# ---------------------------------------------------------------------------

def _request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    config = _get_config()
    max_retries = config["MAX_RETRIES"]
    retry_statuses = config["RETRY_STATUSES"]
    backoff = config["RETRY_BACKOFF_FACTOR"]
    client = _get_client()

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            response = client.request(method=method, url=url, **kwargs)

            if response.status_code in retry_statuses and attempt < max_retries:
                wait = backoff * (2 ** attempt)
                logger.warning(
                    f"VPay: Retry {attempt + 1}/{max_retries} | "
                    f"status={response.status_code} | waiting {wait:.1f}s"
                    f"body={response.text[:500]}"
                )
                time.sleep(wait)
                continue

            return response

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exception = e
            if attempt < max_retries:
                wait = backoff * (2 ** attempt)
                logger.warning(
                    f"VPay: Retry {attempt + 1}/{max_retries} | "
                    f"error={str(e)} | waiting {wait:.1f}s"
                )
                time.sleep(wait)
            else:
                raise

        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                wait = backoff * (2 ** attempt)
                logger.warning(
                    f"VPay: Retry {attempt + 1}/{max_retries} | "
                    f"error={str(e)} | waiting {wait:.1f}s"
                )
                time.sleep(wait)
            else:
                raise

    raise last_exception



# ---------------------------------------------------------------------------
# Vpay Re-query Transaction
# ---------------------------------------------------------------------------
def _vpay_requery_transaction(transaction_reference: str) -> dict:
    """
    Re-query a transaction by its reference number.
    
    Uses POST /api/v1/webintegration/query-transaction
    
    Returns:
        {
            "success": bool,
            "payment_status": str | None,     # "paid", "unpaid", etc.
            "transaction_ref": str,
            "payment_method": str | None,     # "bank", "card", etc.
            "amount": int | None,             # in kobo
            "reversed": bool,
            "raw_response": dict,
            "error": str | None,
        }
    """
    config = _get_config()
    base_url = config["BASE_URL"].rstrip("/")
    public_key = config["PUBLIC_KEY"]

    logger.info(f"VPay: Re-querying transaction | ref={transaction_reference}")

    try:
        access_token = _get_access_token()

        url = f"{base_url}/api/v1/webintegration/query-transaction"
        logger.info(f"Re-query url: {url}")

        headers = {
            "Content-Type": "application/json",
            "publicKey": public_key,
            "b-access-token": access_token,
        }

        body = {
            "transactionRef": transaction_reference,
        }

        logger.info(f"Re-query headers: {headers}")
        logger.info(f"Re-query body: {body}")

        response = _request_with_retry(method="POST", url=url, headers=headers, json=body)
        logger.info(f"Re-query response status: {response.status_code}")
        logger.info(f"Re-query response body: {response.text}")

        # Handle 401 - token expired
        if response.status_code == 401:
            logger.warning(f"VPay: Token expired, refreshing | ref={transaction_reference}")
            invalidate_access_token()
            access_token = _get_access_token()
            headers["b-access-token"] = access_token
            response = _request_with_retry(method="POST", url=url, headers=headers, json=body)
            logger.info(f"Re-query retry response: {response.text}")

        data = response.json()
        logger.info(f"VPay Re-query parsed response: {data}")

        # New response format: { "data": { "paymentstatus": "...", ... } }
        transaction_data = data.get("data", data)

        return {
            "success": True,
            "payment_status": transaction_data.get("paymentstatus"),
            "transaction_ref": transaction_data.get("transactionref"),
            "payment_method": transaction_data.get("paymentmethod"),
            "amount": transaction_data.get("orderamount"),
            "reversed": transaction_data.get("reversed", False),
            "raw_response": data,
            "error": None,
        }

    except httpx.TimeoutException:
        logger.error(f"VPay: Timeout during re-query | ref={transaction_reference}")
        return {
            "success": False,
            "payment_status": None,
            "transaction_ref": transaction_reference,
            "payment_method": None,
            "amount": None,
            "reversed": False,
            "raw_response": {},
            "error": "Timeout",
        }
    except Exception as e:
        logger.exception(f"VPay: Error during re-query | ref={transaction_reference}")
        return {
            "success": False,
            "payment_status": None,
            "transaction_ref": transaction_reference,
            "payment_method": None,
            "amount": None,
            "reversed": False,
            "raw_response": {},
            "error": str(e),
        }