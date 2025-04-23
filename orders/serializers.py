from rest_framework import serializers
from .models import Reservation
from users.models import User
from food.models import Food
from menu.serializers import TimeSlotSerializer

from rest_framework import serializers
from django.db import transaction
from .models import Reservation
from menu.models import TimeSlot
from datetime import datetime
from django.utils import timezone
import pytz

# Define Iran's timezone
IRAN_TZ = pytz.timezone("Asia/Tehran")

class CreateReservationSerializer(serializers.ModelSerializer):
    time_slot = serializers.PrimaryKeyRelatedField(queryset=TimeSlot.objects.all())

    class Meta:
        model = Reservation
        fields = ['food', 'time_slot', 'reserved_date', 'has_voucher', 'meal_type']

    def validate(self, data):
        """
        Custom validation logic for reservations.
        """
        time_slot = data.get('time_slot')  # Now correctly retrieves the object
        reserved_date = data.get('reserved_date')
        meal_type = data.get('meal_type')
        student = self.context['request'].user

        # Ensure the time slot exists and has capacity
        if time_slot.capacity <= 0:
            raise serializers.ValidationError("The selected time slot is full. Please choose a different slot.")
        

        # Ensure the end_time of the time slot hasn't passed
        current_time = datetime.now().time()
        if reserved_date == datetime.today().date() and time_slot.end_time <= current_time:
            raise serializers.ValidationError("The selected time slot has already ended. Please choose a future time slot.")
        

        # Prevent duplicate reservations for the same student, date, and meal type, except those in cancelled or pending_payment state
        if Reservation.objects.filter(student=student, reserved_date=reserved_date, meal_type=meal_type).exclude(status__in=['cancelled', 'pending_payment']).exists():
            raise serializers.ValidationError(
                "You already have a reservation for this date and meal type."
            )

        return data

    def create(self, validated_data):
        """
        Override create() to handle safe time slot capacity updates.
        Also updates daily menu item capacity and availability status.
        """
        with transaction.atomic():  # Prevents race conditions
            time_slot = validated_data['time_slot']
            daily_menu_item = time_slot.daily_menu_item

            # Double-check time slot capacity inside the transaction
            if time_slot.capacity <= 0:
                raise serializers.ValidationError("The selected time slot is full. Please choose a different slot.")

            # Double-check daily menu item capacity inside the transaction
            if daily_menu_item.daily_capacity <= 0 or not daily_menu_item.is_available:
                raise serializers.ValidationError("This menu item is no longer available. Please choose a different item.")

            # Ensure the end_time hasn't passed again inside transaction
            # Get current time in Iran timezone
            iran_now = timezone.now().astimezone(IRAN_TZ)
            current_iran_time = iran_now.time()
            
            if validated_data['reserved_date'] == datetime.today().date() and time_slot.start_time <= current_iran_time:
                raise serializers.ValidationError("The selected time slot has already ended. Please choose a future time slot.")

            return super().create(validated_data)

        

class UserLessSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'phone_number', 'student_number', 'first_name', 'last_name']

class FoodLessSerializer(serializers.ModelSerializer):

    class Meta:
        model = Food
        fields = ['id', 'name', 'description', 'price']

    
class ReservationSerializer(serializers.ModelSerializer):
    time_slot = TimeSlotSerializer()
    student = UserLessSerializer()
    food = FoodLessSerializer()

    class Meta:
        model = Reservation
        fields = ['id', 'student', 'food', 'time_slot', 'meal_type', 'reserved_date', 'has_voucher', 'price', 'status', 'reservation_number', 'delivery_code', 'created_at', 'updated_at']
        read_only_fields = ['price', 'delivery_code']