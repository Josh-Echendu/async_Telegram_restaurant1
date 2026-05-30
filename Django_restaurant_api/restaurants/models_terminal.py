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
from .tasks import create_or_update_restaurant_terminal_address
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

SERVICE_MODE_CHOICES = (
    ('dine_in', 'In-Restaurant Only'),
    ('delivery', 'Delivery Only'),
    ('both', 'Dine-in & Delivery'),
)

BUSINESS_TYPE = (
    ("restaurant", "Restaurant"),
    ("vendor", "Vendor"),
)



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

PAYMENT_FLOW_CHOICES = (
    ('postpay', 'Pay After Service (Order now, pay later)'),
    ('prepay', 'Pay Before Service (Pay now, kitchen prepares)'),
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

    city = models.CharField(max_length=100, null=True, blank=True, 
                            help_text="City where the restaurant is located"
    )
    state = models.CharField(max_length=100, null=True, blank=True, 
                             help_text="State or region where the restaurant is located"
    )

    zipcode = models.CharField(max_length=20, null=True, blank=True,
        help_text="Postal code for the restaurant's location"
    )

    # Terminal API address ID for delivery logistics
    pick_up_address_id  = models.CharField(max_length=255, null=True, blank=True,
        help_text="Terminal API address ID for delivery logistics"
    )
    
    payment_flow = models.CharField(max_length=20, choices=PAYMENT_FLOW_CHOICES, blank=True, null=True,
        help_text="Dine-in payment flow: Pay after service (traditional) or Pay before service (prepaid)"
    )
    
    # ========== TELEGRAM BOT FIELDS ==========
    bot_username = models.CharField(max_length=100, blank=True, null=True)
    bot_token = EncryptedCharField(max_length=255, null=True)
    is_bot_active = models.BooleanField(default=True, db_index=True)
    webhook_secret_token = models.CharField(max_length=255, default=uuid.uuid4, null=True, blank=True,
        help_text="X-Telegram-Bot-Api-Secret-Token"
    )    
    
    # ========== WHATSAPP BUSINESS FIELDS ==========
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
    
    # ========== SHARED FIELDS (Both Telegram & WhatsApp) ==========
    # Real-world use cases: Restaurant closed, Kitchen busy, Maintenance mode
    is_accepting_orders = models.BooleanField(default=True)
    
    kitchen_chat_id = models.BigIntegerField(null=True, blank=True,
        help_text="Telegram Dine-in kitchen group chat ID OR WhatsApp group ID"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    # Delivery support fields
    delivery_chat_id = models.BigIntegerField(null=True, blank=True, 
        help_text="Telegram delivery group chat ID (if supports_delivery is True) OR WhatsApp delivery group ID"
    )

    service_mode = models.CharField(max_length=20, choices=SERVICE_MODE_CHOICES, db_index=True,
        help_text="Primary service mode of the business", 
    )

    max_tables = models.PositiveSmallIntegerField(default=0, 
        help_text="Amount of tables a restaurant has for dine-in orders"
    )
    
    average_preparation_time = models.PositiveIntegerField(default=30, 
        help_text="Minutes - How long food usually takes before it is ready"
    )
    delivery_fee = models.DecimalField(max_digits=1000, decimal_places=2, default=0)

    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE, db_index=True,
        help_text="Type of business: Restaurant or Vendor", 
    )

    timezone = models.CharField(max_length=50,default='Africa/Lagos',
        choices=[(tz, tz) for tz in pytz.common_timezones],
        help_text="Restaurant's local timezone"
    )

    def save(self, *args, **kwargs):
        # 1. Business logic
        if self.business_type == "vendor":
            self.max_tables = 0
            if self.service_mode != "delivery":
                self.service_mode = "delivery"
        elif self.business_type == "restaurant":
            if not self.service_mode:
                raise ValidationError("Restaurant must choose a service mode")

        # 2. Capture old values BEFORE saving
        if self.pk:
            try:
                old = Restaurant.objects.only('city', 'state', 'address').get(pk=self.pk)
                self._old_city = old.city
                self._old_state = old.state
                self._old_address = old.address
            except Restaurant.DoesNotExist:
                self._old_city = None
                self._old_state = None
                self._old_address = None
        else:
            self._old_city = None
            self._old_state = None
            self._old_address = None
            
        # 3. Save LAST
        super().save(*args, **kwargs)

    def clean(self):
        if self.kitchen_chat_id and not str(self.kitchen_chat_id).startswith("-"):
            raise ValidationError("Kitchen chat ID must be a group ID (negative number)")
        
        # WhatsApp validation
        if self.is_whatsapp_active:
            if not self.whatsapp_phone_number_id:
                raise ValidationError("WhatsApp Phone Number ID required when WhatsApp is active")
            if not self.whatsapp_access_token:
                raise ValidationError("WhatsApp Access Token required when WhatsApp is active")
            if not self.whatsapp_business_phone:
                raise ValidationError("WhatsApp Business Phone required when WhatsApp is active")

    def get_bot_token(self):
        return self.bot_token  # decrypted automatically
    
    def get_whatsapp_token(self):
        return self.whatsapp_access_token  # decrypted automatically
    
    def get_telegram_webhook_url(self):
        return f"{FAST_API_URL}/telegram-webhook/{self.rid}"
    

    def get_telegram_deep_url(self):
        return f"https://t.me/{self.bot_username}" if self.bot_username else None
    
    def get_whatsapp_deep_url_or_clean_phone(self, terminal=None):
        if not self.whatsapp_business_phone:
            return None
        
        if self.whatsapp_business_phone.startswith("+234"):
            return self.whatsapp_business_phone.strip()  # Already in correct format
        
        # Clean the string: remove spaces, plus signs, or dashes
        clean_phone = ''.join(filter(str.isdigit, self.whatsapp_business_phone))
        
        # Handle the Nigerian '0' prefix if the user saved it locally (e.g., 0703...)
        if clean_phone.startswith('0') and len(clean_phone) == 11:
            clean_phone = '234' + clean_phone[1:]
        
        # If it starts with 703 or 803 without a country code
        elif not clean_phone.startswith('234') and len(clean_phone) == 10:
            clean_phone = '234' + clean_phone

        if not terminal:
            return f"https://wa.me/{clean_phone}"
        else:
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

    print(f"===== SIGNAL FIRED: created={created}, rid={instance.rid}, city={instance.city} =====")

    # 1. Telegram webhook
    if instance.is_bot_active and instance.bot_token:
        register_telegram_webhook(instance)

    # 2. Detect location change using cached old values
    location_changed = False
    
    if created:
        location_changed = True
    else:
        old_city = getattr(instance, '_old_city', None)
        old_state = getattr(instance, '_old_state', None)
        old_address = getattr(instance, '_old_address', None)
        
        location_changed = (
            old_city != instance.city or
            old_state != instance.state or
            old_address != instance.address
        )
        
        print(f"SIGNAL: Old values - city={old_city}, state={old_state}")
        print(f"SIGNAL: New values - city={instance.city}, state={instance.state}")

    print(f"SIGNAL: location_changed={location_changed}, has_pickup_id={bool(instance.pick_up_address_id)}")

    # 3. Skip if nothing changed
    if instance.pick_up_address_id and not location_changed:
        print("SIGNAL: No location change, skipping")
        return

    # 4. Call directly
    print("SIGNAL: Triggering Terminal address sync...")
    result = create_or_update_restaurant_terminal_address.delay(
        restaurant_id=instance.rid,
        address_id=instance.pick_up_address_id,
        city=instance.city,
        country="NG",
        state=instance.state,
        first_name=instance.first_name,
        last_name=instance.last_name,
        phone=instance.get_whatsapp_deep_url_or_clean_phone(terminal=True),
        line1=instance.address,
        zip_code=instance.zipcode,

    )
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
    is_closed = models.BooleanField(default=False)

    class Meta:

        # Add unique constraint (one entry per day per restaurant)
        unique_together = [['restaurant', 'day_of_week']]

        indexes = [
            models.Index(fields=['restaurant', 'day_of_week']),
        ]


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
        return f"Table {self.table_number} - {self.status} - {self.session_id[:8]}"