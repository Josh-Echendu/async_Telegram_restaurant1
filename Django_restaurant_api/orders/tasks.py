from decimal import Decimal
from httpx import Response, request
from celery import shared_task, group
from celery.signals import worker_ready
from django.conf import settings
from django.db.models import Q
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from .models import KITCHEN_STATUS_CHOICES, OrderBatch, CheckoutSession
from .redis_client import redis_client
from django.db import transaction
from dateutil import parser
from django.utils import timezone
from django.db.transaction import on_commit
import uuid
from celery.exceptions import SoftTimeLimitExceeded

from .virtual_account import initiate_dynamic_virtual_account
from .errors import prefetch_webhooks, delete_webhook
from .virtual_edit_duration import virtual_account_edit_amount_duration

from django.db.models import OuterRef, Subquery, Sum, Value, F



TOKEN = settings.TELEGRAM_BOT_TOKEN
bot = Bot(token=TOKEN)


import logging
logger = logging.getLogger(__name__)

# -----------------------------------------
# 1️⃣ Retry unsent notifications on worker start
# -----------------------------------------
@worker_ready.connect # @worker_ready.connect → run when Celery worker starts
def at_start(sender, **kwargs):
    """Runs immediately when Celery worker starts."""
    retry_unsent_orders_notifications.delay()
    retry_unsent_payment_notifications.delay()
    requery_transaction.delay()


# ---------------------------
# Main retry task: pushes tasks in bulk
# ---------------------------
@shared_task(bind=True, max_retries=10)
def retry_unsent_payment_notifications(self):
    try:
        # Fetch all pending sessions
        pending_sessions = CheckoutSession.objects.filter(
            payment_status="paid",
            notification_sent=False
        ).only('id')

        if not pending_sessions.exists():
            logger.info("No pending sessions to retry.")
            return

        # Create a group of tasks for all pending sessions
        tasks_group = group(send_receipt_safe.s(session.id) for session in pending_sessions)

        # Push all tasks to the broker at once
        tasks_group.apply_async()
        logger.info(f"Pushed {pending_sessions.count()} send_receipt_safe tasks to workers.")

    except Exception as exc:
        # This handles errors pushing tasks to the broker
        logger.error(f"Failed to push send_receipt_safe tasks: {exc}")
        if self.request.retries < 10:
            raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 60))
        

@shared_task
def retry_unsent_orders_notifications():
    """
    Find orders that haven't been sent to kitchen or user,
    and queue them for notification.
    """
    unsent_orders = OrderBatch.objects.filter(
        Q(notified_kitchen=False) | Q(notified_user=False)
    ).only("bid", "telegram_user__telegram_id")

    for order in unsent_orders:
        send_order_notifications.delay(order.restaurant.rid, order.bid, order.telegram_user.telegram_id)


# -----------------------------------------
# 2️⃣ Main Celery task (FULL TRY/EXCEPT)
# -----------------------------------------

# | Setting         | Meaning                                   |
# | --------------- | ------------------------------------------|
# | autoretry_for=(Exception,) | 🔹 autoretry_for=(Exception,)  |
# | `max_retries=5`            | Try again up to 5 times         |
# | `countdown=3`              | Wait 3 seconds between retries |

@shared_task(bind=True)
def send_order_notifications(self, rid, order_bid, telegram_id):
    """
    Sends messages to kitchen and user.
    Retries automatically.
    Only notifies user after FINAL failure.
    """

    try:
        with transaction.atomic():

            order = OrderBatch.objects.select_for_update().get(bid=order_bid, restaurant__rid=rid)

            if order.notified_kitchen and order.notified_user:
                return  # already done

            _send_order_notifications(order, telegram_id)

    except OrderBatch.DoesNotExist:
        # ❌ Order no longer exists → nothing to retry → exit task
        return

    except Exception as exc:

        # “If we haven’t retried 5 times yet, raise a retry and wait 3 seconds before trying again.”
        if self.request.retries < 5:
            print(f"Retrying order {order_bid} for ({self.request.retries + 1}/5)...")
            raise self.retry(exc=exc, countdown=3)
        
        print(f"Final failure for order {order_bid}")
        _notify_user_of_failure(telegram_id)


# -----------------------------------------
# 4️⃣ Sync helper
# -----------------------------------------
def _send_order_notifications(order, telegram_id):
    """
    Sync function to send messages to kitchen and user.
    Updates DB flags after each successful send.
    """

    if not order.notified_kitchen:
        try:
            send_to_kitchen_for_celery(order)
            order.notified_kitchen = True
            order.save(update_fields=["notified_kitchen"])
        except Exception:
            raise

    if not order.notified_user:
        try:
            send_user_message_for_celery(order, telegram_id)
            order.notified_user = True
            order.save(update_fields=["notified_user"])
        except Exception:
            raise


# -----------------------------------------
# 5️⃣ Telegram helpers
# -----------------------------------------
def send_to_kitchen_for_celery(order):
    bot = Bot(token=TOKEN)

    lines = [
        f"{item.quantity}X - {item.product.title} - ₦{item.price * item.quantity}"
        for item in order.items.all()
    ]
    total = sum(item.price * item.quantity for item in order.items.all())

    kitchen_text = (
        f"🔥 NEW ORDER RECEIVED\n\n"
        f"👤 Customer: {order.telegram_user.first_name}\n"
        f"🆔 User ID: {order.telegram_user.telegram_id}\n\n"
        f"🆔 BATCH ID: {order.bid}\n\n"
        f"📦 Items:\n" + "\n".join(lines) +
        f"\n\n——————————\n*Total: ₦{total}*\n\n"
        "⏳ Status: Pending"
    )

    kitchen_keyboard = [
        [
            InlineKeyboardButton("⏳🔄 Processing", callback_data=f"processing_{order.bid}_{order.restaurant.rid}"),
        ]
    ]

    bot.send_message(
        chat_id=order.restaurant.kitchen_chat_id,
        text=kitchen_text,
        reply_markup=InlineKeyboardMarkup(kitchen_keyboard)
    )

def send_user_message_for_celery(order, telegram_id):
    bot = Bot(token=TOKEN)
    lines = []
    total_price = sum(item.price * item.quantity for item in order.items.all())
    for item in order.items.all():
        subtotal = Decimal(item.price) * item.quantity
        lines.append(f"{item.quantity}X - {item.product.title} - ₦{subtotal:,}")
    
    summary = (
        "🧾 *Your New Order Summary*\n\n"
        + "\n".join(lines)
        + f"\n\n——————————\n*Total: ₦{total_price:,}*"
    )

    bot.send_message(
        chat_id=telegram_id,
        text=summary,
    )

    bot.send_message(
        chat_id=telegram_id,
        text="🍽️ Order sent to the kitchen! 🎉🎉🎉\n\nWhat would you like to do next?",
        reply_markup=None
    )

def _notify_user_of_failure(telegram_id):
    bot = Bot(token=TOKEN)
    bot.send_message(
        chat_id=telegram_id,
        text="😔 Sorry your order couldn't be sent to the kitchen.\n\n Please click 🛍️✅💳 Checkout/Pay menu below 👇👇!!"
    )


@shared_task(bind=True, soft_time_limit=200, max_retries=10)
def process_squad_webhook(self, payload):
    print("Processing webhook:", payload)

    # convert transaction status to lowercase
    status = payload.get("transaction_status", "").lower()
    print("testing status....: ", status)
    merchant_ref = payload.get("merchant_reference")

    try:
        session = CheckoutSession.objects.filter(
            merchant_reference=merchant_ref
        ).only("id").first()

        if not session:
            logger.warning("Session not found for %s", merchant_ref)
            return
        
        if session.payment_status == "paid":
            logger.info("Amount already processed %s and %s ", session.payment_status, session.amount_received)
            # handle_success(session, payload)
            return

        handlers = {
            "success": handle_success,
            "mismatch": handle_mismatch,
            "expired": handle_expired,
        }

        loggings = {
            "success": lambda: logger.info("Payment successful for %s", merchant_ref),
            "mismatch": lambda: logger.info("Payment mismatch for %s", merchant_ref),
            "expired": lambda: logger.info("Payment expired for %s", merchant_ref),
        }

        handler = handlers.get(status)

        if not handler:
            logger.warning("Unknown status %s", status)
            return
        
        loggings.get(status, lambda: None)()
        handler(session.id, payload)

    except SoftTimeLimitExceeded:
        logger.warning(f"Soft time limit exceeded for merchant_ref {merchant_ref}, retrying...")
        raise self.retry(exc=SoftTimeLimitExceeded(), countdown=1)

    except Exception as exc:

        logger.error(f"Failed to send receipt for merchant_ref {merchant_ref} for ({self.request.retries + 1}...: {exc}")
        if self.request.retries >= 10:
            logger.error(f"Max retries reached for {session.id}")
            return
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 3600))
    

    
def handle_success(session_id, payload):

    with transaction.atomic():
        session = CheckoutSession.objects.select_for_update().filter(id=session_id).first()   
        
        if not session:
            logger.info("no session in handle_success for session_id: %s", session_id)
            return 
        
        if session.payment_status == "paid":
            logger.info("already paid for merchant_reference : %s......", payload.get("merchant_reference"))
            return

        amount_received = int(Decimal(payload.get("amount_received", "0")))
        
        if amount_received != session.expected_amount:
            merchant_ref = payload.get("merchant_reference")

            logger.warning("Amount mismatch: %s vs %s merchant_ref: %s", amount_received, session.expected_amount, merchant_ref)
            return 
        
        paid_date = parser.isoparse(payload.get("date"))

        session.payment_status = "paid"
        session.amount_received = amount_received
        session.paid_at = paid_date
        session.is_active = False
        session.payment_in_progress = False
        session.webhook_payload = payload
        session.save()
        logger.info("saved payment status for merchant_refrence %s as PAID: ",  session.merchant_reference)

        # 9️⃣ Where You Should Use on_commit()
        # Use on_commit() whenever you do external actions after database updates.
        # on_commit() means: “Run this function only after the database transaction successfully saves to the database.”
        on_commit(lambda: send_receipt_safe.delay(session.id)) # The lambda (function) won’t run until the transaction is fully committed.
        return


def handle_expired(session_id, payload=None):
    with transaction.atomic():
        
        session = CheckoutSession.objects.select_for_update().filter(id=session_id).first()    
        
        if not session:
            logger.info("no session in handle_success for session_id: %s", session_id)
            return 
        
        if session.payment_status == "paid":
            logger.info("already paid for merchant_reference : %s......", payload.get("merchant_reference"))
            return
        
        key = f"{uuid.uuid4().hex}"
        merchant_reference = f"REF-{key}-{session.telegram_user.telegram_id}"
        
        response = initiate_dynamic_virtual_account(
            amount=int(session.expected_amount * 100),
            merchant_reference=merchant_reference,
            duration=1800,
            email='echendujosh@gmail.com'
        )
        
        if response.get("success"):
            virtual_account_data = response.get('data')

            # parse Squad's expires_at string into datetime
            expires_at = parser.isoparse(virtual_account_data['expires_at'])  # parser.isoparse(result['expires_at']) converts that string into a Python datetime object.

            session.expected_amount = int(Decimal(virtual_account_data['expected_amount']))
            session.merchant_reference = virtual_account_data['transaction_reference']
            session.va_acct_number = virtual_account_data['account_number']
            session.va_bank = virtual_account_data['bank']
            session.va_expiry = expires_at
            session.payment_in_progress = True
            session.save() 

            on_commit(lambda: send_account_details_to_user(session, virtual_account_data))

        return

def handle_mismatch(session_id, payload):

    with transaction.atomic():

        session = CheckoutSession.objects.select_for_update().filter(id=session_id).first()    

        if not session:
            logger.info("no session in handle_success for session_id: %s", session_id)
            return 
        
        if session.payment_status == "paid":
            logger.info("already paid for merchant_reference : %s......", payload.get("merchant_reference"))
            return
        
        if session.va_expiry and session.va_expiry < timezone.now():
            handle_expired(session, payload)
            return

        on_commit(lambda: mismatch_message.delay(session.telegram_user.telegram_id))


@shared_task(bind=True, soft_time_limit=200, max_retries=10)
def mismatch_message(self, telegram_id):
    try:
        bot.send_message(
            chat_id=telegram_id,
            text="⚠️ Payment amount mismatch. Your transfer was reversed. Try repaying"
        )
    
    except SoftTimeLimitExceeded:
        logger.warning(f"Soft time limit exceeded for session {telegram_id}, retrying...")
        raise self.retry(exc=SoftTimeLimitExceeded(), countdown=1)

    except Exception as exc:
        logger.error(f"Telegram send failed {telegram_id}: {exc}")
        if self.request.retries >= 10:
            logger.error(f"Max retries reached for telegram {telegram_id}")
            return
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 3600))


# ---------------------------
# Worker task: handles sending receipt
# ---------------------------
@shared_task(bind=True, soft_time_limit=200, max_retries=10)
def send_receipt_safe(self, session_id):
    try:
        session = CheckoutSession.objects.get(id=session_id)

        # Idempotency: only send if not already sent
        if session.notification_sent:
            return

        # Send receipt
        send_receipt_to_user(session)

        # Mark as sent
        session.notification_sent = True
        session.save(update_fields=["notification_sent"])
    
    except CheckoutSession.DoesNotExist:
        return

    except SoftTimeLimitExceeded:
        logger.warning(f"Soft time limit exceeded for session {session_id}, retrying...")
        raise self.retry(exc=SoftTimeLimitExceeded(), countdown=1)

    except Exception as exc:
        logger.error(f"Failed to send receipt for session {session_id}: {exc}")
        if self.request.retries >= 10:
            logger.error(f"Max retries reached for {session_id}")
            return
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 3600))


def send_receipt_to_user(session):
    photo_url = "/app/orders/photo_2026-01-09 14.59.50.jpeg"

    with open(photo_url, "rb") as photo:
        input_file = InputFile(photo)

        bot.send_photo(
            chat_id=session.telegram_user.telegram_id,
            caption="🎉 Your payment has been received! Thank you for choosing our service! 🍽️😊",
            photo=input_file
        )

def send_account_details_to_user(session, virtual_account_data):

    # Define the new buttons you want to show
    keyboard = [
            [InlineKeyboardButton("Back ⬅️", callback_data='back_to_payment_menu')]
        ]

    bank = virtual_account_data.get('bank')
    bank_account_name = virtual_account_data.get('account_name') or "FORKCO"
    bank_account_number = virtual_account_data.get('account_number')

    account_info = (
        f"🏦 Bank: <b>{bank}</b>\n\n"
        f"🔢 Account Number: <code>{bank_account_number}</code>\n\n"
        f"👤 Account Name: <b>{bank_account_name}</b>"
    )

    try:
        bot.send_message(
            chat_id=session.telegram_user.telegram_id,
            text=f"⚠️ <b>Account number Expired. Your transfer was reversed.</b>\n\n"
                f"📝 <b>Account Details</b>\n\n"
                f"Please make your payment to the following account:\n\n"
                f"{account_info}\n\n"
                f"💡 Tap and hold the account number to copy.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Telegram send failed: %s", e)


@shared_task(bind=True, soft_time_limit=200, max_retries=10)
def requery_transaction(self):
    try:    
        pending_sessions = CheckoutSession.objects.filter(
            is_active=True,
            webhook_payload__isnull=True
        ).only('merchant_reference')

        if not pending_sessions:
            logger.info("No pending sessions to re-query...")
            return
        
        
        # Create a group of tasks for all pending sessions
        tasks_group = group(handle_retry_query_external_api.s(session.merchant_reference) for session in pending_sessions)

        # Push all tasks to the broker at once
        tasks_group.apply_async()
        logger.info(f"Pushed {(pending_sessions.count())} handle_retry_query_external_api tasks to workers.")

    except Exception as exc:
        # This handles errors pushing tasks to the broker
        logger.error(f"Failed to push send_receipt_safe tasks: {exc}")
        if self.request.retries < 10:
            raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 60))
        

@shared_task(bind=True, soft_time_limit=200, max_retries=10)
def handle_retry_query_external_api(self, merchant_reference):
    if not merchant_reference:
        return 
    
    missed_webhook = prefetch_webhooks(merchant_reference)
    
    if not missed_webhook:
        logger.info("No webhook found for %s", merchant_reference)
        return

    payload = missed_webhook.get("payload", {})
    
    status = payload.get('transaction_status').lower()
    transaction_ref = missed_webhook.get("transaction_ref")

    try:
        with transaction.atomic():
            session_id = CheckoutSession.objects.select_for_update().filter(merchant_reference=merchant_reference).only('id').first()
            
            if not session_id:
                return
            
            if status == "success":
                logger.info(f"{merchant_reference} success")
                handle_success(session_id, payload)
            
            if status == 'expired':
                logger.info(f"{merchant_reference} expired")
                handle_expired(session_id, payload)

            if status == 'mismatch':
                logger.info(f"{merchant_reference} mismatch")
                handle_mismatch(session_id, payload)


    except SoftTimeLimitExceeded:
        logger.warning(f"Soft time limit exceeded to handle requery for merchant_reference: {merchant_reference}, retrying...")
        raise self.retry(exc=SoftTimeLimitExceeded(), countdown=1)

    except Exception as exc:
        logger.error(f"Failed to handle requery for merchant_reference : {merchant_reference}: {exc}")
        if self.request.retries >= 10:
            logger.error(f"Max retries reached for {merchant_reference}")
            return
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 3600))

    finally:
        if payload:
            delete_webhook(transaction_ref)


@shared_task(bind=True, soft_time_limit=200, max_retries=10)
def edit_amount_duration(self, session_id):
    
    try:
        session = CheckoutSession.objects.filter(id=session_id).prefetch_related('session_batches')

        logger.info("session already exist for %s: ", session.merchant_reference)
        order_batches = session.session_batches.all()
        vat = int(100)

        total = int(order_batches.aggregate(total_price=Sum('total_price'))['total_price'] or 0) + vat

        total_price = int(total * 100)
        print("total_price: ", total_price)
        virtual_account_edit_amount_duration(new_amount=total_price, transaction_ref=session.merchant_reference)

    except SoftTimeLimitExceeded:
        logger.warning(f"Soft time limit exceeded to handle editing of amount and duration for merchant_reference: {session.merchant_reference}, retrying...")
        raise self.retry(exc=SoftTimeLimitExceeded(), countdown=1)

    except Exception as exc:
        logger.error(f"Failed to handle editing of amount and duration for merchant_reference : {session.merchant_reference}: {exc}")
        if self.request.retries >= 10:
            logger.error(f"Max retries reached for {session.merchant_reference}")
            return
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 3600))
 

# @shared_task(bind=True, soft_time_limit=200, max_retries=None)
# def handle_retry_query_external_api(self, merchant_reference):
#     try:
#         requery_response = virtual_account_requery_transaction(merchant_reference)
        
#         if not requery_response.get('success'):
#             return
        
#         rows = requery_response.get('requery_data', [])

#         # next(): "This means give me the FIRST item from that filtered list or None"
#         success_txn = next( 
#             (txn for txn in rows if txn['transaction_status'].lower() == "success"),  # "Go through rows and pick only SUCCESS ones"
#             None
#         )
#         if success_txn:
#             pass

#         # x = one item in rows, so we are looping through rows and compare the created_at which is bigger and extract the full dictionary row
#         latest_txn = max(rows, key=lambda x: x['created_at']) # You get the full dictionary back, not just the date.
#         status = latest_txn['transaction_status'].lower()
        
#         if status == "expired":
#             logger.info(f"{merchant_reference} expired")
#             pass
#         if status == "mismatch":
#             logger.info(f"{merchant_reference} mismatch")
#             mismatch_message
#             pass

#     except SoftTimeLimitExceeded:
#         logger.warning(f"Soft time limit exceeded to handle requery for merchant_reference: {merchant_reference}, retrying...")
#         raise self.retry(exc=SoftTimeLimitExceeded(), countdown=1)

#     except Exception as exc:
#         logger.error(f"Failed to handle requery for merchant_reference : {merchant_reference}: {exc}")
#         raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 3600))





