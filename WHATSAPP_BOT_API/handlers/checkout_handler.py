
from WHATSAPP_BOT_API.services.restaurant_cache import get_restaurant
from WHATSAPP_BOT_API.core.config import *
import math



async def checkout(client, btn):
    user_session = await get_user_session(btn.from_user.wa_id)

    service_mode = (user_session.get("service_mode") or "").lower()

    # ✅ Check if user is allowed to checkout (postpay only)
    if service_mode in ["dine_in", "both"]:

        lines = []
        grand_total = 0

        order_batches = await api_get_user_order_batches(btn)

        if not order_batches:
            await btn.reply("You have no active orders.")
            return

        restaurant_name = order_batches[0]["restaurant"] if order_batches else "Unknown"

        for order in order_batches:
            lines.append(f"🆔 BATCH ID: *_{order['bid']}_*")

            for item in order["items"]:
                qty = int(item["quantity"])
                price = int(item["price"])
                title = item["product_title"]

                subtotal = qty * price

                lines.append(f"_{qty}x {title} - ₦{subtotal:,}_")

            grand_total += int(order["total_price"])
            lines.append("")

        vat = math.ceil(grand_total * 0.075)   # Integer
        final_total = math.ceil(grand_total + vat)    # Integer

        summary = (
            "🧾 *Your Order Summary*\n\n"
            f"Restaurant 📜🍽️🍷: _{restaurant_name}_\n"
            f"👤 Customer: _{btn.from_user.name}_\n\n"
            + "\n".join(lines)
            + f"\n\nTotal Price: ₦{grand_total:,}"
            + f"\nVAT Charges (7.5%): ₦{vat:,}"
            + "\n——————————"
            + f"\n*Grand Total: ₦{final_total:,}*"
        )

        await btn.reply(summary)

        await btn.reply(
            text="💰 *Choose your payment method:*",
            buttons=await payment_keyboard()
        )

    else:
        await btn.reply(
            "❌ You are not allowed to use the Checkout/Pay button.\n\n"
            "This option is only available for:\n"
            "• Restaurant Dine-in\n"
            "• Both services"
        )



async def payment_keyboard():

    buttons = [
        Button(
            title="💵 Cash",
            callback_data="pay_cash",
        ),
        Button(
            title="🏦 Bank Transfer",
            callback_data="bank_transfer",
        ),
        Button(
            title="💳 POS",
            callback_data="pay_pos",
        ),
    ]

    return buttons



async def api_get_user_order_batches(btn, max_retries=3):

    user_id = btn.from_user.wa_id
    user_session = await get_user_session(user_id)
    platform = "whatsapp"

    # 🔍 Get session_id from Redis
    try:    
        session_data = json.loads(
            await redis_client.get(f"whatsapp_dine_user_session:{user_id}")
        )
        logger.info(f"handle session data: {session_data}")
        session_id = session_data.get("session_id")
        restaurant_id = session_data.get('restaurant_id')

    except Exception:
        session_id = None

    if not session_id:
        await btn.reply(
            "❌ *No Active Session Found*\n\n"
            "🛒 You don't have an active order session.\n"
            "🍽️ Please add some items to your cart first."
        )
        return None

    
    url = (
        f"http://web:8000/api/user_batch_list/"
        f"{session_id}/{restaurant_id}/{platform}/"
    )

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers={"Content-Type": "application/json", "X-INTERNAL-API-KEY": INTERNAL_API_KEY})

                resp.raise_for_status()
                data = resp.json()

                if resp.status_code in (200, 201):
                    return data

                logger.warning(f"Unexpected response {resp.status_code} → {data}")
                return None

        except httpx.HTTPStatusError as e:

            if e.response.status_code == 404:
                try:
                    data = e.response.json()

                    if not data.get("found", True):
                        await btn.reply(data.get("message", "You have no active session. Please order some items."))
                        return None

                except ValueError:
                    logger.exception("Invalid JSON returned for 404 response")
                    return None

            logger.warning(f"Attempt {attempt} failed: {e}")

        except (httpx.RequestError, ValueError, Exception) as e:
            logger.exception(f"Attempt {attempt} failed: {e}")

        if attempt < max_retries:
            await asyncio.sleep(1)

    logger.error(
        f"All {max_retries} attempts failed to get order batches from DB."
    )

    return None



async def handle_pos_cash_payment(btn, payment_type, max_retries=3):
    """
    Handles POS or Cash payment selection by the customer.
    """
    user_id = btn.from_user.wa_id

    user_session = await get_user_session(user_id)
    restaurant_id = user_session.get("current_rid")

    logger.info(f"🏪 Restaurant ID: {restaurant_id}")
    logger.info(f"💳 Payment Type: {payment_type}")

    # 🔍 Get session_id from Redis
    try:
        
        session_data = json.loads(
            await redis_client.get(f"whatsapp_dine_user_session:{user_id}")
        )
        logger.info(f"handle session data for handle_pos_cash_payment: {session_data}")
        session_id = session_data.get("session_id")
    except Exception:
        session_id = None

    if not session_id:
        await btn.reply(
            "❌ *No Active Session Found*\n\n"
            "🛒 You don't have an active order session.\n"
            "🍽️ Please add some items to your cart first."
        )
        return None

    payload = {
        "session_id": session_id,
        "payment_type": payment_type,
    }

    url = "http://web:8000/payments/api/handle-payment-selection/"

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )

                resp.raise_for_status()

                data = resp.json()

                return data.get("data")

        except Exception as e:
            logger.info(f"⚠️ Attempt {attempt} failed: {e}")

            if attempt == max_retries:
                await btn.reply(
                    "❌ *Payment Request Failed*\n\n"
                    "We couldn't process your payment request.\n"
                    "🔄 Please try again or contact support."
                )
                return None

        if attempt < max_retries:
            await asyncio.sleep(1)

    return None


async def bank_transfer(client, btn):
    
    user_id = btn.from_user.wa_id

    redis_key = f"whatsapp_dine_user_session:{user_id}"
    session_data = await redis_client.get(redis_key)

    if not session_data:
        await btn.reply(
            "❌ No active order found.\n\n"
            "Please start a new order."
        )
        return

    session_data = json.loads(session_data)

    session_id = session_data["session_id"]
    restaurant_id = session_data["restaurant_id"]
    platform = session_data["platform"]

    payment_url = (
        f"{NGROK_DJANGO}/payments/"
        f"{restaurant_id}/{platform}/{session_id}"
    )

    await btn.reply(
        text=(
            "💳 *Bank/Card Transfer*\n\n"
            "Tap the secure payment link below to complete your payment.\n\n"
            f"{payment_url}\n\n"
            "⚠️ *Important Security Notice*\n"
            "• Do NOT share this payment link with anyone.\n"
            "• It is linked to your current order session.\n"
            "• Anyone with this link may be able to access your payment session while it is still active.\n"
            "• If you accidentally share it, please contact the restaurant immediately."
        ),
        preview_url=True,
    )