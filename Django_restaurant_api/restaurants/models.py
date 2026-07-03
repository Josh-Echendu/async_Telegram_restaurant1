import pytz
from django.db import models
from shortuuid import random
from shortuuid.django_fields import ShortUUIDField
from django.utils.html import mark_safe
from decimal import Decimal
import uuid
from django.db.models import Q
from django.db import IntegrityError, transaction
from userAuths.models import TelegramUser
from encrypted_model_fields.fields import EncryptedCharField
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .services import register_telegram_webhook, delete_webhook
from django.conf import settings
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import OperationalError
from datetime import time, timedelta
import random
from .tasks import get_coordinates_for_address
import logging

logger = logging.getLogger(__name__)


FAST_API_URL = settings.NGROK_FAST_API
ALPHABET = "abcdefghijklmnopqrstuvwxyz123456789"

def resturant_image_path(instance, filename):
    resturant_name = instance.name if instance.name else "uncategorized"
    return f"Restaurants Images/{resturant_name}/{filename}"
    
# class Table(models.Model):
#     restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
#     table_number = models.CharField(max_length=10)
#     is_active = models.BooleanField(default=True)



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
    # | Hotel      | ✅      | ✅       | ❌       | ❌    

# Then food goes to the wrong room, real guest complains, and your system looks broken.

# ---

# ### The Fix: Double Confirmation

# Make the guest confirm their room number **twice** before they can order.

# **Flow:**

# 1. Guest scans QR → bot opens
# 2. Bot: *"Please enter your room number:"*
# 3. Guest types: `305`
# 4. Bot: *"You entered Room 305. Is this correct? (Yes/No)"*
# 5. Guest taps **Yes** → proceeds to menu
# 6. Guest taps **No** → re-enter room number

# ---

# ### Additional Layer: Room Number Display on Payment Screen

# Before they pay, show the room number one more time:

# ```
# ┌─────────────────────────────┐
# │       CONFIRM ORDER         │
# │                             │
# │  🚪 Room: 305               │
# │  🍗 Jollof Rice     ₦3,500 │
# │                             │
# │  [Pay with Transfer]        │
# │  [Pay with Card]            │
# └─────────────────────────────┘
# ```

# Guest sees `Room 305` and thinks: *"Wait, I'm in 503!"* → they'll correct it before paying.

# ---

# ### Why This Is Enough:

# | Layer | What It Catches |
# |-------|----------------|
# | Room number entry | Guest types their room |
# | Confirmation prompt | "Is 305 correct?" catches typos |
# | Display before payment | Final visual check before money leaves |
# | Physical reality | Guest is literally inside the room, they know their room number |

# ---

# If a guest still manages to type the wrong room number after three chances to catch it, that's on them — not your system. But this catches 99% of mistakes.


VENDOR_TYPE_CHOICES = (
    ('cooked_food', 'Cooked Food Vendor'),
    ('goods', 'Goods Vendor'),
)


# models.py
HOTEL_SERVICE_CHOICES = [
    ('dine_in', 'Restaurant (Dine-in)'),
    ('room_service', 'Room Service Only'),
    ('both', 'Both Restaurant & Room Service'),
]

SERVICE_MODE_CHOICES = (
    ('dine_in', 'In-Restaurant Only'),
    ('delivery', 'Delivery Only'),
    ('both', 'Dine-in & Delivery'),
)

BUSINESS_TYPE = (
    ("restaurant", "Restaurant"),
    ("vendor", "Vendor"),
    ("hotel", "Hotel"),
)

class Restaurant(models.Model):
    rid = ShortUUIDField(unique=True, prefix='res', length=10, max_length=20, alphabet=ALPHABET, db_index=True)
    name = models.CharField(max_length=250)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to=resturant_image_path, blank=True, null=True)
    
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    
    address = models.CharField(max_length=45, null=True, blank=True,
        help_text="Physical address of the restaurant"
    )

    state = models.CharField(max_length=100, null=True, blank=True, 
        help_text="State or region where the restaurant is located"
    )

    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE, db_index=True,
        help_text="Type of business: Restaurant, Vendor, or Hotel", 
    )

    service_mode = models.CharField(max_length=20, choices=SERVICE_MODE_CHOICES, db_index=True,
        help_text="Primary service mode of the business", blank=True, null=True
    )

    vendor_type = models.CharField(max_length=20, choices=VENDOR_TYPE_CHOICES, null=True, blank=True,
        help_text="Only applies to vendors. Cooked food vendors have a 15km delivery limit."
    )

    hotel_service_type = models.CharField(max_length=20, choices=HOTEL_SERVICE_CHOICES, blank=True, null=True,
        help_text="Only applies to hotels. Determines if the hotel has a restaurant, room service, or both."
    )

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    max_delivery_radius_km = models.FloatField(blank=True, null=True)
    lga = models.CharField(max_length=100, null=True, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=100, blank=True, null=True)
    bank_account_name = models.CharField(max_length=100, blank=True, null=True)

    # ========== TELEGRAM BOT FIELDS ==========
    bot_username = models.CharField(max_length=100, blank=True, null=True)
    owner_telegram_username = models.CharField(max_length=100, blank=True, null=True)
    bot_token = EncryptedCharField(max_length=255, null=True)
    is_bot_active = models.BooleanField(default=True, db_index=True)
    webhook_secret_token = models.CharField(max_length=255, default=uuid.uuid4, null=True, blank=True,
        help_text="X-Telegram-Bot-Api-Secret-Token"
    )    
    
    # ========== WHATSAPP BUSINESS FIELDS ==========
    whatsapp_verified_name = models.CharField(max_length=255, null=True, blank=True, 
        help_text="WhatsApp Bussiness Verified Name"
    )

    # restaurants/models.py
    whatsapp_setup_status = models.CharField(max_length=20,
        choices=(('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('failed', 'Failed'),), default='pending',
        help_text='Status of WhatsApp onboarding after initial token exchange'
    )
    whatsapp_business_account_id = models.CharField(max_length=255, null=True, blank=True,
        help_text="WhatsApp Business Account ID (WABA ID)"
    )
    whatsapp_phone_number_id = models.CharField(max_length=255, null=True, blank=True,
        help_text="WhatsApp Phone Number ID for sending messages"
    )
    whatsapp_access_token = EncryptedCharField(max_length=500, null=True, blank=True,
        help_text="WhatsApp Cloud API access token"
    )
    whatsapp_business_phone = models.CharField(max_length=20, null=True, blank=True,
        help_text="WhatsApp business phone number (e.g., +2348123456789)"
    )
    whatsapp_webhook_verified = models.BooleanField(default=False,
        help_text="Whether WhatsApp webhook has been verified"
    )
    is_whatsapp_active = models.BooleanField(default=False, db_index=True,
        help_text="Whether WhatsApp bot is active"
    )
    
    # ========== SHARED FIELDS ==========
    is_accepting_orders = models.BooleanField(default=True)
    
    kitchen_chat_id = models.BigIntegerField(null=True, blank=True,
        help_text="Telegram Dine-in kitchen group chat ID OR WhatsApp group ID"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    delivery_chat_id = models.BigIntegerField(null=True, blank=True, 
        help_text="Telegram delivery group chat ID OR WhatsApp delivery group ID"
    )

    max_tables = models.PositiveSmallIntegerField(default=10, 
        help_text="Amount of tables a restaurant has for dine-in orders"
    )
    average_preparation_time = models.PositiveIntegerField(default=30, 
        help_text="Minutes - How long food usually takes before it is ready"
    )
    delivery_fee = models.DecimalField(max_digits=1000, decimal_places=2, default=0)

    timezone = models.CharField(max_length=50, default='Africa/Lagos',
        choices=[(tz, tz) for tz in pytz.common_timezones],
        help_text="Restaurant's local timezone"
    )

    def save(self, *args, **kwargs):
        
        # ========== NEW: Auto-set delivery radius ==========
        if self.business_type == 'restaurant' and self.service_mode in ('delivery', 'both'):
            self.max_delivery_radius_km = 15

        elif self.business_type == 'vendor' and self.vendor_type == 'cooked_food':
            self.max_delivery_radius_km = 15

        else:
            self.max_delivery_radius_km = None  # Unlimited for goods vendors

        # ──────────────────────────────────────────────
        # 1. VENDOR VALIDATION
        # ──────────────────────────────────────────────
        if self.business_type == "vendor":
            
            # Vendor must have vendor_type
            if not self.vendor_type:
                raise ValidationError({
                    "vendor_type": "Vendor must choose a vendor type (Cooked Food or Goods)."
                })

            # Vendor is always delivery-only
            self.service_mode = "delivery"
            self.max_tables = 0

            # Vendor must have delivery fee
            if not self.delivery_fee or self.delivery_fee <= 0:
                raise ValidationError({
                    "delivery_fee": "Vendor must set a delivery fee."
                })

        # ──────────────────────────────────────────────
        # 2. HOTEL VALIDATION
        # ──────────────────────────────────────────────
        if self.business_type == "hotel":
            
            if self.hotel_service_type == "dine_in":
                self.service_mode = "dine_in"

            elif self.hotel_service_type == "room_service":
                self.service_mode = "delivery"

            elif self.hotel_service_type == "both":
                self.service_mode = "both"
            
            # Hotel must have a service type
            if not self.hotel_service_type:
                raise ValidationError({
                    "hotel_service_type": "Hotel must choose a service type (Dine-in, Room Service, or Both)."
                })

            # Dine-in or Both → require tables
            if self.hotel_service_type in ["dine_in", "both"]:
                if not self.max_tables or self.max_tables < 1:
                    raise ValidationError({
                        "max_tables": "Hotel with dine-in service must have at least 1 table."
                    })

            # Room Service only → no tables needed
            elif self.hotel_service_type == "room_service":
                self.max_tables = 0

        # ──────────────────────────────────────────────
        # 3. RESTAURANT VALIDATION
        # ──────────────────────────────────────────────
        if self.business_type == "restaurant":
            
            # Service mode must be set
            if not self.service_mode:
                raise ValidationError({
                    "service_mode": "Restaurant must choose a service mode (Dine-in, Delivery, or Both)."
                })

            # Dine-in or Both → require tables
            if self.service_mode in ["dine_in", "both"]:
                if not self.max_tables or self.max_tables < 1:
                    raise ValidationError({
                        "max_tables": "Restaurant with dine-in service must have at least 1 table."
                    })

            # Delivery only → no tables needed
            elif self.service_mode == "delivery":
                self.max_tables = 0



        # Normalize WhatsApp phone number
        if self.whatsapp_business_phone:
            if self.whatsapp_business_phone.startswith("+234"):
                self.whatsapp_business_phone = self.whatsapp_business_phone.strip()
            else:
                clean_phone = ''.join(filter(str.isdigit, self.whatsapp_business_phone))
                if clean_phone.startswith('0') and len(clean_phone) == 11:
                    clean_phone = '234' + clean_phone[1:]
                elif not clean_phone.startswith('234') and len(clean_phone) == 10:
                    clean_phone = '234' + clean_phone
                if clean_phone:
                    self.whatsapp_business_phone = clean_phone
        
        # Capture old values BEFORE saving
        if self.pk:
            try:
                old = Restaurant.objects.only('lga', 'state', 'address', 'latitude', 'longitude').get(pk=self.pk)
                self._old_lga = old.lga
                self._old_state = old.state
                self._old_address = old.address
                self._old_latitude = old.latitude
                self._old_longitude = old.longitude
            except Restaurant.DoesNotExist:
                self._old_lga = None
                self._old_state = None
                self._old_address = None
                self._old_latitude = None
                self._old_longitude = None
        else:
            self._old_lga = None
            self._old_state = None
            self._old_address = None
            self._old_latitude = None
            self._old_longitude = None

        super().save(*args, **kwargs)

    def clean(self):
        
        if self.kitchen_chat_id and not str(self.kitchen_chat_id).startswith("-"):
            raise ValidationError("Kitchen chat ID must be a group ID (negative number)")
   
        if self.is_whatsapp_active:
            # Official WhatsApp (Meta OAuth) — all three fields come from the handshake
            if self.business_type == 'hotel' or (self.business_type == 'restaurant' and self.service_mode in ('dine_in', 'both')):
                # These are auto-filled by Meta OAuth — just confirm they exist
                if not self.whatsapp_phone_number_id or not self.whatsapp_access_token:
                    raise ValidationError("WhatsApp connection incomplete. Please reconnect via Meta.")

            # Unofficial WhatsApp (Baileys) — only phone number needed
            else:
                if not self.whatsapp_business_phone:
                    raise ValidationError("WhatsApp Business Phone required to link your device")

    def get_bot_token(self):
        return self.bot_token

    def get_whatsapp_token(self):
        return self.whatsapp_access_token

    def get_telegram_webhook_url(self):
        return f"{FAST_API_URL}/telegram-webhook/{self.rid}"

    def get_telegram_deep_url(self):
        return f"https://t.me/{self.bot_username}" if self.bot_username else None

    def get_whatsapp_deep_url_or_clean_phone(self, terminal=None):
        if not self.whatsapp_business_phone:
            return None
        
        if self.whatsapp_business_phone.startswith("+234"):
            return self.whatsapp_business_phone.strip()
        
        clean_phone = ''.join(filter(str.isdigit, self.whatsapp_business_phone))
        
        if clean_phone.startswith('0') and len(clean_phone) == 11:
            clean_phone = '234' + clean_phone[1:]
        elif not clean_phone.startswith('234') and len(clean_phone) == 10:
            clean_phone = '234' + clean_phone

        if clean_phone:
            return clean_phone

    def restaurant_image(self):
        if self.image:
            return mark_safe(f'<img src="{self.image.url}" width="50" height="50" />')
        return "No Image"

    def __str__(self):
        platform = []
        if self.is_bot_active:
            platform.append("Telegram")
        if self.is_whatsapp_active:
            platform.append("WhatsApp")
        platform_str = f" ({'+'.join(platform)})" if platform else ""
        return f"{self.name}{platform_str}"
    

@receiver(post_save, sender=Restaurant)
def manage_restaurant_webhook(sender, instance, created, **kwargs):

    print(f"===== SIGNAL FIRED: created={created}, rid={instance.rid}, lga={instance.lga} =====")

    # 1. Telegram webhook
    if instance.is_bot_active and instance.bot_token:
        register_telegram_webhook(instance)

    vendor_type = (instance.vendor_type or "").lower()
    service_mode = (instance.service_mode or "").lower()

    if vendor_type == 'cooked_food' or service_mode == 'both':       
        
        # 2. Detect location change using cached old values
        location_changed = False
        
        if created:
            location_changed = True
        else:
            old_lga = getattr(instance, '_old_lga', None)
            old_state = getattr(instance, '_old_state', None)
            old_address = getattr(instance, '_old_address', None)
            old_latitude = getattr(instance, '_old_latitude', None)
            old_longitude = getattr(instance, '_old_longitude', None)
            
            location_changed = (
                old_lga != instance.lga or
                old_state != instance.state or
                old_address != instance.address or
                old_latitude != instance.latitude or
                old_longitude != instance.longitude
            )
            
            print(f"SIGNAL: Old values - lga={old_lga}, state={old_state}, address={old_address}, latitude={old_latitude}, longitude={old_longitude}")
            print(f"SIGNAL: New values - lga={instance.lga}, state={instance.state}, address={instance.address}")

        print(f"SIGNAL: location_changed={location_changed}, longitude={instance.longitude}, latitude={instance.latitude}")

        # 3. Skip if nothing changed
        if not location_changed:
            print("SIGNAL: No location change, skipping")
            return

        # 4. Call directly
        print("SIGNAL: Triggering Terminal address sync...")
        result = get_coordinates_for_address.delay(lga=instance.lga, state=instance.state, restaurant_id=instance.rid)
        print(f"SIGNAL: Terminal sync result = {result}")



@receiver(post_delete, sender=Restaurant)
def remove_restaurant_webhook(sender, instance, **kwargs):
    """
    Handles Deletion.
    """
    if instance.bot_token:
        delete_webhook(instance)



class RestaurantDeliveryOpeningHours(models.Model):
    restaurant = models.ForeignKey(Restaurant, db_index=True, on_delete=models.CASCADE, related_name='delivery_opening_hours')
    day_of_week = models.IntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(6)
        ]
    )
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = [['restaurant', 'day_of_week']]
        indexes = [
            models.Index(fields=['restaurant', 'day_of_week']),
        ]

    def clean(self):

        # Hotels can't set delivery hours
        if self.restaurant.business_type == 'hotel':
            raise ValidationError("Hotels cannot have delivery hours.")
        
        # Dine-in only restaurants can't set delivery hours
        if self.restaurant.business_type == 'restaurant' and self.restaurant.service_mode == 'dine_in':
            raise ValidationError("This restaurant is dine-in only.")
        
        # Only restaurants with delivery or vendors can set hours
        if self.restaurant.business_type not in ('restaurant', 'vendor'):
            raise ValidationError("Only restaurants and vendors can set delivery hours.")
        
        if self.restaurant.business_type == 'restaurant' and self.restaurant.service_mode not in ('delivery', 'both'):
            raise ValidationError("This restaurant does not offer delivery.")
        
        # Both or neither
        if (self.open_time and not self.close_time) or (self.close_time and not self.open_time):
            raise ValidationError("Both open and close time must be set, or leave both empty for closed.")
        
        if self.open_time and self.close_time and self.open_time >= self.close_time:
            raise ValidationError("Open time must be before close time.")

    @property
    def is_closed(self):
        return self.open_time is None or self.close_time is None


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

class DineInOTPSession(models.Model):
    """
    Production-grade OTP session for restaurant dine-in verification
    """
    STATUS_CHOICES = (
        ('pending', 'Waiting for waiter'),
        ('verified', 'Customer verified'),
        ('expired', 'OTP expired'),
        ('cancelled', 'Cancelled by waiter'),
    )
    
    # Core fields
    session_id = ShortUUIDField(max_length=100, unique=True, db_index=True)
    restaurant = models.ForeignKey('restaurants.Restaurant', on_delete=models.CASCADE, db_index=True)
    user = models.ForeignKey('userAuths.TelegramUser', on_delete=models.CASCADE, db_index=True, null=True)    

    # Verification fields
    table_number = models.PositiveSmallIntegerField()
    waiter_telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    waiter_username = models.CharField(max_length=255, null=True, blank=True)
    

    # OTP fields
    otp_code = models.CharField(max_length=10, null=True, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps & status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Idempotency & security
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=3)
    
    class Meta:
        
        indexes = [
            models.Index(fields=['restaurant', 'status']),
            models.Index(fields=['user', 'restaurant', 'status']),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=['restaurant', 'otp_code'],
                condition=Q(status='pending'),
                name='unique_active_otp_per_restaurant'
            )
        ]

    def generate_otp(self):

        for _ in range(5):
            code = str(random.randint(100000, 999999))

            try:
                with transaction.atomic():
                    exists = DineInOTPSession.objects.select_for_update().filter(
                        restaurant=self.restaurant,
                        otp_code=code,
                        status='pending'
                    ).exists()

                    if not exists:
                        self.otp_code = code
                        self.otp_expires_at = timezone.now() + timedelta(minutes=1)
                        self.save(update_fields=['otp_code', 'otp_expires_at'])
                        return code

            except IntegrityError:
                continue

        raise Exception("Failed to generate unique OTP")
    
    def is_otp_valid(self, code):
        """Check if OTP is valid and not expired"""
        if self.otp_code != code:
            return False
        if self.otp_expires_at < timezone.now():
            return False
        return True
    
    def verify(self, active_user):
        """Mark session as verified"""
        self.user=active_user
        self.status='verified'
        self.verified_at=timezone.now()
        self.save(update_fields=['status', 'verified_at', 'user'])
    
    def expire(self):
        """Expire the session"""
        self.status = 'expired'
        self.save(update_fields=['status'])
    
    def increment_retry(self):
        """Increment retry count and expire if exceeded"""
        
        self.retry_count += 1
        if self.retry_count >= self.max_retries:
            self.status = 'expired'
        self.save(update_fields=['retry_count', 'status'])
    
    @classmethod
    def create_session(cls, waiter_telegram_id, restaurant, table_number, waiter_username):
        """Factory method to create a new session"""
        
        return cls.objects.create(
            status='pending',
            restaurant=restaurant,
            table_number=table_number,
            waiter_telegram_id=waiter_telegram_id,
            waiter_username=waiter_username,
        )
    
    def __str__(self):
        return f"Table {self.table_number} - {self.status} - {self.restaurant.name}"

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
