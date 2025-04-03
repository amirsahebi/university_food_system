from rest_framework import serializers
from .models import Payment

class PaymentRequestSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1000)  # Min 1000 Rials
    callback_url = serializers.URLField()
    reservation_id = serializers.IntegerField()

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
