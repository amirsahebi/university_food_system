from rest_framework import serializers
from .models import Food

class FoodSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Food
        fields = ['id', 'name', 'description', 'price', 'image', 'image_url', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_image_url(self, obj):
        if obj.image:
            return self.context['request'].build_absolute_uri(obj.image.url)
        return None

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero")
        return value
