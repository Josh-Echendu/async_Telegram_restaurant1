import time
import logging
from datetime import datetime, timedelta
from typing import Optional

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

def _fetch_access_token() -> dict:
    """Get a fresh token from Moniepoint. Caches it with expiry buffer."""

    config = _get_config()
    url = f"{config['BASE_URL'].rstrip('/')}/v1/auth"
    payload = {
        "client_id": config["CLIENT_ID"],
        "client_secret": config["CLIENT_SECRET"],
    }

    logger.info("Moniepoint: Fetching new access token")
    response = _request_with_retry(method="POST", url=url, json=payload)
    data = response.json()

    access_token = data.get("access_token")
    expires_in = data.get("expires_in")

    expires_at = datetime.now() + timedelta(seconds=expires_in) if expires_in else None
    jti = data.get("jti", "")

    token_data = {
        "access_token": access_token,
        "expires_at": expires_at,
        "jti": jti,
    }

    cache_ttl = expires_in - config["TOKEN_REFRESH_BUFFER"]
    cache.set(CACHE_KEY_TOKEN, token_data, timeout=max(cache_ttl, 60))

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

def moniepoint_push_payment(
    terminal_serial: str,
    amount: int,
    merchant_reference: str,
    payment_method: str = "ANY",
) -> dict:
    """
    Push a payment request to a POS terminal.
    The actual result comes later via webhook.

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
        response = _request_with_retry(
            method="POST",
            url=url,
            headers=headers,
            json=payload,
        )

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
    

# ---------------------------------------------------------------------------
# Moniepoint Re-query Transaction
# ---------------------------------------------------------------------------

def _moniepoint_requery_transaction(transaction_reference: str) -> dict:
    """Re-query a transaction by its reference number."""
    pass