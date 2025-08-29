from rest_framework import serializers
from .models import Food, FoodCategory


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
    # Explicitly define the field to ensure proper handling
    supports_extra_voucher = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=False,  # Set a default value if needed
    )
    
    class Meta:
        model = Food
        fields = [
            'id', 'name', 'description', 'price', 'image', 'image_url', 
            'category_id', 'category_name', 'supports_extra_voucher',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_image_url(self, obj):
        if obj.image:
            return self.context['request'].build_absolute_uri(obj.image.url)
        return None
        
    def get_category_name(self, obj):
        if obj.category:
            return obj.category.name
        return None

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero")
        return value
