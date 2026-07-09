from WHATSAPP_BOT_API.core.config import *


HTTP_CONFIG = {
    "REQUEST_TIMEOUT": 15,

    # Retry config
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


async def _request_with_retry(
    method: str,
    url: str,
    process: str,
    **kwargs,
):
    """
    Make an HTTP request with exponential backoff retry.
    Returns the 'data' field from the JSON response.
    """

    config = await _get_config()

    max_retries = config["MAX_RETRIES"]
    backoff = config["RETRY_BACKOFF_FACTOR"]

    client = await _get_client()

    last_exception = None

    for attempt in range(max_retries + 1):

        try:
            response = await client.request(
                method=method,
                url=url,
                **kwargs,
            )

            response.raise_for_status()

            data = response.json()

            logger.info(
                "API request for %s succeeded: %s",
                process,
                data,
            )
            return data.get("data")

        except Exception as e:
            last_exception = e

            if attempt < max_retries:

                wait = backoff * (2 ** attempt)

                logger.warning(
                    "Process %s | Retry %s/%s | Error: %s | Waiting %.1fs",
                    process,
                    attempt + 1,
                    max_retries,
                    e,
                    wait,
                )

                await asyncio.sleep(wait)

            else:
                logger.exception(
                    "Process %s failed after %s retries.",
                    process,
                    max_retries,
                )
                raise

    raise last_exception