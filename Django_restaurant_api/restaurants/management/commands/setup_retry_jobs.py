from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask
import json


class Command(BaseCommand):
    help = "Setup 5-minute retry jobs"

    def handle(self, *args, **kwargs):

        # 1. Create/Get interval (every 5 minutes)
        schedule, _ = IntervalSchedule.objects.get_or_create( # IntervalSchedule: Defines how often something runs e.g every 5 minutes
            every=5,
            period=IntervalSchedule.MINUTES,
        )

        # 2. Create/Get periodic task
        task, created = PeriodicTask.objects.get_or_create(
            name="retry_failed_operations_every_5mins",
            defaults={
                "interval": schedule,
                "task": "orders.tasks.run_retry_jobs",
                "args": json.dumps([]),
                "enabled": True,
            },
        )

        # 3. If it already exists → update it
        if not created:
            task.interval = schedule
            task.task = "orders.tasks.run_retry_jobs"
            task.enabled = True
            task.save()

        self.stdout.write(self.style.SUCCESS("5-minute retry job ensured"))