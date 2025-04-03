from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Reservation, TimeSlot
from .serializers import ReservationSerializer, CreateReservationSerializer
from university_food_system.permissions import (
    IsChefOrAdmin,
    IsStudentOrAdmin,
    IsChefOrReceiverOrAdmin,
    IsReceiverOrAdmin,
)
from django.db.models import Q
import pytz
from datetime import datetime

class ChefOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsChefOrAdmin]

    def get(self, request):
        """Retrieve all orders for chefs to prepare."""
        reserved_date = request.query_params.get('reserved_date')
        meal_type = request.query_params.get('meal_type')

        if not reserved_date or not meal_type:
            return Response({"error": "Both date and meal_type are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        orders = Reservation.objects.filter(Q(reserved_date=reserved_date) & Q(meal_type=meal_type))
        serializer = ReservationSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateOrderStatusView(APIView):
    permission_classes = [IsAuthenticated, IsChefOrAdmin]

    def patch(self, request, id):
        """Update the status of an order."""
        try:
            order = Reservation.objects.get(id=id)
        except Reservation.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        status_update = request.data.get('status')
        if status_update not in dict(Reservation.STATUS_CHOICES):
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)

        order.status = status_update
        order.save()
        serializer = ReservationSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PlaceOrderView(APIView):
    permission_classes = [IsAuthenticated, IsStudentOrAdmin]

    def post(self, request):
        """Place a new order."""
        serializer = CreateReservationSerializer(data=request.data, context={'request': request})
        print(request.data)
        if serializer.is_valid():
            # Get the time slot and check its capacity
            time_slot_id = request.data.get('time_slot')
            try:
                time_slot = TimeSlot.objects.get(id=time_slot_id)
                
                # Check if time slot has expired
                iran_tz = pytz.timezone('Asia/Tehran')
                current_iran_time = datetime.now(iran_tz).time()
                
                if time_slot.end_time <= current_iran_time:
                    return Response(
                        {"error": "This time slot has expired"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if time_slot.capacity <= 0:
                    return Response(
                        {"error": "This time slot is full"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check daily menu item capacity
                daily_menu_item = time_slot.daily_menu_item
                if daily_menu_item.daily_capacity <= 0:
                    return Response(
                        {"error": "This food item is out of stock"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except TimeSlot.DoesNotExist:
                return Response(
                    {"error": "Time slot not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Create the reservation (capacity updates will be handled by signals)
            reservation = serializer.save(student=request.user)
            
            # Generate QR code and save
            reservation.generate_qr_code()
            reservation.save()
            
            return Response(ReservationSerializer(reservation).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PendingOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsChefOrReceiverOrAdmin]

    def get(self, request):
        """Retrieve all pending orders."""
        orders = Reservation.objects.filter(status='waiting')
        serializer = ReservationSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeliverOrderView(APIView):
    permission_classes = [IsAuthenticated, IsReceiverOrAdmin]

    def patch(self, request, id):
        """Mark an order as delivered."""
        try:
            order = Reservation.objects.get(id=id)
        except Reservation.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        if order.status != 'ready_to_pickup':
            return Response({"error": "Order is not ready for delivery"}, status=status.HTTP_400_BAD_REQUEST)

        order.status = 'picked_up'
        order.save()
        serializer = ReservationSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsStudentOrAdmin]

    def get(self, request):
        """Retrieve all orders for the current student."""
        orders = Reservation.objects.filter(student=request.user)
        serializer = ReservationSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class RetrieveReservationByQRCodeView(APIView):
    permission_classes = [IsAuthenticated, IsReceiverOrAdmin]

    def post(self, request):
        """Retrieve reservation details by encrypted QR code data."""
        encrypted_qr_code_data = request.data.get('qr_code_data')
        print(request.data)

        if not encrypted_qr_code_data:
            return Response({"error": "QR code data is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Decrypt QR code data
            reservation = Reservation.objects.all()[0]  # Dummy instance for accessing decrypt_data method
            decrypted_data = reservation.decrypt_data(encrypted_qr_code_data)

            # Parse decrypted data to get the reservation ID
            reservation_id = int(decrypted_data.split(":")[1].split(",")[0].strip())
            reservation = Reservation.objects.get(id=reservation_id)
        except (ValueError, IndexError, Reservation.DoesNotExist):
            return Response({"error": "Invalid or unknown QR code data"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReservationSerializer(reservation)
        return Response(serializer.data, status=status.HTTP_200_OK)

class PickedUpOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsReceiverOrAdmin]

    def get(self, request):
        """Retrieve all picked-up orders for a specific date and meal type."""
        reserved_date = request.query_params.get('reserved_date')
        meal_type = request.query_params.get('meal_type')

        if not reserved_date or not meal_type:
            return Response(
                {"error": "Both date and meal_type are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        orders = Reservation.objects.filter(
            Q(status='picked_up') & Q(reserved_date=reserved_date) & Q(meal_type=meal_type)
        )
        serializer = ReservationSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ReadyToPickupOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsChefOrReceiverOrAdmin]

    def get(self, request):
        """Retrieve all ready-to-pickup orders for a specific date and meal type."""
        reserved_date = request.query_params.get('reserved_date')
        meal_type = request.query_params.get('meal_type')

        if not reserved_date or not meal_type:
            return Response(
                {"error": "Both date and meal_type are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        orders = Reservation.objects.filter(
            Q(status='ready_to_pickup') & Q(reserved_date=reserved_date) & Q(meal_type=meal_type)
        )
        print(orders)
        serializer = ReservationSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)