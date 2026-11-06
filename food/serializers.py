from rest_framework import serializers
from .models import Food, FoodCategory
from core.models import VoucherType
from core.serializers import VoucherTypeSerializer


class FoodCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodCategory
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class FoodSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    category_id = serializers.PrimaryKeyRelatedField(
        source='category',
        queryset=FoodCategory.objects.all(),
        required=False,
        allow_null=True
    )
    allowed_vouchers = VoucherTypeSerializer(many=True, read_only=True)
    allowed_voucher_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=VoucherType.objects.all(),
        source='allowed_vouchers',
        required=False,
        write_only=True
    )
    supports_extra_voucher = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=False,
    )
    
    class Meta:
        model = Food
        fields = [
            'id', 'name', 'description', 'price', 'image', 'image_url', 
            'category_id', 'category_name', 'allowed_vouchers', 'allowed_voucher_ids',
            'supports_extra_voucher', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def to_internal_value(self, data):
        # Robust handling of allowed_vouchers across JSON payloads and multipart/form-data QueryDict
        import json
        if hasattr(data, 'getlist'):
            mutable_data = data.copy()
            voucher_vals = mutable_data.getlist('allowed_vouchers') or mutable_data.getlist('allowed_voucher_ids')
            parsed_ids = []
            for v in voucher_vals:
                if isinstance(v, str) and v.startswith('[') and v.endswith(']'):
                    try:
                        parsed_ids.extend(json.loads(v))
                    except:
                        pass
                elif isinstance(v, str) and ',' in v:
                    parsed_ids.extend([x.strip() for x in v.split(',') if x.strip()])
                elif v:
                    parsed_ids.append(v)
            if parsed_ids:
                mutable_data.setlist('allowed_voucher_ids', parsed_ids)
            data = mutable_data
        elif isinstance(data, dict):
            raw_vouchers = data.get('allowed_vouchers') if 'allowed_vouchers' in data else data.get('allowed_voucher_ids')
            if raw_vouchers is not None:
                data = data.copy()
                if isinstance(raw_vouchers, str):
                    if raw_vouchers.startswith('[') and raw_vouchers.endswith(']'):
                        try:
                            raw_vouchers = json.loads(raw_vouchers)
                        except:
                            raw_vouchers = []
                    elif ',' in raw_vouchers:
                        raw_vouchers = [x.strip() for x in raw_vouchers.split(',') if x.strip()]
                    elif raw_vouchers.strip():
                        raw_vouchers = [raw_vouchers.strip()]
                data['allowed_voucher_ids'] = raw_vouchers
        return super().to_internal_value(data)

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
        
    def get_category_name(self, obj):
        if obj.category:
            return obj.category.name
        return None

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero")
        return value
