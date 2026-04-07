from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserAccountManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class AdminUser(AbstractBaseUser, PermissionsMixin):
    restaurant = models.ForeignKey('restaurants.Restaurant', on_delete=models.SET_NULL, null=True, related_name='admin_users')

    email = models.EmailField(max_length=200, unique=True)

    # Indicates whether this user can log into the Django admin site.
    is_staff = models.BooleanField(default=True)

    # Example: If a staff leaves the restaurant, you can set is_active=False to block login without deleting their account.
    is_active = models.BooleanField(default=True)
    
    # Indicates full control over the system.
    is_superuser = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)

    # connect the  userAccountmanager to the AdminUser model
    objects = UserAccountManager()

    USERNAME_FIELD = 'email'

    # used when creating superuser
    # REQUIRED_FIELDS = ['']

    def get_full_name(self):
        return self.user_name
    
    def __str__(self):
        return self.email
    

class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True)
    username = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Create timestamp, and Set once when the row is first inserted
    date_created = models.DateTimeField(auto_now_add=True)
    
    # Updated every time .save() is called
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.telegram_id)
    
    class Meta:

        indexes = [
            models.Index(fields=["telegram_id"]),
        ]



# class TelegramUser(models.Model):
#     telegram_id = models.BigIntegerField(unique=True, db_index=True)
#     first_name = models.CharField(max_length=100, blank=True)
#     username = models.CharField(max_length=100, blank=True)
#     is_active = models.BooleanField(default=True)
    
#     # Create timestamp, and Set once when the row is first inserted
#     date_created = models.DateTimeField(auto_now_add=True)
    
#     # Updated every time .save() is called
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return str(self.telegram_id)
    
#     class Meta:
#         indexes = [
#             models.Index(fields=["telegram_id"]),
#         ]



# | Field          | True → Meaning            | False → Meaning                     |
# | -------------- | ------------------------- | ----------------------------------- |
# | `is_staff`     | Can log into Django admin | Cannot log in admin                 |
# | `is_superuser` | Has full permissions      | Permissions limited by groups/roles |
# | `is_active`    | Account is active         | Cannot log in (soft delete)         |





# Ahhh I see exactly where the confusion is coming from 😅 — this is super common when mixing **Django’s auth system** with **custom user models like your TelegramUser**. Let’s break it down clearly.

# ---

# ### 1️⃣ What `self.request.user` usually means

# In a **DRF view**, when you use:

# ```python
# queryset = Cart.objects.filter(user=self.request.user)
# ```

# `self.request.user` refers to **the currently authenticated Django user** — i.e., someone logged in via Django’s authentication system (`AbstractBaseUser`, `AdminUser`, or the default `User`).

# This works perfectly if your app only uses Django auth users.

# ---

# ### 2️⃣ Why it doesn’t work for Telegram users

# Your Telegram users **aren’t Django users**. They only exist in your `TelegramUser` table. When the bot calls your DRF endpoint, `self.request.user` is **not set** unless you do extra work to authenticate them.

# So if you tried:

# ```python
# Cart.objects.filter(user=self.request.user)
# ```

# for a Telegram user, `self.request.user` will be either:

# * `AnonymousUser` (if the bot isn’t sending a token or Django session), or
# * Not relevant at all.

# Result? Wrong queries, or your cart won’t match the Telegram user.

# ---

# ### 3️⃣ The correct approach for your setup

# Instead of relying on `self.request.user`, you **must explicitly link models to `TelegramUser`**. For example:

# ```python
# class Cart(models.Model):
#     telegram_user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE)
#     product = models.ForeignKey(Product, on_delete=models.CASCADE)
#     quantity = models.PositiveIntegerField(default=1)
# ```

# Then in your DRF view, use the Telegram user object to filter:

# ```python
# telegram_user = TelegramUser.objects.get(telegram_id=request.data['telegram_id'])
# cart_items = Cart.objects.filter(telegram_user=telegram_user)
# ```

# ✅ This ensures that **all cart operations are scoped to that Telegram user**, not any Django auth user.

# ---

# ### 4️⃣ When `self.request.user` is okay

# You **can** still use `self.request.user` in your **AdminUser / React portal**, because your admin portal users will log in via Django auth.

# So your system will have **two separate “user contexts”**:

# | Context              | Model        | Access       |
# | -------------------- | ------------ | ------------ |
# | Telegram Bot         | TelegramUser | Cart, Orders |
# | Admin Portal (React) | AdminUser    | Products     |

# They never overlap. Telegram users don’t touch `AdminUser`. AdminUser doesn’t have a cart.

# ---

# ### ✅ Key takeaway

# * `self.request.user` → only works for Django-authenticated users.
# * Telegram bot users → use `TelegramUser` explicitly in all cart/order queries.
# * This separation keeps your bot logic safe and avoids accidentally mixing admin and Telegram users.

# ---

# If you want, I can **rewrite your DRF Cart/OrderBatch view** the way it should work **with TelegramUser instead of `request.user`**, so you can see it fully in action.

# Do you want me to do that?
