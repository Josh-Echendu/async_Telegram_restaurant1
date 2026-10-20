
from WHATSAPP_BOT_API.services.restaurant_cache import get_restaurant
from WHATSAPP_BOT_API.core.config import *
import math
from WHATSAPP_BOT_API.core.config import _request_with_retry





async def checkout(client, btn):
    user_id = btn.from_user.wa_id

    user_session = await get_user_session(user_id)

    business_type = (
        user_session.get("business_type") or ""
    ).lower()

    service_mode = (
        user_session.get("service_mode") or ""
    ).lower()

    # ========== CHECKOUT ACCESS ==========
    if service_mode not in ["dine_in", "both"]:
        logger.warning(
            "User %s tried Checkout/Pay in mode: %s",
            user_id,
            service_mode,
        )

        await btn.reply(
            "❌ *Checkout Not Available*\n\n"
            "This option is only available for:\n"
            "• Restaurant Dine-in\n"
            "• Hotel Dine-in\n"
            "• Both services"
        )
        return

    # ========== FETCH ORDER BATCHES ==========
    result = await api_get_user_order_batches(btn)

    if not result or not result.get("ok"):

        # Recoverable failure — retry through ARQ
        if result and result.get("recoverable"):
            raise Exception(
                "Fetching order batches failed. Will retry: "
                f"{result.get('error', 'Unknown error')}"
            )

        error_msg = (
            result.get("error", "Unable to load your orders")
            if result
            else "Unable to load your orders"
        )

        # No active session
        if result and result.get("session_id") is None:
            await btn.reply(
                "❌ *No Active Session Found*\n\n"
                "🛒 You don't have an active order session.\n"
                "🍽️ Please add some items to your cart first."
            )
            return

        logger.error(
            "Could not load bill for WhatsApp user %s: %s",
            user_id,
            error_msg,
        )

        await btn.reply(
            "⚠️ *Could Not Load Your Bill*\n\n"
            "Please try again shortly. Thank you."
        )
        return

    data = result["data"]
    batches = data.get("batches", [])

    if not batches:
        await btn.reply(
            "🛒 *No Active Orders*\n\n"
            "You haven't placed any orders yet."
        )
        return

    # ========== BUILD BILL SUMMARY ==========
    dine_session = data.get("dine_session") or {}
    host = data.get("host") or {}
    participants = data.get("participants", [])
    declined_participants = data.get("declined_participants", [])

    table_number = dine_session.get("table_number", "—")

    restaurant_name = (
        user_session.get("restaurant_name") or "Restaurant"
    )

    customer_name = (
        getattr(btn.from_user, "name", None)
        or getattr(btn.from_user, "first_name", None)
        or "Guest"
    )

    # Totals from API
    subtotal = float(data.get("subtotal", 0))

    vat_amount = math.ceil(subtotal * 0.075)
    grand_total = math.ceil(subtotal + vat_amount)

    # ========== FORMAT EACH BATCH ==========
    batch_lines = []

    for batch in batches:
        is_host = batch.get("is_host", False)
        user_label = batch.get("user_first_name", "Guest")
        host_marker = "👑" if is_host else "👤"

        batch_lines.append(
            f"{host_marker} *{user_label}* · "
            f"_Batch: #{batch['bid']}_"
        )

        for item in batch.get("items", []):
            qty = item["quantity"]
            title = item["product_title"]
            line_total = item.get(
                "multiply_price",
                float(item["quantity"]) * float(item["price"]),
            )

            batch_lines.append(
                f"    • {qty}× {title} — ₦{float(line_total):,.0f}"
            )

        batch_lines.append(
            f"    *Subtotal:* ₦{float(batch['total_price']):,.0f}"
        )

        batch_lines.append("")

    # ========== PARTICIPANTS SUMMARY ==========
    people_count = 1 + len(participants)

    people_line = f"👥 *{people_count}* at table"

    if declined_participants:
        people_line += (
            f" · ⚠️ {len(declined_participants)} declined"
        )

    # ========== FINAL BILL ==========
    summary = (
        f"🧾 *BILL — TABLE {table_number}*\n"
        f"_{restaurant_name}_\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"

        f"👤 Customer: _{customer_name}_\n"
        f"{people_line}\n"
        f"🍽️ Batches: *{len(batches)}*\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "*ORDER BREAKDOWN*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"

        + "\n".join(batch_lines)

        + "\n━━━━━━━━━━━━━━━━━━━━\n"
        "*BILL SUMMARY*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Subtotal: ₦{subtotal:,.0f}\n"
        f"VAT (7.5%): ₦{vat_amount:,.0f}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"*GRAND TOTAL: ₦{grand_total:,.0f}*\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    await btn.reply(summary)

    # ========== PAYMENT PROMPT ==========
    await btn.reply(
        text="💰 *Choose your payment method:*",
        buttons=await payment_keyboard(),
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
    platform = "whatsapp"

    # Get WhatsApp user and restaurant session
    user_id = btn.from_user.wa_id

    try:
        user_session = await get_user_session(user_id)
        restaurant_id = user_session.get("current_rid")

        raw = await redis_client.get(
            f"whatsapp_dine_user_session:{restaurant_id}:{user_id}"
        )

        session_data = json.loads(raw) if raw else {}
        session_id = session_data.get("session_id")

        # Use restaurant_id from session data if available
        restaurant_id = session_data.get("restaurant_id") or restaurant_id

    except Exception:
        logger.exception(
            "Failed to retrieve WhatsApp dine-in session for user=%s",
            user_id,
        )
        session_id = None
        restaurant_id = None

    # No session — permanent failure
    if not session_id:
        return {
            "ok": False,
            "recoverable": False,
            "error": "No active order session. Please add some items to your cart first.",
            "session_id": None,
        }

    if not restaurant_id:
        return {
            "ok": False,
            "recoverable": False,
            "error": "No restaurant associated with the active session.",
            "restaurant_id": None,
        }

    url = (
        f"http://web:8000/api/user_batch_list/"
        f"{session_id}/{restaurant_id}/{platform}/"
    )

    response, success = await _request_with_retry(
        method="GET",
        url=url,
        headers={
            "Content-Type": "application/json",
            "X-INTERNAL-API-KEY": INTERNAL_API_KEY,
        },
        timeout=30.0,
    )

    # Network / 5xx failure — recoverable
    if not success or response is None:
        return {
            "ok": False,
            "recoverable": True,
            "error": "Network error",
        }

    # Parse response body
    try:
        data = response.json()
    except Exception:
        data = {}

    # Success
    if 200 <= response.status_code < 300:
        return {
            "ok": True,
            "recoverable": False,
            "data": data,
        }

    # Session not found
    if data.get("found") is False:
        return {
            "ok": False,
            "recoverable": False,
            "session_id": None,
            "error": data.get(
                "message",
                data.get("error", "Session not found"),
            ),
        }

    # 400 — bad request
    if response.status_code == 400:
        return {
            "ok": False,
            "recoverable": False,
            "error": data.get("error", "Bad request"),
        }

    # Other 4xx — permanent failure
    if 400 <= response.status_code < 500:
        return {
            "ok": False,
            "recoverable": False,
            "error": data.get(
                "error",
                f"API returned {response.status_code}",
            ),
        }

    # Unexpected status — recoverable
    return {
        "ok": False,
        "recoverable": True,
        "error": f"Unexpected status {response.status_code}",
    }


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
            await redis_client.get(f"whatsapp_dine_user_session:{restaurant_id}:{user_id}")
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

    user_session = await get_user_session(user_id)
    restaurant_id = user_session.get("current_rid")

    redis_key = f"whatsapp_dine_user_session:{restaurant_id}:{user_id}"
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