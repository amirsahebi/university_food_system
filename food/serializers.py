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
    allowed_extra_vouchers = VoucherTypeSerializer(many=True, read_only=True)
    allowed_extra_voucher_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=VoucherType.objects.all(),
        source='allowed_extra_vouchers',
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
            'allowed_extra_vouchers', 'allowed_extra_voucher_ids',
            'supports_extra_voucher', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def to_internal_value(self, data):
        # Robust handling of allowed_vouchers and allowed_extra_vouchers across JSON payloads and multipart/form-data QueryDict
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

            extra_voucher_vals = mutable_data.getlist('allowed_extra_vouchers') or mutable_data.getlist('allowed_extra_voucher_ids')
            parsed_extra_ids = []
            for v in extra_voucher_vals:
                if isinstance(v, str) and v.startswith('[') and v.endswith(']'):
                    try:
                        parsed_extra_ids.extend(json.loads(v))
                    except:
                        pass
                elif isinstance(v, str) and ',' in v:
                    parsed_extra_ids.extend([x.strip() for x in v.split(',') if x.strip()])
                elif v:
                    parsed_extra_ids.append(v)
            if parsed_extra_ids:
                mutable_data.setlist('allowed_extra_voucher_ids', parsed_extra_ids)
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

            raw_extra_vouchers = data.get('allowed_extra_vouchers') if 'allowed_extra_vouchers' in data else data.get('allowed_extra_voucher_ids')
            if raw_extra_vouchers is not None:
                if not isinstance(data, dict) or not hasattr(data, 'copy'):
                    data = dict(data)
                else:
                    data = data.copy()
                if isinstance(raw_extra_vouchers, str):
                    if raw_extra_vouchers.startswith('[') and raw_extra_vouchers.endswith(']'):
                        try:
                            raw_extra_vouchers = json.loads(raw_extra_vouchers)
                        except:
                            raw_extra_vouchers = []
                    elif ',' in raw_extra_vouchers:
                        raw_extra_vouchers = [x.strip() for x in raw_extra_vouchers.split(',') if x.strip()]
                    elif raw_extra_vouchers.strip():
                        raw_extra_vouchers = [raw_extra_vouchers.strip()]
                data['allowed_extra_voucher_ids'] = raw_extra_vouchers
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

    def validate(self, attrs):
        price = attrs.get('price')
        if price is None and self.instance:
            price = self.instance.price

        allowed_vouchers = attrs.get('allowed_vouchers')
        if allowed_vouchers is None and self.instance:
            allowed_vouchers = list(self.instance.allowed_vouchers.all())

        allowed_extra_vouchers = attrs.get('allowed_extra_vouchers')
        if allowed_extra_vouchers is None and self.instance:
            allowed_extra_vouchers = list(self.instance.allowed_extra_vouchers.all())

        supports_extra_voucher = attrs.get('supports_extra_voucher')
        if supports_extra_voucher is None and self.instance:
            supports_extra_voucher = self.instance.supports_extra_voucher

        if price:
            # 1. Single regular voucher discount cannot exceed food price
            if allowed_vouchers:
                for v1 in allowed_vouchers:
                    if v1.discount_amount > price:
                        raise serializers.ValidationError({
                            'allowed_voucher_ids': (
                                f"تخفیف ژتون «{v1.name}» ({v1.discount_amount:,.0f} تومان) "
                                f"نمی‌تواند از قیمت کل غذا ({price:,.0f} تومان) بیشتر باشد."
                            )
                        })

            # 2. If extra voucher is enabled, validate extra vouchers and dual combinations
            if supports_extra_voucher:
                if allowed_extra_vouchers:
                    for v2 in allowed_extra_vouchers:
                        if v2.discount_amount > price:
                            raise serializers.ValidationError({
                                'allowed_extra_voucher_ids': (
                                    f"تخفیف ژتون اضافه «{v2.name}» ({v2.discount_amount:,.0f} تومان) "
                                    f"نمی‌تواند از قیمت کل غذا ({price:,.0f} تومان) بیشتر باشد."
                                )
                            })

                if allowed_vouchers and allowed_extra_vouchers:
                    for v1 in allowed_vouchers:
                        for v2 in allowed_extra_vouchers:
                            if (v1.discount_amount + v2.discount_amount) > price:
                                raise serializers.ValidationError({
                                    'allowed_extra_voucher_ids': (
                                        f"مجموع تخفیف فیش اول ({v1.name}: {v1.discount_amount:,.0f} تومان) "
                                        f"و فیش اضافه ({v2.name}: {v2.discount_amount:,.0f} تومان) "
                                        f"برابر {(v1.discount_amount + v2.discount_amount):,.0f} تومان است "
                                        f"که از قیمت غذا ({price:,.0f} تومان) بیشتر می‌شود."
                                    )
                                })
        return attrs

    def update(self, instance, validated_data):
        supports_extra = validated_data.get('supports_extra_voucher', instance.supports_extra_voucher)
        instance = super().update(instance, validated_data)
        if not supports_extra:
            instance.allowed_extra_vouchers.clear()
        return instance
