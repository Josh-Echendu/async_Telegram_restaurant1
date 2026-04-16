from email.policy import default
import json

from django.db import models
from shortuuid.django_fields import ShortUUIDField
from django.utils.html import mark_safe
from decimal import Decimal
import uuid
from userAuths.models import TelegramUser
from encrypted_model_fields.fields import EncryptedCharField
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .services import register_telegram_webhook, delete_webhook
from django.conf import settings
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator



# To differentiate between dine-in and remote users in a Telegram bot without QR codes, use Telegram’s native "Share Location" feature to check proximity, require table number entry, or use deep-linking via Wi-Fi/NFC for automatic detection. These methods ensure accurate order routing to kitchen (dine-in) or delivery systems. 
# Landbot
# Landbot
#  +2
# Here are the best methods to differentiate without QR codes:
# Telegram Location Sharing (Geofencing): Prompt the user to "Share Location" within the bot. If the coordinates are within a predefined radius of the restaurant (e.g., 50 meters), tag them as "Dine-In".
# Table Number/Passcode Entry: Upon starting the bot, immediately ask the user to enter a table number or a dynamic, frequently changing code displayed in the restaurant. Without this, they are defaulted to "Remote".
# Telegram Web App with Geolocation API: If your bot uses a Mini App (embedded web page), use the browser's Geolocation API to check if the user is on-site before loading the menu.
# Unique URL/Deep-linking: Create a specific link (e.g., t.me/RestaurantBot?start=table1) and place it on physical table signs, a NFC tap-point, or a Wi-Fi captive portal page. Users who use this link are automatically recognized as diners. 
# BistroStack
# BistroStack
#  +4
# Dine-In vs. Remote Workflow Example:
# Start: User initiates the bot.
# Detection: Bot asks: "Are you here?"
# Yes: Triggers "Share Location" or asks for Table #. -> Dine-in Menu/Service.
# No: Defaults to delivery/pickup. -> Delivery Menu.
# Order Processing: If dine-in, require a table number to submit the order. 
# BistroStack
# BistroStack
#  +1



FAST_API_URL = settings.NGROK_FAST_API
ALPHABET = "abcdefghijklmnopqrstuvwxyz123456789"

def resturant_image_path(instance, filename):
    resturant_name = instance.name if instance.name else "uncategorized"
    return f"Restaurants Images/{resturant_name}/{filename}"
    
# class Table(models.Model):
#     restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
#     table_number = models.CharField(max_length=10)
#     is_active = models.BooleanField(default=True)

SERVICE_MODE_CHOICES = (
    ('dine_in', 'In-Restaurant Only'),
    ('delivery', 'Delivery Only'),
    ('both', 'Dine-in & Delivery'),
)

BUSINESS_TYPE = (
    ("restaurant", "Restaurant"),
    ("vendor", "Vendor"),
)


class Restaurant(models.Model):
    rid = ShortUUIDField(unique=True, prefix='res', length=10, max_length=20, alphabet=ALPHABET, db_index=True)
    name = models.CharField(max_length=250)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to=resturant_image_path, blank=True, null=True)
    
    # @my_restaurant_bot
    bot_username = models.CharField(max_length=100, blank=True, null=True)
    bot_token = EncryptedCharField(max_length=255, null=True)
    webhook_secret_token = models.CharField(
            max_length=255, 
            default=uuid.uuid4, 
            help_text="X-Telegram-Bot-Api-Secret-Token", 
            null=True, 
            blank=True
        )    
    is_bot_active = models.BooleanField(default=True, db_index=True)
    
    # Real-world use cases: Restaurant closed, Kitchen busy, Maintenance mode, 👉 Think of it as a “restaurant open/closed” switch.
    # if not restaurant.is_accepting_orders:
    #     await update.message.reply_text("Sorry, we are not accepting orders right now.")
    #     return
    is_accepting_orders = models.BooleanField(default=True)
    
    # ✅ add this field
    kitchen_chat_id = models.BigIntegerField(null=True,blank=True,help_text="Telegram kitchen group chat ID")
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    # Delivery support fields
    delivery_chat_id = models.BigIntegerField(null=True, blank=True, help_text="Telegram delivery group chat ID (if supports_delivery is True)")
    service_mode = models.CharField(max_length=20, choices=SERVICE_MODE_CHOICES, help_text="Primary service mode of the business", db_index=True)
    max_tables = models.PositiveSmallIntegerField(default=0, help_text="Amount of tables a restaurant has for dine-in orders")
    
    # “How long does food usually take before it is ready?”
    average_preparation_time = models.PositiveIntegerField(default=30, help_text="Minutes")
    delivery_fee = models.DecimalField(max_digits=1000, decimal_places=2, default=0)

    # restaurant → cooks meals for immediate consumption(dine-in) or instant-delivery
    # vendor → handles preorders / flexible delivery / non-restaurant items
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE, help_text="Type of business: Restaurant or Vendor", db_index=True)

    # | Feature         | Restaurant   | Food Vendor     |
    # | --------------- | ------------ | -----------     |
    # | Cooking speed   | Immediate    | Delayed         |
    # | Orders/delivery |  Instant     | instant/Preorder|
    # | Dining          | Yes/optional | No              |
    # | Scheduling      | Not needed   | Required        |

    # | Type       | Dine-in | Instant | Delayed | Scheduling |
    # | ---------- | -------  | ------- | ------- | ---------- |
    # | Restaurant | ✅      | ✅       | ❌       | ❌    |
    # | Vendor     | ❌      | ✅       | ✅       | ✅     


    def save(self, *args, **kwargs):
        if self.business_type == "vendor":
            self.max_tables = 0

            # Only override if wrong
            if self.service_mode != "delivery":
                self.service_mode = "delivery"

        elif self.business_type == "restaurant":
            if not self.service_mode:
                raise ValidationError("Restaurant must choose a service mode")
            
        elif self.business_type == "vendor":
            if not self.service_mode:
                raise ValidationError("Vendor must choose a service mode")
            
        super().save(*args, **kwargs)

    def clean(self):
        if self.kitchen_chat_id and not str(self.kitchen_chat_id).startswith("-"):
            raise ValidationError("Kitchen chat ID must be a group ID (negative number)")

    def get_bot_token(self):
        return self.bot_token  # decrypted automatically
    
    def get_webhook_url(self):
        return f"{FAST_API_URL}/webhook/{self.rid}"

    def restaurant_image(self):
        if self.image:
            return mark_safe(f'<img src="{self.image.url}" width="50" height="50" />')
        return "No Image"

    def __str__(self):
        return self.name
 
# 🧠 YOUR FINAL DESIGN (CLEAN & CORRECT)
# 🟢 RESTAURANT

# 👉 Focus: instant / same-day service

# Modes:
# Dine-in only
# serve immediately in restaurant 🍽️
# no delivery
# Delivery only
# instant / same-day delivery 🚚
# no scheduling
# Hybrid (both)
# dine-in + instant delivery

# 👉 ❌ No delayed orders
# 👉 ❌ No scheduling

# 🔵 VENDOR

# 👉 Focus: flexible delivery (instant + delayed)

# delivery only 🚚
# supports:
# instant
# delayed (24h, 48h…)
# scheduled delivery

# 👉 ❌ No dine-in

class RestaurantDeliveryOpeningHours(models.Model):
    restaurant = models.ForeignKey(Restaurant, db_index=True, on_delete=models.CASCADE, related_name='delivery_opening_hours')
    # service_type = models.CharField()
    day_of_week = models.IntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(6)
        ]
    )
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)


    def clean(self):
        if not self.is_closed:
            if not self.open_time or not self.close_time:
                raise ValidationError("Open and close time required if not closed")

            if self.open_time >= self.close_time:
                raise ValidationError("Open time must be before close time")


class RestaurantMembership(models.Model):
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='users')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='restaurants')

    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        # one user per resturant
        unique_together = ('user', 'restaurant')

    # ASK YOURSELF WHO OWNS WHO FIRST

    # 🧠 FINAL ANSWER (VERY CLEAR)
    #     TelegramUser → independent entity
    #     Restaurant → independent entity
    #     PaymentSession → dependent entity

    #     So:

    #     PaymentSession belongs to BOTH TelegramUser and Restaurant


    #     Step 2 — Cardinality
    # One user → how many restaurants?

    # 👉 MANY
    # (user can order from multiple restaurants)

    # One restaurant → how many users?

    # 👉 MANY
    # (many customers)

@receiver(post_save, sender=Restaurant)
def manage_restaurant_webhook(sender, instance, created, **kwargs):
    """
    Handles both Creation and Updates.
    """
    if created:
        # Scenario: New Restaurant created with an active bot
        if instance.is_bot_active and instance.bot_token:
            register_telegram_webhook(instance)
    else:
        # Scenario: Update to existing Restaurant
        # We trigger the webhook setup if the bot is active. 
        # Telegram's setWebhook is idempotent, so calling it again 
        # just refreshes the configuration.
        if instance.is_bot_active and instance.bot_token:
            register_telegram_webhook(instance)
        # else:
        #     # If bot was deactivated during update, clean up the webhook
        #     delete_webhook(instance)

@receiver(post_delete, sender=Restaurant)
def remove_restaurant_webhook(sender, instance, **kwargs):
    """
    Handles Deletion.
    """
    if instance.bot_token:
        delete_webhook(instance)


# 💬 IF YOU WANT NEXT

# I can upgrade this to:

# 🔥 Redis caching for tokens (no DB hit per request)
# 🔥 Rate limiting per bot
# 🔥 Background processing with Celery
# 🔥 Nginx + HTTPS production setup
# 🔥 Token encryption best practice (you already started this)



# 🔥 Redis (instead of in-memory cache)
# 🔥 Horizontal scaling (multiple FastAPI workers)
# 🔥 Queue-based processing (Celery)
# 🔥 Auto bot warm-up (no cold start lag)




# Good question — this is where your system starts feeling like a *real product*, not just backend logic. Let’s make it very simple and practical.

# ---

# # 🧠 First: What the database stores vs what the dashboard shows

# You must separate two things:

# ## 🟡 DATABASE (backend)

# Stores:

# ```python
# day_of_week = 0,1,2,3,4,5,6
# ```

# ## 🟢 DASHBOARD (frontend)

# Shows:

# ```text
# Monday, Tuesday, Wednesday...
# ```

# 👉 The restaurant owner NEVER sees numbers.

# ---

# # 🍽️ So how does it look in a real dashboard?

# Imagine a page like this:

# ## 📅 “Delivery Schedule Settings”

# ### Monday

# * ⭕ Open time: [09:00]
# * ⭕ Close time: [17:00]
# * ☑ Closed toggle

# ---

# ### Tuesday

# * ⭕ Open time: [09:00]
# * ⭕ Close time: [17:00]
# * ☑ Closed toggle

# ---

# ### Sunday

# * ⭕ Open time: [12:00]
# * ⭕ Close time: [20:00]
# * ☑ Closed toggle

# ---

# # 🧠 How frontend converts Integer → Day name

# In your frontend (React / HTML / Django template), you map numbers like this:

# ```javascript id="daymap1"
# const DAYS = {
#   0: "Monday",
#   1: "Tuesday",
#   2: "Wednesday",
#   3: "Thursday",
#   4: "Friday",
#   5: "Saturday",
#   6: "Sunday"
# };
# ```

# So when backend sends:

# ```json
# { "day_of_week": 6 }
# ```

# Frontend shows:

# ```text
# Sunday
# ```

# ---

# # 🧩 What the restaurant owner actually interacts with

# They don’t see your model.

# They see a form like:

# ## 🟢 Delivery Settings Form

# ### Day: Monday

# * Open time: ⏰ [09:00]
# * Close time: ⏰ [17:00]
# * Closed? [checkbox]

# ---

# ## 🧠 If “Closed” is checked:

# Frontend does:

# * disables time inputs
# * sends:

# ```json
# {
#   "day_of_week": 0,
#   "is_closed": true
# }
# ```

# ---

# # 🔥 IMPORTANT DESIGN IDEA (this is key)

# Even if database uses:

# ```python
# TimeField
# IntegerField
# ```

# 👉 frontend ALWAYS uses human language.

# ---

# # 🍽️ Example full flow

# ## Step 1: Restaurant owner opens dashboard

# Sees:

# ```
# Monday   [Open 09:00 - 17:00]  [ ]
# Tuesday  [Open 09:00 - 17:00]  [ ]
# Sunday   [CLOSED]              [✔]
# ```

# ---

# ## Step 2: They click Sunday → Closed

# Frontend sends:

# ```json
# {
#   "day_of_week": 6,
#   "open_time": null,
#   "close_time": null
# }
# ```

# ---

# ## Step 3: Bot logic sees NULL → treats as CLOSED

# ---

# # 🧠 VERY SIMPLE MENTAL MODEL

# ## Backend thinks:

# > “Numbers and times”

# ## Frontend thinks:

# > “Days of the week and human-friendly forms”

# ## User thinks:

# > “Open or closed switches per day”

# ---

# # ⚖️ Why this design is standard

# Because:

# * backend must be structured (numbers)
# * frontend must be human (words)
# * users must see simplicity (toggles)

# ---

# # 🚀 BEST PRACTICAL UI DESIGN (for your system)

# For each restaurant:

# ```
# [ Monday    ]  Open: 09:00  Close: 17:00  [Closed toggle]
# [ Tuesday   ]  Open: 09:00  Close: 17:00  [Closed toggle]
# [ Wednesday ]  Open: 09:00  Close: 17:00  [Closed toggle]
# ...
# ```

# ---

# # ❤️ Final clarity

# If you remember ONE thing:

# > The database speaks numbers, but the dashboard speaks human language.

# ---

# If you want, I can next design your **full restaurant admin dashboard UI layout (like real SaaS systems such as Uber Eats merchant panel)** — that will make everything click visually 👍
