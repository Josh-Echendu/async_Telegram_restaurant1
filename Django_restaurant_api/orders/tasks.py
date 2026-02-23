from decimal import Decimal

from httpx import Response, request
from celery import shared_task
from celery.signals import worker_ready
from django.conf import settings
from django.db.models import Q
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from .models import KITCHEN_STATUS_CHOICES, OrderBatch
from .redis_client import redis_client
from django.db import transaction



TOKEN = settings.TELEGRAM_BOT_TOKEN
KITCHEN_ID = settings.KITCHEN_CHAT_ID

import logging
logger = logging.getLogger(__name__)

# -----------------------------------------
# 1️⃣ Retry unsent notifications on worker start
# -----------------------------------------
@worker_ready.connect # @worker_ready.connect → run when Celery worker starts
def at_start(sender, **kwargs):
    """Runs immediately when Celery worker starts."""
    retry_unsent_notifications.delay()


@shared_task
def retry_unsent_notifications():
    """
    Find orders that haven't been sent to kitchen or user,
    and queue them for notification.
    """
    unsent_orders = OrderBatch.objects.filter(
        Q(notified_kitchen=False) | Q(notified_user=False)
    ).only("bid", "telegram_user__telegram_id")

    for order in unsent_orders:
        send_order_notifications.delay(order.bid, order.telegram_user.telegram_id)


# -----------------------------------------
# 2️⃣ Main Celery task (FULL TRY/EXCEPT)
# -----------------------------------------

# | Setting         | Meaning                                   |
# | --------------- | ------------------------------------------|
# | autoretry_for=(Exception,) | 🔹 autoretry_for=(Exception,)  |
# | `max_retries=5`            | Try again up to 5 times         |
# | `countdown=3`              | Wait 3 seconds between retries |

@shared_task(bind=True)
def send_order_notifications(self, order_bid, telegram_id):
    """
    Sends messages to kitchen and user.
    Retries automatically.
    Only notifies user after FINAL failure.
    """

    try:
        with transaction.atomic():

            order = OrderBatch.objects.select_for_update().get(bid=order_bid)

            if order.notified_kitchen and order.notified_user:
                return  # already done

            _send_order_notifications(order, telegram_id)

    except OrderBatch.DoesNotExist:
        # ❌ Order no longer exists → nothing to retry → exit task
        return

    except Exception as exc:

        # “If we haven’t retried 5 times yet, raise a retry and wait 3 seconds before trying again.”
        if self.request.retries < 5:
            print(f"Retrying order {order_bid} ({self.request.retries + 1}/5)...")
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
            send_to_kitchen_for_celery(order, KITCHEN_ID)
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
def send_to_kitchen_for_celery(order, kitchen_id):
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
            InlineKeyboardButton("⏳🔄 Processing", callback_data=f"processing_{order.bid}"),
        ]
    ]

    bot.send_message(
        chat_id=kitchen_id,
        text=kitchen_text,
        reply_markup=InlineKeyboardMarkup(kitchen_keyboard)
    )

def send_user_message_for_celery(order, telegram_id):
    bot = Bot(token=TOKEN)

    key = f"user:{telegram_id}:removed_items:{order.bid}"
    lock = redis_client.set(key, "sent", nx=True, ex=120)

    if not lock:
        logger.warning(f"Duplicate message prevented for batch {order.bid}")
        return

    removed_items = order.removed_cart_items
    if removed_items:
        item_list = "\n".join(removed_items)
        sorry_message = (
            "😔 Sorry! The following item(s) are out of stock and were removed from your cart:\n\n"
            f"{item_list}\n\n"
            "Sorry for the inconvenience 😔"
        )
        bot.send_message(chat_id=telegram_id, text=sorry_message)

    keyboard = [
        [InlineKeyboardButton("➕ Add More Items", callback_data="order_more_items"),
         InlineKeyboardButton("💳 Pay Now", callback_data="pay_now")],
        [InlineKeyboardButton("📉📈📶📦 Track Orders", callback_data="track_orders")]
    ]

    # send main order message / summary only once
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
    if removed_items:
        bot.send_message(chat_id=telegram_id, text=summary)

    bot.send_message(
        chat_id=telegram_id,
        text="🍽️ Order sent to the kitchen! 🎉🎉🎉\n\nWhat would you like to do next?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def _notify_user_of_failure(telegram_id):
    bot = Bot(token=TOKEN)
    bot.send_message(
        chat_id=telegram_id,
        text="😔 Sorry your order couldn't be sent to the kitchen.\n\n Please click 🛍️✅💳 Checkout/Pay menu below 👇👇!!"
    )

    
# def send_user_message_for_celery(order, telegram_id):
#     bot = Bot(token=TOKEN)

#     removed_items = order.removed_cart_items

#     if removed_items:
#         _remove_items(order, telegram_id, removed_items)

#     keyboard = [
#         [InlineKeyboardButton("➕ Add More Items", callback_data="order_more_items"),
#          InlineKeyboardButton("💳 Pay Now", callback_data="pay_now")],
#         [InlineKeyboardButton("📉📈📶📦 Track Orders", callback_data="track_orders")]
#     ]

#     msg = bot.send_message(
#         chat_id=telegram_id,
#         text="🍽️ Order sent to the kitchen! 🎉🎉🎉\n\nWhat would you like to do next?",
#         reply_markup=InlineKeyboardMarkup(keyboard)
#     )
#     redis_client.set(f"user:{telegram_id}:send_to_kitchen_id", msg.message_id)
#     redis_client.get(f"user:{telegram_id}:send_to_kitchen_id")





# def _remove_items(order, telegram_id, removed_items):

#     key = f"user:{telegram_id}:removed_items:{order.bid}"

#     # ✅ ATOMIC LOCK (critical fix)
#     lock = redis_client.set(key, "sent", nx=True, ex=120)

#     if not lock:
#         logger.warning(
#             f"Duplicate remove message prevented for batch {order.bid}"
#         )
#         return

#     bot = Bot(token=TOKEN)

#     item_list = "\n".join(removed_items)

#     sorry_message = (
#         "😔 Sorry! The following item(s) are out of stock and were removed from your cart:\n\n"
#         f"{item_list}\n\n"
#         "Sorry for the inconvenience 😔"
#     )

#     lines = []
#     total_price = sum(item.price * item.quantity for item in order.items.all())

#     for item in order.items.all():
#         subtotal = Decimal(item.price) * item.quantity
#         lines.append(f"{item.quantity}X - {item.product.title} - ₦{subtotal:,}")

#     summary = (
#         "🧾 *Your New Order Summary*\n\n"
#         + "\n".join(lines)
#         + f"\n\n——————————\n*Total: ₦{total_price:,}*"
#     )

#     bot.send_message(chat_id=telegram_id, text=sorry_message)
#     bot.send_message(chat_id=telegram_id, text=summary)


# # orders/tasks.py
# from celery import shared_task
# from celery.signals import worker_ready
# from django.conf import settings
# from django.db.models import Q
# from .models import OrderBatch
# from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
# from celery.exceptions import MaxRetriesExceededError


# # Telegram bot settings
# TOKEN = settings.TELEGRAM_BOT_TOKEN
# KITCHEN_ID = settings.KITCHEN_CHAT_ID


# # -----------------------------------------
# # 1️⃣ Retry unsent notifications on worker start
# # -----------------------------------------
# @worker_ready.connect # @worker_ready.connect → run when Celery worker starts
# def at_start(sender, **kwargs):
#     """Runs immediately when Celery worker starts."""
#     retry_unsent_notifications.delay()


# @shared_task
# def retry_unsent_notifications():
#     """
#     Find orders that haven't been sent to kitchen or user,
#     and queue them for notification.
#     """
#     unsent_orders = OrderBatch.objects.filter(
#         Q(notified_kitchen=False) | Q(notified_user=False)
#     )

#     for order in unsent_orders:
#         send_order_notifications.delay(order.bid, order.telegram_user.telegram_id)


# # -----------------------------------------
# # 2️⃣ Main Celery task
# # -----------------------------------------

# # | Setting         | Meaning                                   |
# # | --------------- | ------------------------------------------|
# # | autoretry_for=(Exception,) | 🔹 autoretry_for=(Exception,)  |
# # | `max_retries=5`            | Try again up to 5 times         |
# # | `countdown=3`              | Wait 3 seconds between retries |

# @shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 5, "countdown": 3})
# def send_order_notifications(self, order_bid, telegram_id, removed_items=None):
#     """
#     Sends messages to kitchen and user for a given order.
#     Retries automatically. Only notifies user after FINAL failure.
#     """
#     try:
#         order = OrderBatch.objects.get(bid=order_bid)
#         _send_order_notifications(order, telegram_id)

#     except OrderBatch.DoesNotExist:
#         return  # order was deleted, nothing to do

#     except MaxRetriesExceededError:
#         _notify_user_of_failure(telegram_id)
#         return 

#     except Exception:
#         raise  # IMPORTANT: let Celery retry


# @send_order_notifications.on_failure
# def _notify_user_of_failure(telegram_id):
#     bot = Bot(token=TOKEN)
#     bot.send_message(chat_id=telegram_id, text="😔 Sorry your order couldn't be sent to the kitchen.\n\n Please click 🛍️✅💳 Checkout/Pay menu below 👇👇!!")


# # -----------------------------------------
# # 3️⃣ Sync helper
# # -----------------------------------------
# def _send_order_notifications(order, telegram_id):
#     """
#     Sync function to send messages to kitchen and user.
#     Updates DB flags after each successful send.
#     """
#     if not order.notified_kitchen:
#         send_to_kitchen_for_celery(order, KITCHEN_ID)
#         order.notified_kitchen = True
#         order.save(update_fields=["notified_kitchen"])

#     if not order.notified_user:
#         send_user_message_for_celery(order, telegram_id)
#         order.notified_user = True
#         order.save(update_fields=["notified_user"])


# # -----------------------------------------
# # 4️⃣ Telegram helpers (SYNC)
# # -----------------------------------------
# def send_to_kitchen_for_celery(order, kitchen_id):
#     """
#     Sends a Telegram message to the kitchen about a new order.
#     """
#     bot = Bot(token=TOKEN)

#     lines = [
#         f"{item.quantity}X - {item.product.title} - ₦{item.price * item.quantity}"
#         for item in order.items.all()
#     ]
#     total = sum(item.price * item.quantity for item in order.items.all())

#     kitchen_text = (
#         f"🔥 NEW ORDER RECEIVED\n\n"
#         f"👤 Customer: {order.telegram_user.first_name}\n"
#         f"🆔 User ID: {order.telegram_user.telegram_id}\n\n"
#         f"📦 Items:\n" + "\n".join(lines) +
#         f"\n\n——————————\n*Total: ₦{total}*\n\n"
#         "⏳ Status: Pending"
#     )

#     kitchen_keyboard = [
#         [
#             InlineKeyboardButton("⏳🔄 Processing", callback_data=f"processing_{order.bid}"),
#             InlineKeyboardButton("📦✅ Delivered", callback_data=f"delivered_{order.bid}"),
#         ]
#     ]

#     bot.send_message(
#         chat_id=kitchen_id,
#         text=kitchen_text,
#         reply_markup=InlineKeyboardMarkup(kitchen_keyboard)
#     )


# def send_user_message_for_celery(order, telegram_id):
#     """
#     Sends a Telegram message to the user confirming their order.
#     """
#     bot = Bot(token=TOKEN)

#     # lines = [
#     #     f"{item.quantity}X - {item.product.title} - ₦{item.price * item.quantity}"
#     #     for item in order.items.all()
#     # ]
#     # total = sum(item.price * item.quantity for item in order.items.all())

#     # user_text = (
#     #     f"🍽️ Your order has been sent to the kitchen!🎉🎉🎉\n\nWhat would you like to do next?\n\n"
#     #     f"🧾 Order Summary:\n" + "\n".join(lines) +
#     #     f"\n\n——————————\n*Total: ₦{total}*"
#     # )

#     keyboard = [
#         [InlineKeyboardButton("➕ Add More Items", callback_data="order_more_items"),
#          InlineKeyboardButton("💳 Pay Now", callback_data="pay_now")],
#         [InlineKeyboardButton("📉📈📶📦 Track Orders", callback_data="track_orders")]
#     ]

#     bot.send_message(
#         chat_id=telegram_id,
#         text="🍽️ Order sent to the kitchen! 🎉🎉🎉\n\nWhat would you like to do next?",
#         reply_markup=InlineKeyboardMarkup(keyboard)
#     )
    
