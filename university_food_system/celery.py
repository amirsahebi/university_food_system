# university_food_system/celery.py
from __future__ import absolute_import, unicode_literals
import os
from datetime import timedelta
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'university_food_system.settings')

# Create the Celery app
app = Celery('university_food_system')

# Load configuration from Django settings with CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Basic Celery configuration
app.conf.update(
    accept_content=['application/json'],
    task_serializer='json',
    result_serializer='json',
    timezone='Asia/Tehran',  # Using explicit timezone instead of from settings
    enable_utc=False,
)

# Auto-discover tasks in all installed apps
app.autodiscover_tasks([
    'users.tasks',
    'payments.tasks',
    'university_food_system.tasks.background_tasks',
    # Add other task modules here as needed
])

# Configure scheduled tasks
app.conf.beat_schedule = {
    # User management tasks
    'delete-expired-otps-every-5-minutes': {
        'task': 'users.tasks.delete_expired_otps',
        'schedule': 300.0,  # Every 5 minutes
    },
    'recover-trust-scores-daily': {
        'task': 'users.tasks.recover_trust_scores_daily',
        'schedule': crontab(hour=3, minute=0),  # Run daily at 3 AM
    },
    # Order management tasks
    'cancel-pending-payment-reservations': {
        'task': 'university_food_system.tasks.background_tasks.cancel_pending_payment_reservations',
        'schedule': timedelta(minutes=1),
    },
    'check-and-reverse-failed-payments': {
        'task': 'payments.tasks.check_and_reverse_failed_payments',
        'schedule': timedelta(minutes=1),
    },
}

# Debug task
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f'Request: {self.request!r}')
