from django.db import models
from shortuuid.django_fields import ShortUUIDField
from django.utils.html import mark_safe
from django.contrib.auth.models import User
from decimal import Decimal
from userAuths.models import TelegramUser, AdminUser
from django.core.exceptions import ValidationError
from restaurants.models import Restaurant


ALPHABET = "abcdefghijklmnopqrstuvwxyz123456789"

KITCHEN_STATUS_CHOICES = (
    ('pending', 'Pending'),        # Kitchen hasn’t started
    ('processing', 'Processing'),  # Being cooked
    ('delivered', 'Delivered'),    # Done and ready
)

PAYMENT_STATUS_CHOICES = (
    ('unpaid', 'Unpaid'),
    ('paid', 'Paid'),
)

TRANSACTION_TYPE = (
    ('None', 'None'),
    ('cash', 'CASH'),
    ('pos', 'POS'),
    ('dynamic_virtual_account', 'dynamic_virtual_account'),
)

def product_image_path(instance, filename):
    category_title = instance.category.title if instance.category else "uncategorized"
    resturant_name = instance.restaurant.name if instance.restaurant else "uncategorized"
    return f'{resturant_name}/products/{category_title}/{filename}'


class Category(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, db_index=True, null=True)
    cid = ShortUUIDField(unique=True, length=10, max_length=20, alphabet=ALPHABET)
    title = models.CharField(max_length=100)
    image = models.ImageField(blank=True, null=True, upload_to='category/')

    class Meta:
        verbose_name_plural = 'Categories'

        indexes = [
            models.Index(fields=["restaurant"]),
        ]
        constraints = []
    
    def category_image(self):
        if self.image:
            return mark_safe(f'<img src="{self.image.url}" width="50" height="50" />')
        return "No Image"
    
    def __str__(self):
        return self.title

product = None  # Replace with your actual product instance
Category.objects.filter(product__product=product, product_set__instock=True).distinct()

class Product(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='restaurant_products', db_index=True, null=True)
    pid = ShortUUIDField(unique=True, length=10, max_length=20, alphabet=ALPHABET)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='category', db_index=True)
    title = models.CharField(max_length=100, default='Affordable meal', unique=True)
    image = models.ImageField(upload_to=product_image_path, default='product.jpg')
    description = models.TextField(null=True, blank=True, default='This is the product')
    price = models.DecimalField(max_digits=12, decimal_places=2, default='0.00')
    in_stock = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        verbose_name_plural = 'Products'
        ordering = ['-date']

        indexes = [
            models.Index(fields=['category', 'date', 'restaurant']),
        ]

    def product_image(self):
        if self.image:
            return mark_safe(f'<img src="{self.image.url}" width="50" height="50" />')
        return "No Image"
    
    def str(self):
        return self.title
    
class ProductImages(models.Model):
    images = models.ImageField(upload_to=product_image_path, default='product.jpg')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name='p_images', db_index=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Product Images'
    
    def product_image(self):
        if self.images:
            return mark_safe(f'<img src="{self.images.url}" width="50" height="50" />')
        return "No Image"
    

# Temporary cart model (session-like, user adds items here)
class Cart(models.Model):
    telegram_user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='cart_items', db_index=True, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product', db_index=True)
    quantity = models.PositiveIntegerField(default=1)
    date_added = models.DateTimeField(auto_now_add=True)

    def product_image(self):
        if self.product.image:
            return mark_safe(f'<img src="{self.product.image.url}" width="50" height="50" />')
        return "No Image"

    class Meta:
        indexes = [
            models.Index(fields=["product", "telegram_user"]),
        ]

        constraints = [
            models.UniqueConstraint(fields=["telegram_user", "product"], name="unique_telegram_user_product")
        ]
        
    def multiply_price(self):
        return self.product.price * self.quantity

    def str(self):
        return f'{self.telegram_user} | {self.product.title} | {self.quantity}'


class CheckoutSession(models.Model):
    session_id = ShortUUIDField(unique=True, length=10, alphabet=ALPHABET, prefix='ses')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, null=True, related_name='restaurant_session')
    telegram_user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, null=True, related_name='telegram_session')
    
    va_acct_number = models.CharField(max_length=50, null=True, blank=True)  # Assigned DVA
    va_bank = models.CharField(max_length=50, null=True, blank=True)
    va_expiry = models.DateTimeField(null=True, blank=True)  # NEW FIELD
    merchant_reference = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    transaction_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    transaction_type = models.CharField(max_length=100, choices=TRANSACTION_TYPE, default='None')


    expected_amount = models.PositiveIntegerField(null=True, blank=True)
    amount_received = models.PositiveIntegerField(null=True, blank=True)
    
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    webhook_payload = models.JSONField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    payment_in_progress = models.BooleanField(default=False)
    notification_sent =  models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True, db_index=True)
    # expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta: # In Django models, Meta is a special inner class used to define extra rules or settings for the model.
        indexes = [
            models.Index(fields=["telegram_user", "restaurant", "is_active", "date_created"])
        ]

        # This line starts a list of database constraints.
        # A constraint is a rule the database must obey.
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "telegram_user"], # A telegram user can only have ONE session for that restaurant in the entire database.
                condition=models.Q(is_active=True), # here we update it to: A single user in a restaurant can only have ONE session where is_active=True.
                name="one_active_session_per_user" # This gives the constraint a name. It also helps when: debugging, migrations, database inspection
            )
        ]
    def __str__(self):
        return f"{self.session_id}-{self.restaurant}"

# Permanent order batch (represents one checkout)
class OrderBatch(models.Model):
    checkout_session = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name="session_batches", null=True, db_index=True)
    
    bid = ShortUUIDField(unique=True, length=10, max_length=20, editable=False) # editable=False: 👉 This field will not appear in Django forms or admin forms.
    restaurant = models.ForeignKey(Restaurant, db_index=True, on_delete=models.SET_NULL, null=True, related_name='restaurant_orders')
    telegram_user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='order_batches', db_index=True, null=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=KITCHEN_STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    date_created = models.DateTimeField(auto_now_add=True, db_index=True)
    
    notified_kitchen = models.BooleanField(default=False)
    notified_user = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=255, unique=True, null=True)
    removed_cart_items = models.JSONField(default=list, blank=True)


    class Meta:
        indexes = [
            models.Index(fields=["telegram_user", "restaurant", "checkout_session"]),
        ]    

    def __str__(self):
        return f'{self.bid} - {self.telegram_user}'

    

# Items that belong to an order batch
class OrderBatchItem(models.Model):
    batch = models.ForeignKey(OrderBatch, on_delete=models.CASCADE, related_name='items', db_index=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, db_index=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def product_image(self):
        if self.product.image:
            return mark_safe(f'<img src="{self.product.image.url}" width="50" height="50" />')
        return "No Image"
    
    def multiply_price(self):
        return self.quantity * self.price
    
    class Meta:
        indexes = [
            models.Index(fields=["batch", "product"]),
        ]

    def __str__(self):
        return f'{self.batch}'


#  confirmOrder() {
#     this.showCheckoutModal = false;
#     this.showCart = false;
#     this.clearCart();
#     this.toast = { visible: true, message: '🍽️ YOUR ORDER HAS BEEN SENT TO THE KITCHEN. PLEASE CHECK YOUR WHATSAPP FOR ORDER DETAILS.' };
#     setTimeout(() => this.toast.visible = false, 6000);
#   }

# docker exec -it django_restaurant_api python manage.py flush --noinput
# docker exec -it django_restaurant_api python manage.py loaddata data_backup_utf8.json



# docker compose exec web python manage.py migrate

# docker compose exec web python manage.py flush --noinput

# docker compose exec web python manage.py loaddata data_backup_utf8.json