from rest_framework import serializers
from .models import Voucher, VoucherType


class VoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voucher
        fields = ['price']


class VoucherTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherType
        fields = ['id', 'code', 'name', 'discount_amount', 'is_active', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
