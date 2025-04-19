from rest_framework import serializers
from .models import Payment
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
