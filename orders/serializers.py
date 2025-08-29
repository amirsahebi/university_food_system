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
    has_extra_voucher = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = Reservation
        fields = ['food', 'time_slot', 'reserved_date', 'has_voucher', 'has_extra_voucher', 'meal_type']
        
    def validate_has_extra_voucher(self, value):
        """Validate that extra voucher can only be used with a regular voucher."""
        if value and not self.initial_data.get('has_voucher'):
            raise serializers.ValidationError("Cannot use extra voucher without a regular voucher")
        return value
        
    def validate(self, data):
        """
        Custom validation logic for reservations with trust score and voucher checks.
        """
        time_slot = data.get('time_slot')  # Now correctly retrieves the object
        reserved_date = data.get('reserved_date')
        meal_type = data.get('meal_type')
        user = self.context['request'].user
        has_voucher = data.get('has_voucher', False)
        has_extra_voucher = data.get('has_extra_voucher', False)
        food = data.get('food')

        # Check trust score for voucher usage
        if user.trust_score < 0 and has_voucher:
            raise serializers.ValidationError(
                "Cannot use vouchers with a negative trust score"
            )
            
        # Check extra voucher validation
        if has_extra_voucher and food and not food.supports_extra_voucher:
            raise serializers.ValidationError(
                "This food item does not support extra vouchers"
            )

        # Ensure the time slot exists and has capacity
        if time_slot.capacity <= 0:
            raise serializers.ValidationError("The selected time slot is full. Please choose a different slot.")

        # Ensure the end_time of the time slot hasn't passed
        current_time = datetime.now().time()
        if reserved_date == datetime.today().date() and time_slot.end_time <= current_time:
            raise serializers.ValidationError("The selected time slot has already ended. Please choose a future time slot.")

        # Prevent duplicate reservations for the same student, date, and meal type, except those in cancelled or pending_payment state
        if Reservation.objects.filter(student=user, reserved_date=reserved_date, meal_type=meal_type).exclude(status__in=['cancelled', 'pending_payment']).exists():
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
    trust_score = serializers.SerializerMethodField()
    trust_score_impact = serializers.IntegerField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id', 'student', 'food', 'time_slot', 'reserved_date', 'meal_type',
            'has_voucher', 'has_extra_voucher', 'price', 'status', 'delivery_code',
            'created_at', 'updated_at', 'trust_score', 'trust_score_impact',
            'reservation_number'
        ]
        read_only_fields = ['price', 'delivery_code', 'reservation_number', 'status']
    
    def get_trust_score(self, obj):
        """Get the current trust score of the student."""
        return obj.student.trust_score if obj.student else 0