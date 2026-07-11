import httpx
import asyncio
from .logger_config import logger

_client = None

HTTP_CONFIG = {
    "REQUEST_TIMEOUT": 15,
    "MAX_RETRIES": 3,
    "RETRY_BACKOFF_FACTOR": 0.5,
}


async def _get_config() -> dict:
    return HTTP_CONFIG


async def _get_client() -> httpx.AsyncClient:
    global _client
    
    if _client is None:
        config = await _get_config()
        _client = httpx.AsyncClient(
            timeout=config["REQUEST_TIMEOUT"]
        )
    
    return _client


async def close_client():
    global _client
    
    if _client is not None:
        await _client.aclose()
        _client = None


async def _request_with_retry(method: str, url: str, **kwargs):
    """
    Make an HTTP request with exponential backoff retry.
    Returns the Response object.
    """
    
    config = await _get_config()
    max_retries = config["MAX_RETRIES"]
    backoff = config["RETRY_BACKOFF_FACTOR"]
    
    client = await _get_client()
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            response = await client.request(method=method, url=url, **kwargs)
            response.raise_for_status()
            
            logger.info(
                "API request to %s succeeded (attempt %d/%d)",
                url,
                attempt + 1,
                max_retries + 1
            )
            return response, True
            
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries:
                wait = backoff * (2 ** attempt)
                logger.warning(
                    "Request to %s failed (attempt %d/%d): %s. Retrying in %.1fs",
                    url,
                    attempt + 1,
                    max_retries + 1,
                    str(e),
                    wait
                )
                await asyncio.sleep(wait)
            else:
                logger.exception(
                    "Request to %s failed after %d attempts.",
                    url,
                    max_retries + 1
                )
                return None, False
