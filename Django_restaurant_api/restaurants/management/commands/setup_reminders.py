from django.core.management.base import BaseCommand

# 👉 These are the database tables/models used by Celery Beat:
from django_celery_beat.models import CrontabSchedule, PeriodicTask
import json

# 👉 This lets you create a custom Django command
class Command(BaseCommand):

    # 👉 Just a description (shows when listing commands)
    help = "Setup weekly reminders"

    # 👉 This is the entry point
    # When you run: python manage.py setup_reminders 👉 THIS function(handle) runs
    def handle(self, *args, **kwargs):

        #👉 “Run at 12:00 PM every Saturday”
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='12',
            day_of_week='sat'
        )

        # PeriodicTask → WHAT to run (your task)
        obj, created = PeriodicTask.objects.get_or_create(
            name="weekly_reminder_restaurants",
            defaults={
                "crontab": schedule,
                "task": "orders.tasks.send_weekly_reminder",
                "args": json.dumps([]),
                "enabled": True,
            }
        )

        if not created:
            obj.crontab = schedule
            obj.task = "orders.tasks.send_weekly_reminder"
            obj.enabled = True
            obj.save()

        self.stdout.write(self.style.SUCCESS("Reminder setup ensured"))







# class Command(BaseCommand):
#     def handle(self, *args, **kwargs):

#         schedule, _ = CrontabSchedule.objects.get_or_create(
#             minute='0',
#             hour='12',
#             day_of_week='sat'
#         )
#         TASK_NAME = "weekly_reminder_restaurants"
#         PeriodicTask.objects.get_or_create(
#             crontab=schedule,
#             name=TASK_NAME,
#             task='orders.tasks.send_weekly_reminder',
#             args=json.dumps([]),
#             enabled=True
#         )

#         self.stdout.write(self.style.SUCCESS("Reminder setup done"))