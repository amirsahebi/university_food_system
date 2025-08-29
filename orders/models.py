from django.db import models
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
        
        # Apply regular voucher if applicable
        if self.has_voucher:
            price -= float(Voucher.get_voucher_price())
            
            # Apply extra voucher if applicable (same value as regular voucher)
            if self.has_extra_voucher and self.food.supports_extra_voucher:
                price -= float(Voucher.get_voucher_price())
        
        return max(price, 0)  # Ensure price doesn't go below zero

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
            # Positive impact for picking up food
            points = int(self.price / 10000)  # +1 point per 10,000 tomans
            self.trust_score_impact = points
            self.student.trust_score += points
            self.student.trust_score_updated_at = timezone.now()
            self.student.save()
            
        elif self.status == 'not_picked_up' and self.has_voucher:
            # Negative impact for not picking up with voucher
            penalty = -10
            
            # Additional penalty for extra voucher
            if self.has_extra_voucher:
                penalty -= 10
                
            self.trust_score_impact = penalty
            self.student.trust_score += penalty  # penalty is negative, so this decreases the score
            self.student.trust_score_updated_at = timezone.now()
            self.student.save()
    
    def save(self, *args, **kwargs):
        # Calculate price if not already set
        if not self.price or not self.original_price:
            self.price = self.calculate_price()
            
        # Check if this is a new reservation (created_at is None)
        is_new = self._state.adding
        
        # If it's a new reservation and price is zero and voucher is applied, set status to waiting
        if is_new and self.price == 0 and self.has_voucher:
            self.status = 'waiting'
            
        # Validate extra voucher usage
        if self.has_extra_voucher and not self.has_voucher:
            raise ValueError("Cannot use extra voucher without a regular voucher")
            
        if self.has_extra_voucher and not (hasattr(self, 'food') and self.food and self.food.supports_extra_voucher):
            raise ValueError("This food item does not support extra vouchers")
            
        # Check if user can use vouchers based on trust score
        if self.student and self.student.trust_score < 0 and (self.has_voucher or self.has_extra_voucher):
            raise ValueError("Cannot use vouchers with a negative trust score")
        
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

    def __str__(self):
        return f"{self.student.phone_number} - {self.food.name} ({self.status})"
