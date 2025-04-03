from django.db import models
from django.contrib.auth import get_user_model
from orders.models import Reservation
User = get_user_model()

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="payments")
    amount = models.PositiveIntegerField()  # Amount in Rial (IRR)
    authority = models.CharField(max_length=255, blank=True, null=True)  # Authority Code from ZarinPal
    ref_id = models.CharField(max_length=255, blank=True, null=True)  # Reference ID after success
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} - {self.user.phone_number} - {self.status}"
