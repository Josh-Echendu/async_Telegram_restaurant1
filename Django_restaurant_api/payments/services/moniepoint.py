import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import httpx
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------


_client: Optional[httpx.Client] = None
CACHE_KEY_TOKEN = "moniepoint:access_token"

def _get_config() -> dict:
    return settings.MONIEPOINT_CONFIG

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


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _fetch_access_token() -> str:
    """Get a fresh token from Moniepoint. Returns {access_token, expires_at, jti}."""

    config = _get_config()
    url = f"{config['BASE_URL'].rstrip('/')}/v1/auth"
    payload = {
        "client_id": config["CLIENT_ID"],
        "client_secret": config["CLIENT_SECRET"]
    }

    logger.info("Moniepoint: Fetching new access token")
    response = _request_with_retry(method="POST", url=url, json=payload)
    data = response.json()

    access_token = data.get("access_token")
    expires_in = data.get("expires_in")  # in seconds

    expires_at = datetime.now() + timedelta(seconds=expires_in) if expires_in else None
    jti = data.get("jti", "")

    token_data = {
        "access_token": access_token,
        "expires_at": expires_at,
        "jti": jti
    }

    # Cache with expiry (subtract buffer so we refresh early)
    cache_ttl = expires_in - config["TOKEN_REFRESH_BUFFER"]
    cache.set(CACHE_KEY_TOKEN, token_data, timeout=max(cache_ttl, 60))  # Ensure at least 60s TTL to avoid rapid refetching on failures

    logger.info(f"Moniepoint: Token cached, expires in {expires_in}s")
    return token_data    


def _is_token_expired(token_data: dict) -> bool:
    """Check if token is expired or about to expire."""
    config = _get_config()
    buffer = config["TOKEN_REFRESH_BUFFER"]
    return datetime.now() >= token_data["expires_at"] - timedelta(seconds=buffer)


def get_token() -> str:
    """Get a valid access token (from cache or fresh)."""

    token_data = cache.get(CACHE_KEY_TOKEN)

    if token_data is None or _is_token_expired(token_data):
        logger.info("Moniepoint: No valid token in cache, fetching new one")
        token_data = _fetch_access_token()

    return token_data["access_token"]


def invalidate_token():
    """Force token refresh on next call."""
    cache.delete(CACHE_KEY_TOKEN)
    logger.info("Moniepoint: Token invalidated")


# ---------------------------------------------------------------------------
# HTTP Helpers
# ---------------------------------------------------------------------------

def _request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    """Make an HTTP request with exponential backoff retry."""
    config = _get_config()
    max_retries = config["MAX_RETRIES"]
    retry_statuses = config["RETRY_STATUSES"]
    backoff = config["RETRY_BACKOFF_FACTOR"]
    client = _get_client()

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            response = client.request(method=method, url=url, **kwargs)

            # Retry on server errors
            if response.status_code in retry_statuses and attempt < max_retries:
                wait = backoff * (2 ** attempt)
                logger.warning(
                    f"Moniepoint: Retry {attempt + 1}/{max_retries} | "
                    f"status={response.status_code} | waiting {wait:.1f}s"
                )
                time.sleep(wait)
                continue

            return response

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exception = e
            if attempt < max_retries:
                wait = backoff * (2 ** attempt)
                logger.warning(
                    f"Moniepoint: Retry {attempt + 1}/{max_retries} | "
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
                    f"Moniepoint: Retry {attempt + 1}/{max_retries} | "
                    f"error={str(e)} | waiting {wait:.1f}s"
                )
                time.sleep(wait)
            else:
                raise


    raise last_exception



# ---------------------------------------------------------------------------
# Payment Operations
# ---------------------------------------------------------------------------

def push_payment(terminal_serial: str, amount: int, merchant_reference: str, payment_method: str = "ANY",) -> dict:
    """
    Push a payment request to a POS terminal.
    
    Returns:
        {
            "accepted": bool,
            "merchant_reference": str,
            "error": str | None,
            "http_status": int | None,
        }
    """
    config = _get_config()
    url = f"{config['BASE_URL'].rstrip('/')}/v1/transactions"
    token = get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "terminalSerial": terminal_serial,
        "amount": amount,
        "merchantReference": merchant_reference,
        "transactionType": "PURCHASE",
        "paymentMethod": payment_method,
    }

    logger.info(
        f"Moniepoint: Pushing payment | "
        f"terminal={terminal_serial} "
        f"amount={amount} "
        f"ref={merchant_reference} "
        f"method={payment_method}"
    )

    try:
        response = _request_with_retry(method="POST", url=url, headers=headers, json=payload,)
        if response.status_code == 202:
            logger.info(f"Moniepoint: Payment accepted | ref={merchant_reference}")
            return {
                "accepted": True,
                "merchant_reference": merchant_reference,
                "error": None,
                "http_status": 202,
            }

        elif response.status_code == 401:
            invalidate_token()
            return {
                "accepted": False,
                "merchant_reference": merchant_reference,
                "error": "Authentication failed — token refreshed, retry",
                "http_status": 401,
            }

        elif response.status_code == 400:
            data = response.json()
            error_msg = data.get("message", "Bad request")
            logger.warning(f"Moniepoint: Bad request | ref={merchant_reference} | {error_msg}")
            return {
                "accepted": False,
                "merchant_reference": merchant_reference,
                "error": error_msg,
                "http_status": 400,
            }

        else:
            logger.error(f"Moniepoint: Unexpected status {response.status_code}")
            return {
                "accepted": False,
                "merchant_reference": merchant_reference,
                "error": f"Unexpected status: {response.status_code}",
                "http_status": response.status_code,
            }

    except httpx.TimeoutException:
        logger.error(f"Moniepoint: Timeout pushing payment | ref={merchant_reference}")
        return {
            "accepted": False,
            "merchant_reference": merchant_reference,
            "error": "Request timed out",
            "http_status": None,
        }
    except Exception as e:
        logger.exception(f"Moniepoint: Error pushing payment | ref={merchant_reference}")
        return {
            "accepted": False,
            "merchant_reference": merchant_reference,
            "error": str(e),
            "http_status": None,
        }


def get_transaction_status(merchant_reference: str) -> dict:
    """
    Poll for the outcome of a previously pushed payment.
    
    Returns:
        {
            "processing_status": str,      # PENDING, PROCESSED, CANCELLED, ERROR
            "response_code": str | None,   # "00" = success
            "response_message": str | None,
            "actual_amount": int | None,
            "actual_payment_method": str | None,
            "transaction_reference": str | None,
            "terminal_serial": str | None,
        }
    """
    config = _get_config()
    url = f"{config['BASE_URL'].rstrip('/')}/v1/transactions/merchants/{merchant_reference}"
    token = get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    logger.info(f"Moniepoint: Checking status | ref={merchant_reference}")

    try:
        response = _request_with_retry(
            method="GET",
            url=url,
            headers=headers,
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "processing_status": data["processingStatus"],
                "response_code": data.get("responseCode"),
                "response_message": data.get("responseMessage"),
                "actual_amount": data.get("actualAmount"),
                "actual_payment_method": data.get("actualPaymentMethod"),
                "transaction_reference": data.get("transactionReference"),
                "terminal_serial": data.get("terminalSerial"),
            }

        elif response.status_code == 401:
            invalidate_token()
            return {
                "processing_status": "ERROR",
                "response_code": None,
                "response_message": "Authentication failed",
                "actual_amount": None,
                "actual_payment_method": None,
                "transaction_reference": None,
                "terminal_serial": None,
            }

        elif response.status_code == 404:
            return {
                "processing_status": "ERROR",
                "response_code": None,
                "response_message": "Transaction not found",
                "actual_amount": None,
                "actual_payment_method": None,
                "transaction_reference": None,
                "terminal_serial": None,
            }

        else:
            logger.error(f"Moniepoint: Unexpected status {response.status_code}")
            return {
                "processing_status": "ERROR",
                "response_code": None,
                "response_message": f"Unexpected status: {response.status_code}",
                "actual_amount": None,
                "actual_payment_method": None,
                "transaction_reference": None,
                "terminal_serial": None,
            }

    except httpx.TimeoutException:
        logger.error(f"Moniepoint: Timeout checking status | ref={merchant_reference}")
        return {
            "processing_status": "ERROR",
            "response_code": None,
            "response_message": "Request timed out",
            "actual_amount": None,
            "actual_payment_method": None,
            "transaction_reference": None,
            "terminal_serial": None,
        }
    except Exception as e:
        logger.exception(f"Moniepoint: Error checking status | ref={merchant_reference}")
        return {
            "processing_status": "ERROR",
            "response_code": None,
            "response_message": str(e),
            "actual_amount": None,
            "actual_payment_method": None,
            "transaction_reference": None,
            "terminal_serial": None,
        }
    

def push_and_wait(terminal_serial: str, amount: int, merchant_reference: str, payment_method: str = "ANY", poll_interval: Optional[int] = None, max_attempts: Optional[int] = None,) -> dict:
    """
    Push a payment and poll until the customer pays or cancels.
    
    This blocks for up to POLL_TIMEOUT seconds.
    
    Returns the same dict structure as get_transaction_status(),
    with possible processing_status values:
        PROCESSED, CANCELLED, ERROR, TIMEOUT
    """

    config = _get_config()
    poll_interval = poll_interval or config["POLL_INTERVAL"]
    max_attempts = max_attempts or config["POLL_MAX_ATTEMPTS"]

    # Step 1: Push
    push_result = push_payment(
        terminal_serial=terminal_serial,
        amount=amount,
        merchant_reference=merchant_reference,
        payment_method=payment_method,
    )

    if not push_result["accepted"]:
        # If auth failed, retry once with fresh token
        if push_result["http_status"] == 401:
            logger.info("Moniepoint: Retrying push after token refresh")
            push_result = push_payment(
                terminal_serial=terminal_serial,
                amount=amount,
                merchant_reference=merchant_reference,
                payment_method=payment_method,
            )

        if not push_result["accepted"]:
            return {
                "processing_status": "ERROR",
                "response_code": None,
                "response_message": push_result["error"] or "Push failed",
                "actual_amount": None,
                "actual_payment_method": None,
                "transaction_reference": None,
                "terminal_serial": None,
            }

    # Step 2: Poll
    for attempt in range(1, max_attempts + 1):
        logger.info(
            f"Moniepoint: Poll attempt {attempt}/{max_attempts} | ref={merchant_reference}"
        )

        time.sleep(poll_interval)

        status = get_transaction_status(merchant_reference)

        if status["processing_status"] in ("PROCESSED", "CANCELLED", "ERROR"):
            logger.info(
                f"Moniepoint: Terminal result | "
                f"ref={merchant_reference} "
                f"status={status['processing_status']} "
                f"code={status['response_code']} "
                f"amount={status['actual_amount']}"
            )
            return status

        logger.info(f"Moniepoint: Still PENDING | ref={merchant_reference}")

    # Timed out
    logger.warning(f"Moniepoint: Polling timed out | ref={merchant_reference}")
    return {
        "processing_status": "TIMEOUT",
        "response_code": None,
        "response_message": f"Customer did not respond after {max_attempts * poll_interval}s",
        "actual_amount": None,
        "actual_payment_method": None,
        "transaction_reference": None,
        "terminal_serial": None,
    }
