# management/commands/register_webhooks.py

from django.core.management.base import BaseCommand
from restaurants.models import Restaurant
from ...services import register_telegram_webhook


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for r in Restaurant.objects.filter(is_bot_active=True):
            register_telegram_webhook(r)
            self.stdout.write(f"Webhook set for {r.name}")

# docker exec -it django_restaurant_api python manage.py register_webhooks