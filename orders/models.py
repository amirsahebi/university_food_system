from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from food.models import Food
from core.models import Voucher
from menu.models import TimeSlot
import random
from django.db.models import Sum, F
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
User = get_user_model()

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('cancelled', 'Cancelled'),
        ('pending_payment', 'Pending Payment'),
        ('waiting', 'Waiting'),
        ('preparing', 'Preparing'),
        ('ready_to_pickup', 'Ready to Pickup'),
        ('picked_up', 'Picked Up'),
        ('not_picked_up', 'Not Picked Up'),
    ]

    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservations')
    food = models.ForeignKey(Food, on_delete=models.SET_NULL, null=True, blank=True)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.SET_NULL, null=True, blank=True)
    meal_type = models.CharField(max_length=10, choices=[('lunch', 'Lunch'), ('dinner', 'Dinner')])
    reserved_date = models.DateField()
    voucher_type = models.ForeignKey(
        'core.VoucherType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations',
        help_text='The specific voucher type used for this reservation'
    )
    voucher_discount_applied = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        help_text='Snapshot of voucher discount applied at the time of reservation'
    )
    has_voucher = models.BooleanField(default=False)
    has_extra_voucher = models.BooleanField(
        default=False,
        help_text='Whether this reservation uses an extra voucher'
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Original price before any vouchers applied'
    )
    trust_score_impact = models.IntegerField(
        default=0,
        help_text='Impact on user trust score from this reservation'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    delivery_code = models.CharField(max_length=6, blank=True, null=True)
    reservation_number = models.PositiveIntegerField(blank=True, null=True, help_text="Sequential number for each meal and day")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    def assign_reservation_number(self):
        """Assign a sequential reservation number for this meal type and date."""
        if not self.reservation_number:
            # Get the highest reservation number for this meal type and date
            highest = Reservation.objects.filter(
                meal_type=self.meal_type,
                reserved_date=self.reserved_date
            ).aggregate(models.Max('reservation_number'))
            
            # Start from 1 if no reservations exist for this meal/day
            current_highest = highest['reservation_number__max'] or 0
            
            # Assign the next number (max 9999)
            self.reservation_number = min(current_highest + 1, 9999)
    
    def generate_delivery_code(self):
        """Generate a unique 6-digit delivery code based on reservation number + random digits."""
        # Ensure we have a reservation number assigned
        if not self.reservation_number:
            self.assign_reservation_number()
            
        # First 4 digits: reservation number padded to 4 digits
        seq_part = str(self.reservation_number).zfill(4)
        
        # Last 2 digits: random digits for unpredictability
        random_part = str(random.SystemRandom().randint(0, 99)).zfill(2)
        
        # Combine to form a 6-digit delivery code
        self.delivery_code = seq_part + random_part
        

    def calculate_price(self):
        """Calculate the final price after applying vouchers."""
        if not hasattr(self, 'food') or not self.food:
            return 0
            
        price = float(self.food.price)
        self.original_price = price
        discount = 0.0

        # Priority 1: Multi-tier VoucherType
        if self.voucher_type:
            discount = float(self.voucher_type.discount_amount)
            self.has_voucher = True
        # Priority 2: Legacy boolean voucher
        elif self.has_voucher:
            voucher_price = float(Voucher.get_voucher_price())
            discount += voucher_price
            if self.has_extra_voucher and self.food.supports_extra_voucher:
                discount += voucher_price

        self.voucher_discount_applied = discount
        final_price = max(price - discount, 0)
        return final_price

    def update_trust_score(self):
        """Update user's trust score based on reservation status."""
        if not self.student or self.student.role != 'student':
            return
            
        # Only process status changes
        if not self.pk:  # New reservation
            return
            
        try:
            old_instance = Reservation.objects.get(pk=self.pk)
            if self.status == old_instance.status:
                return
        except Reservation.DoesNotExist:
            return
            
        # Handle trust score updates based on status changes
        if self.status == 'picked_up':
            # Award +1 trust score point per 100,000 Tomans of cumulative successful spending
            paid_amount = int(self.price or 0)
            if paid_amount > 0 and self.student_id:
                with transaction.atomic():
                    from users.models import User
                    student = User.objects.select_for_update().get(id=self.student_id)
                    student.total_spent = (student.total_spent or 0) + paid_amount
                    total_points_deserved = student.total_spent // 100000
                    already_awarded = student.loyalty_points_awarded or 0
                    points_to_award = max(0, total_points_deserved - already_awarded)
                    if points_to_award > 0:
                        student.loyalty_points_awarded = already_awarded + points_to_award
                        student.trust_score += points_to_award
                        self.trust_score_impact = points_to_award
                    else:
                        self.trust_score_impact = 0
                    student.trust_score_updated_at = timezone.now()
                    student.save(update_fields=['total_spent', 'loyalty_points_awarded', 'trust_score', 'trust_score_updated_at'])
                    self.student = student
            else:
                self.trust_score_impact = 0

        elif self.status == 'not_picked_up' and (self.has_voucher or self.voucher_type):
            # Negative impact for not picking up with voucher
            penalty = -10

            # Additional penalty for extra voucher
            if self.has_extra_voucher:
                penalty -= 10

            if self.student_id:
                with transaction.atomic():
                    from users.models import User
                    student = User.objects.select_for_update().get(id=self.student_id)
                    self.trust_score_impact = penalty
                    student.trust_score += penalty  # penalty is negative, decreases score
                    student.trust_score_updated_at = timezone.now()
                    student.save(update_fields=['trust_score', 'trust_score_updated_at'])
                    self.student = student
    
    def save(self, *args, **kwargs):
        # Calculate price if not already set
        if self.price is None or self.original_price is None:
            self.price = self.calculate_price()
            
        # Check if this is a new reservation (created_at is None)
        is_new = self._state.adding
        
        # If it's a new reservation and price is zero and voucher is applied, set status to waiting
        if is_new and self.price == 0 and (self.has_voucher or self.voucher_type):
            self.status = 'waiting'
            
        # Validate extra voucher usage
        if self.has_extra_voucher and not self.has_voucher:
            raise ValueError("Cannot use extra voucher without a regular voucher")
            
        if self.has_extra_voucher and not (hasattr(self, 'food') and self.food and self.food.supports_extra_voucher):
            raise ValueError("This food item does not support extra vouchers")
            
        # Check if user can use vouchers based on trust score
        if self.student and self.student.trust_score < 0 and (self.has_voucher or self.has_extra_voucher or self.voucher_type):
            raise ValueError("Cannot use vouchers with a negative trust score")

        # Validate voucher eligibility for the selected food item
        if self.voucher_type and hasattr(self, 'food') and self.food:
            if not self.food.allowed_vouchers.filter(id=self.voucher_type.id).exists():
                raise ValueError(f"Food '{self.food.name}' does not allow voucher type '{self.voucher_type.name}'")
        
        # Assign reservation number if not already assigned
        if not self.reservation_number:
            self.assign_reservation_number()
        
        # Generate delivery code if not already generated
        if not self.delivery_code:
            self.generate_delivery_code()
            
        # Save the reservation first to get an ID
        super().save(*args, **kwargs)
        
        # Update trust score if status changed
        self.update_trust_score()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['delivery_code', 'reserved_date', 'meal_type']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['student', 'reserved_date', 'meal_type']),
            models.Index(fields=['reserved_date', 'meal_type']),
        ]

    def __str__(self):
        return f"{self.student.phone_number} - {self.food.name} ({self.status})"
