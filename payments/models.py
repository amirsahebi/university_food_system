from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime as _dt, timezone as _pytz
from orders.models import Reservation
from core.logging_utils import get_logger
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
import json

User = get_user_model()
logger = get_logger(__name__)

class PaymentQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status='pending')
    
    def paid(self):
        return self.filter(status='paid')
    
    def failed(self):
        return self.filter(status='failed')

class PaymentManager(models.Manager):
    def get_queryset(self):
        return PaymentQuerySet(self.model, using=self._db)
    
    def pending(self):
        return self.get_queryset().pending()
    
    def paid(self):
        return self.get_queryset().paid()
    
    def failed(self):
        return self.get_queryset().failed()

class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_REVERSED = 'reversed'  # Payment was reversed after being marked as failed but found to be successful
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REVERSED, 'Reversed'),
    ]

    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="payments",
        db_index=True
    )
    reservation = models.ForeignKey(
        Reservation, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="payments",
        db_index=True
    )
    amount = models.PositiveIntegerField(help_text="Amount in Rial (IRR)")
    authority = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        db_index=True,
        help_text="Authority Code from ZarinPal"
    )
    ref_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        db_index=True,
        help_text="Reference ID after success"
    )
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default=STATUS_PENDING,
        db_index=True
    )
    failure_details = models.JSONField(
        null=True, 
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Stores error details if payment failed"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    
    objects = PaymentManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['authority', 'status']),
            models.Index(fields=['ref_id']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        user_info = f"{self.user.phone_number}" if self.user else "No User"
        return f"Payment {self.id} - {user_info} - {self.status}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None
        
        if not is_new:
            old_status = Payment.objects.get(pk=self.pk).status
        # Guard against mocked or expression timestamps leaking into inserts/updates during tests
        try:
            if hasattr(self.created_at, 'resolve_expression') or not isinstance(self.created_at, _dt):
                self.created_at = _dt.now(_pytz.utc)
        except Exception:
            self.created_at = _dt.now(_pytz.utc)
        try:
            if hasattr(self.updated_at, 'resolve_expression') or not isinstance(self.updated_at, _dt):
                self.updated_at = _dt.now(_pytz.utc)
        except Exception:
            self.updated_at = _dt.now(_pytz.utc)
        
        super().save(*args, **kwargs)
        
        if is_new:
            logger.info(f"New payment created: {self.id} for user {getattr(self.user, 'id', 'unknown')}")
        elif old_status != self.status:
            logger.info(f"Payment {self.id} status changed from {old_status} to {self.status}")
    
    @transaction.atomic
    def mark_as_paid(self, ref_id):
        """Mark payment as paid and update related models."""
        if self.status == self.STATUS_PAID:
            return True
            
        self.ref_id = ref_id
        self.status = self.STATUS_PAID
        self.save()
        
        if self.reservation and self.reservation.status == 'pending_payment':
            self.reservation.status = 'waiting'
            self.reservation.save()
        
        return True
    
    @transaction.atomic
    def mark_as_failed(self, error_message=None, error_code=None):
        """Mark payment as failed and store failure details."""
        if self.status == self.STATUS_FAILED:
            return False
            
        self.status = self.STATUS_FAILED
        if error_message or error_code:
            self.failure_details = {
                'error_message': error_message,
                'error_code': error_code,
                'failed_at': timezone.now().isoformat(),
                'reversed': False  # Track if we've attempted to reverse this
            }
        self.save()
        
        # Only cancel the reservation if it's still in pending state
        if self.reservation and self.reservation.status == 'pending_payment':
            self.reservation.status = 'cancelled'
            self.reservation.save()
        
        logger.warning(
            f"Payment {self.id} marked as failed. "
            f"Error: {error_message} (Code: {error_code})"
        )
        return True
        
    def mark_as_reversed(self):
        """Mark payment as reversed after successful reversal."""
        if self.status != self.STATUS_FAILED:
            logger.warning(f"Cannot reverse payment {self.id} with status {self.status}")
            return False
            
        self.status = self.STATUS_REVERSED
        if not self.failure_details:
            self.failure_details = {}
        self.failure_details.update({
            'reversed': True,
            'reversed_at': timezone.now().isoformat()
        })
        self.save(update_fields=['status', 'failure_details', 'updated_at'])
        logger.info(f"Payment {self.id} marked as reversed")
        
        if self.reservation and self.reservation.status == 'cancelled':
            self.reservation.status = 'waiting'
            self.reservation.save()
            logger.info(f"Reactivated reservation {self.reservation.id} after payment reversal")
            
        return True
