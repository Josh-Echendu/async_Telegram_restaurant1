# project_name/celery.py
import os
from celery import Celery
from celery.signals import worker_ready


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restaurant_api.settings')

app = Celery('restaurant_api')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()