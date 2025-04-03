from rest_framework import serializers
from orders.models import Order


class ReservationLogSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    food = serializers.CharField(source='food.name')

    class Meta:
        model = Order
        fields = ['id', 'student', 'food', 'status', 'created_at', 'updated_at']

    def get_student(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class DailyOrderCountSerializer(serializers.Serializer):
    day = serializers.DateField()
    order_count = serializers.IntegerField()
