# services/drf_client.py

import httpx

DRF_URL = "https://08a7-185-132-132-106.ngrok-free.app"

async def send_order(data):
    async with httpx.AsyncClient() as client:
        return await client.post(f"{DRF_URL}/api/orders/", json=data)