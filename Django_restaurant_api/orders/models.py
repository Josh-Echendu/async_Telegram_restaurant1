from django.db import models
from shortuuid.django_fields import ShortUUIDField
from django.utils.html import mark_safe
from django.contrib.auth.models import User
from decimal import Decimal
from userAuths.models import TelegramUser

KITCHEN_STATUS_CHOICES = (
    ('pending', 'Pending'),        # Kitchen hasn’t started
    ('processing', 'Processing'),  # Being cooked
    ('delivered', 'Delivered'),    # Done and ready
)

PAYMENT_STATUS_CHOICES = (
    ('unpaid', 'Unpaid'),
    ('paid', 'Paid'),
)

def product_image_path(instance, filename):
    category_title = instance.category.title if instance.category else "uncategorized"
    return f'products/{category_title}/{filename}'

class Category(models.Model):
    telegram_user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='categories', db_index=True, null=True)
    cid = ShortUUIDField(unique=True, length=10, max_length=20, alphabet='abcdefgh12345')
    title = models.CharField(max_length=100)
    image = models.ImageField(blank=True, null=True, upload_to='category/')

    class Meta:
        verbose_name_plural = 'Categories'

        indexes = [
            models.Index(fields=["telegram_user"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["telegram_user"], name="unique_telegram_user")
        ]
    
    def category_image(self):
        if self.image:
            return mark_safe(f'<img src="{self.image.url}" width="50" height="50" />')
        return "No Image"
    
    def __str__(self):
        return self.title


class Product(models.Model):
    pid = ShortUUIDField(unique=True, length=10, max_length=20, alphabet='abcdefgh12345')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='category', db_index=True)
    title = models.CharField(max_length=100, default='Affordable meal', unique=True)
    image = models.ImageField(upload_to=product_image_path, default='product.jpg')
    description = models.TextField(null=True, blank=True, default='This is the product')
    price = models.DecimalField(max_digits=12, decimal_places=2, default='0.00')
    in_stock = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name_plural = 'Products'
        ordering = ['-date']

        indexes = [
            models.Index(fields=['category']),
        ]

    def product_image(self):
        if self.image:
            return mark_safe(f'<img src="{self.image.url}" width="50" height="50" />')
        return "No Image"
    
    def __str__(self):
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

    def __str__(self):
        return f'{self.telegram_user} | {self.product.title} | {self.quantity}'

# Permanent order batch (represents one checkout)
class OrderBatch(models.Model):
    bid = ShortUUIDField(unique=True, length=10, max_length=20, editable=False) # editable=False: 👉 This field will not appear in Django forms or admin forms.
    telegram_user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='order_batches', db_index=True, null=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=KITCHEN_STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    date_created = models.DateTimeField(auto_now_add=True)
    
    notified_kitchen = models.BooleanField(default=False)
    notified_user = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=255, unique=True, null=True)
    removed_cart_items = models.JSONField(default=list, blank=True)


    class Meta:
        indexes = [
            models.Index(fields=["telegram_user"]),
        ]    
        constraints = [
            models.UniqueConstraint(fields=["bid", "telegram_user"], name="unique_telegram_user_bid")
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


# docker exec -it django_restaurant_api python manage.py flush --noinput
# docker exec -it django_restaurant_api python manage.py loaddata data_backup_utf8.json



# docker compose exec web python manage.py migrate

# docker compose exec web python manage.py flush --noinput

# docker compose exec web python manage.py loaddata data_backup_utf8.json
