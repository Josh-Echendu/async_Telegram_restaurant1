from django.db import models
from django.core.exceptions import ValidationError


# Create your models here.
class POSConfig(models.Model):
    BRAND_CHOICES = (
        ('moniepoint', 'Moniepoint'),
        ('opay', 'Opay'),
        ('palmpay', 'Palmpay'),
    )

    restaurant = models.ForeignKey('restaurants.Restaurant', on_delete=models.CASCADE, related_name='pos_configs', db_index=True)
    brand = models.CharField(max_length=20, choices=BRAND_CHOICES, db_index=True)
    terminal_identifier = models.CharField(max_length=100, help_text="Terminal serial number or merchant ID from the POS provider")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "POS Configuration"
        verbose_name_plural = "POS Configurations"

        constraints = [
            # A restaurant can only have ONE config per brand
            models.UniqueConstraint(
                fields=['restaurant', 'brand'],
                name='unique_restaurant_brand'
            ),
        ]

        indexes = [
            models.Index(fields=['restaurant', 'is_active']),
        ]

    def clean(self):
        # Terminal identifier must not be empty or whitespace-only
        if self.terminal_identifier:
            self.terminal_identifier = self.terminal_identifier.strip()
        
        if not self.terminal_identifier:
            raise ValidationError({
                'terminal_identifier': 'Terminal identifier cannot be empty.'
            })

        # Prevent duplicate active configs for same brand (extra safety)
        if self.is_active:
            existing = POSConfig.objects.filter(restaurant=self.restaurant, brand=self.brand, is_active=True)

            if self.pk:
                existing = existing.exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError({
                    'brand': f"An active {self.get_brand_display()} config already exists for this restaurant."
                })

    def save(self, *args, **kwargs):

        # Always run full clean before save
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.restaurant.name} - {self.get_brand_display()} ({status})"
