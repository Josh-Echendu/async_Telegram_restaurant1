from config import *


def generate_session_id() -> str:
    """Generate unique session ID for tracking"""
    return f"telegram_setup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"


def get_headers() -> Dict[Any, str]:
    """Get headers for FastAPI-userbot requests"""
    
    return {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, Exception))
)

async def make_api_request(
    method: str,
    endpoint: str,
    data: Optional[Dict] = None,
    timeout: int = CONFIG["TIMEOUT_SECONDS"]
) -> Dict[str, Any]:
    """
    Make HTTP request to FastAPI-userbot with retries
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint path
        data: Request payload
        timeout: Request timeout in seconds
    
    Returns:
        API response as dictionary
    
    Raises:
        Exception: If API call fails after retries
    """
    url = f"{CONFIG['FASTAPI_USERBOT_URL']}{endpoint}"
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, headers=get_headers(), params=data)
            elif method.upper() == "POST":
                response = await client.post(url, headers=get_headers(), json=data)
            elif method.upper() == "PUT":
                response = await client.put(url, headers=get_headers(), json=data)
            elif method.upper() == "DELETE":
                response = await client.delete(url, headers=get_headers(), json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            logger.info(f"response data for endpoint={endpoint}: {response.json()}")
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise
        except Exception as e:
            logger.error(f"API request failed: {e}")
            raise
