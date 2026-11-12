from rest_framework import serializers
from django.db import transaction
from .models import Reservation
from users.models import User
from food.models import Food
from menu.serializers import TimeSlotSerializer
from menu.models import TimeSlot, DailyMenuItem
from core.models import VoucherType
from core.serializers import VoucherTypeSerializer
from datetime import datetime
from django.utils import timezone
import pytz

# Define Iran's timezone
IRAN_TZ = pytz.timezone("Asia/Tehran")

class CreateReservationSerializer(serializers.ModelSerializer):
    time_slot = serializers.PrimaryKeyRelatedField(queryset=TimeSlot.objects.all())
    voucher_type = serializers.PrimaryKeyRelatedField(
        queryset=VoucherType.objects.filter(is_active=True),
        required=False,
        allow_null=True
    )
    has_extra_voucher = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = Reservation
        fields = ['food', 'time_slot', 'reserved_date', 'voucher_type', 'has_voucher', 'has_extra_voucher', 'meal_type']
        
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
        voucher_type = data.get('voucher_type')
        food = data.get('food')

        # Check trust score for voucher usage
        if user.trust_score < 0 and (has_voucher or voucher_type or has_extra_voucher):
            raise serializers.ValidationError(
                "امکان استفاده از ژتون یا فیش تخفیف با امتیاز اعتبار منفی وجود ندارد. سفارش با پرداخت آزاد امکان‌پذیر است."
            )

        # Validate voucher_type eligibility
        if voucher_type:
            if not voucher_type.is_active:
                raise serializers.ValidationError("The selected voucher type is inactive.")
            if food and not food.allowed_vouchers.filter(id=voucher_type.id).exists():
                raise serializers.ValidationError(
                    {"voucher_type": f"'{food.name}' cannot be purchased with {voucher_type.name}."}
                )
            
        # Check extra voucher validation
        if has_extra_voucher and food and not food.supports_extra_voucher:
            raise serializers.ValidationError(
                "This food item does not support extra vouchers"
            )

        # Ensure the time slot exists and has capacity
        if time_slot.capacity <= 0:
            raise serializers.ValidationError("The selected time slot is full. Please choose a different slot.")

        # Ensure the end_time of the time slot hasn't passed using Iran timezone
        iran_now = timezone.now().astimezone(IRAN_TZ)
        if reserved_date == iran_now.date() and time_slot.end_time <= iran_now.time():
            raise serializers.ValidationError("The selected time slot has already ended. Please choose a future time slot.")

        # Prevent duplicate active reservations (including pending_payment) for the same student, date, and meal type
        existing_reservation = Reservation.objects.filter(
            student=user, 
            reserved_date=reserved_date, 
            meal_type=meal_type
        ).exclude(status='cancelled').exists()
        if existing_reservation:
            raise serializers.ValidationError(
                "You already have an active or pending reservation for this date and meal type."
            )

        return data

    def create(self, validated_data):
        """
        Override create() to handle safe time slot capacity updates with database locking.
        """
        with transaction.atomic():
            user = self.context['request'].user
            reserved_date = validated_data['reserved_date']
            meal_type = validated_data['meal_type']

            # Acquire row-level locks on TimeSlot and DailyMenuItem to prevent concurrency race conditions
            time_slot = TimeSlot.objects.select_for_update().get(id=validated_data['time_slot'].id)
            daily_menu_item = DailyMenuItem.objects.select_for_update().get(id=time_slot.daily_menu_item_id)
            validated_data['time_slot'] = time_slot

            # Double-check capacity under row-level lock
            if time_slot.capacity <= 0:
                raise serializers.ValidationError("The selected time slot is full. Please choose a different slot.")

            if daily_menu_item.daily_capacity <= 0 or not daily_menu_item.is_available:
                raise serializers.ValidationError("This menu item is no longer available. Please choose a different item.")

            # Ensure time slot has not expired
            iran_now = timezone.now().astimezone(IRAN_TZ)
            if reserved_date == iran_now.date() and time_slot.end_time <= iran_now.time():
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
    voucher_type = VoucherTypeSerializer(read_only=True)
    voucher_discount_applied = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    trust_score = serializers.SerializerMethodField()
    trust_score_impact = serializers.IntegerField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id', 'student', 'food', 'time_slot', 'reserved_date', 'meal_type',
            'voucher_type', 'voucher_discount_applied', 'has_voucher', 'has_extra_voucher',
            'price', 'original_price', 'status', 'delivery_code',
            'created_at', 'updated_at', 'trust_score', 'trust_score_impact',
            'reservation_number'
        ]
        read_only_fields = ['price', 'original_price', 'delivery_code', 'reservation_number', 'status']
    
    def get_trust_score(self, obj):
        """Get the current trust score of the student."""
        return obj.student.trust_score if obj.student else 0