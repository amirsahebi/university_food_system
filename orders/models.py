from django.db import models
from django.contrib.auth import get_user_model
from food.models import Food
from core.models import Voucher
from menu.models import TimeSlot
import random
User = get_user_model()

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('cancelled', 'Cancelled'),
        ('pending_payment', 'Pending Payment'),
        ('waiting', 'Waiting'),
        ('preparing', 'Preparing'),
        ('ready_to_pickup', 'Ready to Pickup'),
        ('picked_up', 'Picked Up'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations')
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    meal_type = models.CharField(max_length=10, choices=[('lunch', 'Lunch'), ('dinner', 'Dinner')])
    reserved_date = models.DateField()
    has_voucher = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    delivery_code = models.CharField(max_length=6, blank=True, null=True, unique=True)
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
        global_voucher_price = Voucher.get_voucher_price()
        return self.food.price-global_voucher_price if self.has_voucher else self.food.price

    def save(self, *args, **kwargs):
        # Calculate price if not already set
        if not self.price:
            self.price = self.calculate_price()
        
            # If price is zero and voucher is applied, set status to waiting
            if self.price == 0 and self.has_voucher:
                self.status = 'waiting'
        
        # Assign reservation number if not already assigned
        if not self.reservation_number:
            self.assign_reservation_number()
        
        # Generate delivery code if not already generated
        if not self.delivery_code:
            self.generate_delivery_code()
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.phone_number} - {self.food.name} ({self.status})"
