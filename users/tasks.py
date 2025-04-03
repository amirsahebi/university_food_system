# users/tasks.py
from celery import shared_task
from django.utils.timezone import now, timedelta
from .models import OTP

@shared_task
def delete_expired_otps():
    expiration_time = now() - timedelta(minutes=5)
    expired_otps = OTP.objects.filter(created_at__lt=expiration_time)
    count = expired_otps.delete()[0]
    return f"{count} expired OTP(s) deleted."
