from django.db import models

# Create your models here.
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



FAST_API_URL = settings.NGROK_FAST_API
ALPHABET = "abcdefghijklmnopqrstuvwxyz123456789"

def resturant_image_path(instance, filename):
    resturant_name = instance.name if instance.name else "uncategorized"
    return f"Restaurants Images/{resturant_name}/{filename}"


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
    kitchen_chat_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Telegram kitchen group chat ID"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)


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