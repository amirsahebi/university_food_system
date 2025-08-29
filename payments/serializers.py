from rest_framework import serializers
from django.utils import timezone
from django.db.models import Q
from .models import Payment
from users.serializers import UserSerializer
from orders.serializers import ReservationSerializer
from core.logging_utils import get_logger

logger = get_logger(__name__)

class PaymentRequestSerializer(serializers.Serializer):
    callback_url = serializers.URLField()
    reservation_id = serializers.IntegerField()
    
    def validate_reservation_id(self, value):
        logger.debug(f"Validating reservation_id: {value}")
        return value
    
    def validate_callback_url(self, value):
        logger.debug(f"Validating callback_url: {value}")
        return value

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
    
    def create(self, validated_data):
        logger.info(f"Creating new payment: {validated_data}")
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        logger.info(f"Updating payment {instance.id}: {validated_data}")
        return super().update(instance, validated_data)

# Admin Serializers
class AdminPaymentSerializer(serializers.ModelSerializer):
    """Serializer for admin to view payment details."""
    user = UserSerializer(read_only=True)
    reservation = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'reservation', 'amount', 'status',
            'authority', 'ref_id', 'created_at', 'updated_at', 'failure_details'
        ]
        read_only_fields = ('created_at', 'updated_at', 'failure_details')
    
    def get_reservation(self, obj):
        from orders.serializers import ReservationSerializer  # Avoid circular import
        if obj.reservation:
            return ReservationSerializer(obj.reservation).data
        return None

class PaymentFilterSerializer(serializers.Serializer):
    """Serializer for payment filtering query parameters."""
    user_id = serializers.IntegerField(required=False)
    status = serializers.ChoiceField(
        choices=Payment.STATUS_CHOICES, 
        required=False
    )
    min_amount = serializers.IntegerField(required=False, min_value=0)
    max_amount = serializers.IntegerField(required=False, min_value=0)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    search = serializers.CharField(required=False, help_text="Search in user phone, authority, or ref_id")
    
    def validate(self, data):
        """Validate that start_date is before end_date if both are provided."""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date.'
                })
        return data
