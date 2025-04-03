from rest_framework import serializers
from .models import TemplateMenu, TemplateMenuItem, DailyMenu, DailyMenuItem, TimeSlot
from django.db.models import Q
from rest_framework.response import Response
from rest_framework import status
import ast
from datetime import datetime, timedelta
from food.serializers import FoodSerializer
from food.models import Food

class TemplateMenuItemSerializer(serializers.ModelSerializer):
    food = FoodSerializer(read_only=True)
    class Meta:
        model = TemplateMenuItem
        fields = ['id', 'food','start_time', 'end_time', 'time_slot_count', 'time_slot_capacity', 'daily_capacity']

class TemplateMenuSerializer(serializers.ModelSerializer):
    items = TemplateMenuItemSerializer(many=True)

    class Meta:
        model = TemplateMenu
        fields = ['id', 'day', 'meal_type', 'items']

class CreateTemplateMenuItemSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = TemplateMenuItem
        fields = ['id', 'food','start_time', 'end_time', 'time_slot_count', 'time_slot_capacity', 'daily_capacity']


class CreateTemplateMenuSerializer(serializers.ModelSerializer):
    items = CreateTemplateMenuItemSerializer(many=True)

    class Meta:
        model = TemplateMenu
        fields = ['id', 'day', 'meal_type', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])

        template_menu = TemplateMenu.objects.filter(Q(day=validated_data["day"]) & Q(meal_type=validated_data["meal_type"]))
        if template_menu:
            template_menu = template_menu[0]
        else:
            template_menu = TemplateMenu.objects.create(
            day = validated_data["day"],
            meal_type = validated_data["meal_type"]
            )
        print(items_data)
        for item_data in items_data:
            print(item_data)
            TemplateMenuItem.objects.create(
                template_menu=template_menu,
                food_id = item_data.get('food').id,
                start_time=item_data.get('start_time'),
                end_time=item_data.get('end_time'),
                time_slot_count=item_data.get('time_slot_count'),
                time_slot_capacity=item_data.get('time_slot_capacity'),
                daily_capacity=item_data.get('daily_capacity'),
            )
        return template_menu
    
    def update(self, instance, validated_data):
        """Custom update to handle time_slot_capacity changes."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ['id', 'start_time', 'end_time', 'capacity']


class GetDailyMenuItemSerializer(serializers.ModelSerializer):
    time_slots = TimeSlotSerializer(many=True, read_only=True)
    food = FoodSerializer(read_only=True)

    class Meta:
        model = DailyMenuItem
        fields = ['id', 'food', 'start_time', 'end_time', 'time_slot_count', 'time_slot_capacity', 'is_available', 'time_slots', 'daily_capacity']

class CreateDailyMenuItemSerializer(serializers.ModelSerializer):
    time_slots = TimeSlotSerializer(many=True, read_only=True)

    class Meta:
        model = DailyMenuItem
        fields = ['id', 'food', 'start_time', 'end_time', 'time_slot_count', 'time_slot_capacity', 'is_available', 'time_slots', 'daily_capacity']


class CreateDailyMenuSerializer(serializers.ModelSerializer):
    items = CreateDailyMenuItemSerializer(many=True)

    def create(self, validated_data):
        daily_menu = DailyMenu.objects.filter(Q(date=validated_data["date"]) & Q(meal_type=validated_data["meal_type"]))
        if daily_menu:
            daily_menu = daily_menu[0]
        else:
            daily_menu = DailyMenu.objects.create(date=validated_data["date"],meal_type=validated_data["meal_type"])
        items_data = validated_data.pop('items', [])
        # Ensure items_data is a list of dictionaries
        if isinstance(items_data, str):
            try:
                items_data = ast.literal_eval(items_data)
            except:
                return Response(
                    {"error": "Invalid items data format"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        for item_data in items_data:

            # Set is_available to True by default if not provided
            is_available = item_data.get('is_available', True)
            
            daily_menu_item = DailyMenuItem.objects.create(
                daily_menu=daily_menu,
                food_id=item_data.get('food').id,
                start_time=item_data.get('start_time'),
                end_time=item_data.get('end_time'),
                time_slot_count=item_data.get('time_slot_count'),
                time_slot_capacity=item_data.get('time_slot_capacity'),
                daily_capacity=item_data.get('daily_capacity'),
                is_available=is_available
            )
            daily_menu_item.refresh_from_db()
            
            # Calculate time slots
            duration = (
                (daily_menu_item.end_time.hour * 60 + daily_menu_item.end_time.minute) -
                (daily_menu_item.start_time.hour * 60 + daily_menu_item.start_time.minute)
            )
            slot_duration = duration // daily_menu_item.time_slot_count
            
            # Create time slots
            for i in range(daily_menu_item.time_slot_count):
    
                start_time = (
                    (datetime.combine(datetime.today(), daily_menu_item.start_time) + 
                    timedelta(minutes=i * slot_duration)).time()
                )

                end_time = (
                    (datetime.combine(datetime.today(), daily_menu_item.start_time) + 
                    timedelta(minutes=(i * slot_duration)+slot_duration)).time()
                )
                
                TimeSlot.objects.create(
                    daily_menu_item=daily_menu_item,
                    start_time=start_time,
                    end_time=end_time,
                    capacity=daily_menu_item.time_slot_capacity
                )

        return daily_menu

    class Meta:
        model = DailyMenu
        fields = ['id', 'date', 'meal_type', 'items']


class GetDailyMenuSerializer(serializers.ModelSerializer):
    items = GetDailyMenuItemSerializer(many=True)

    class Meta:
        model = DailyMenu
        fields = ['id', 'date', 'meal_type', 'items']
