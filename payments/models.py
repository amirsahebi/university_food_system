from django.db import models
from django.contrib.auth import get_user_model
from orders.models import Reservation
from core.logging_utils import get_logger

User = get_user_model()
logger = get_logger(__name__)

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    reservation = models.ForeignKey(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    amount = models.PositiveIntegerField()  # Amount in Rial (IRR)
    authority = models.CharField(max_length=255, blank=True, null=True)  # Authority Code from ZarinPal
    ref_id = models.CharField(max_length=255, blank=True, null=True)  # Reference ID after success
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} - {self.user.phone_number} - {self.status}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            logger.info(f"New payment created: {self.id} for user {self.user.id}")
        else:
            logger.info(f"Payment updated: {self.id} status changed to {self.status}")
