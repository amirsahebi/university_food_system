from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import TemplateMenu, TemplateMenuItem, DailyMenu, DailyMenuItem, TimeSlot
from .serializers import (
    CreateDailyMenuItemSerializer,
    CreateDailyMenuSerializer,
    CreateTemplateMenuItemSerializer,
    CreateTemplateMenuSerializer,
    GetDailyMenuItemSerializer,
    GetDailyMenuSerializer,
    TemplateMenuSerializer,
    TemplateMenuItemSerializer,
    TimeSlotSerializer
)
import ast
from university_food_system.permissions import IsAdminOnly, IsAdminOrReadOnly
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Prefetch
from django.utils import timezone
import pytz
from typing import Dict, Any, Optional

# Define Iran's timezone
IRAN_TZ = pytz.timezone("Asia/Tehran")


class TemplateMenuView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOnly]
    """View for managing template menus."""

    def get(self, request):
        template_menus = TemplateMenu.objects.prefetch_related('items').all()
        serializer = TemplateMenuSerializer(template_menus, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        print(request.data)
        serializer = CreateTemplateMenuSerializer(data=request.data)
        print(serializer.is_valid())
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TemplateMenuDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOnly]
    """View for updating and deleting template menu items."""

    def put(self, request, id):
        try:
            template_menu_item =  TemplateMenuItem.objects.get(id=id)
        except TemplateMenuItem.DoesNotExist:
            return Response({"error": "Template menu item not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreateTemplateMenuItemSerializer(template_menu_item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        try:
            template_menu_item = TemplateMenuItem.objects.get(id=id)
        except TemplateMenuItem.DoesNotExist:
            return Response({"error": "Template menu item not found"}, status=status.HTTP_404_NOT_FOUND)

        template_menu_item.delete()
        return Response({"message": "Template menu item deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class DailyMenuView(APIView):
    """
    View for managing daily menus.
    
    GET: Retrieve daily menu for a specific date and meal type
    POST: Create a new daily menu
    """
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get(self, request) -> Response:
        """
        Retrieve daily menu for a specific date and meal type.
        
        Args:
            request: HTTP request object containing query parameters:
                - date: Date in YYYY-MM-DD format
                - meal_type: Type of meal (lunch/dinner)
                
        Returns:
            Response: Daily menu data or error message
        """
        date = request.query_params.get('date')
        meal_type = request.query_params.get('meal_type')

        if not date or not meal_type:
            return Response(
                {"error": "Both date and meal_type are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get current Iran time
            current_iran_time = timezone.now().astimezone(IRAN_TZ)
            current_date = datetime.now().date()
            current_iran_time = current_iran_time.time()

            # Validate and parse requested date
            try:
                requested_date = datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate meal type
            if meal_type not in ['lunch', 'dinner']:
                return Response(
                    {"error": "Invalid meal type. Must be 'lunch' or 'dinner'"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if the requested date is in the past - only for non-admin users
            user = request.user
            if user.role != "admin" and requested_date < current_date:
                return Response(
                    {"error": "Cannot view past dates"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Optimize query with select_related and prefetch_related
            daily_menu = DailyMenu.objects.select_related().prefetch_related(
                Prefetch(
                    'items',
                    queryset=DailyMenuItem.objects.select_related('food').prefetch_related(
                        Prefetch(
                            'time_slots',
                            queryset=TimeSlot.objects.all() if user.role == "admin" 
                            else TimeSlot.objects.filter(end_time__gt=current_iran_time)
                        )
                    )
                )
            ).get(
                Q(date=date) & Q(meal_type=meal_type)
            )

            # For admin users, return all data
            serializer = GetDailyMenuSerializer(daily_menu, context={'request': request})
            return Response(serializer.data)

        except DailyMenu.DoesNotExist:
            return Response(
                {"error": "Daily menu not found for the specified date and meal type."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request) -> Response:
        """
        Create a new daily menu.
        
        Args:
            request: HTTP request object containing daily menu data
            
        Returns:
            Response: Created daily menu data or error message
        """
        serializer = CreateDailyMenuSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response(
                    {"error": f"Failed to create daily menu: {str(e)}"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class DailyMenuItemView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOnly]
    def get(self, request, pk):
        try:
            daily_menu_item = DailyMenuItem.objects.prefetch_related('time_slots').get(pk=pk)
            serializer = GetDailyMenuItemSerializer(daily_menu_item)
            return Response(serializer.data)
        except DailyMenuItem.DoesNotExist:
            return Response({"error": "DailyMenuItem not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            daily_menu_item = DailyMenuItem.objects.get(pk=pk)
            print(request.data)
            serializer = CreateDailyMenuItemSerializer(daily_menu_item, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except DailyMenuItem.DoesNotExist:
            return Response({"error": "DailyMenuItem not found"}, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, pk):
        try:
            daily_menu_item = DailyMenuItem.objects.get(pk=pk)
        except daily_menu_item.DoesNotExist:
            return Response({"error": "Template menu item not found"}, status=status.HTTP_404_NOT_FOUND)

        daily_menu_item.delete()
        return Response({"message": "Template menu item deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class ToggleDailyMenuItemAvailabilityView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOnly]
    """View for toggling the availability of a daily menu item."""

    def put(self, request, id):
        try:
            daily_menu_item = DailyMenuItem.objects.get(id=id)
        except DailyMenuItem.DoesNotExist:
            return Response({"error": "Daily menu item not found"}, status=status.HTTP_404_NOT_FOUND)

        daily_menu_item.is_available = not daily_menu_item.is_available
        daily_menu_item.save()
        return Response({"message": "Availability toggled", "is_available": daily_menu_item.is_available}, status=status.HTTP_200_OK)

class UseTemplateForDailyView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOnly]
    """View for using a template menu to create a daily menu."""

    def post(self, request):
        day = request.data.get('day')
        date = request.data.get('date')

        if not day or not date:
            return Response({"error": "Both day and date are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Find the template menu for the specified day
        try:
            template_menu = TemplateMenu.objects.get(day=day)
        except TemplateMenu.DoesNotExist:
            return Response({"error": "Template menu not found for the specified day."}, status=status.HTTP_404_NOT_FOUND)

        # Create or retrieve the daily menu for the given date and meal type
        daily_menu, created = DailyMenu.objects.get_or_create(date=date, meal_type=template_menu.meal_type)

        # Copy template menu items to daily menu items
        for item in template_menu.items.all():
            daily_menu_item = DailyMenuItem.objects.create(
                daily_menu=daily_menu,
                food=item.food,
                start_time=item.start_time,
                end_time=item.end_time,
                time_slot_count=item.time_slot_count,
                time_slot_capacity=item.time_slot_capacity,
                daily_capacity=item.daily_capacity,
                is_available=True
            )

            # Calculate and create time slots for each daily menu item
            duration = (
                (daily_menu_item.end_time.hour * 60 + daily_menu_item.end_time.minute) -
                (daily_menu_item.start_time.hour * 60 + daily_menu_item.start_time.minute)
            )
            slot_duration = duration // daily_menu_item.time_slot_count

            for i in range(daily_menu_item.time_slot_count):
                start_time = (
                    (datetime.combine(datetime.today(), daily_menu_item.start_time) +
                     timedelta(minutes=i * slot_duration)).time()
                )
                end_time = (
                    (datetime.combine(datetime.today(), daily_menu_item.start_time) +
                     timedelta(minutes=(i * slot_duration) + slot_duration)).time()
                )
                TimeSlot.objects.create(
                    daily_menu_item=daily_menu_item,
                    start_time=start_time,
                    end_time=end_time,
                    capacity=daily_menu_item.time_slot_capacity
                )

        return Response({"message": "Daily menu created successfully from template."}, status=status.HTTP_201_CREATED)
