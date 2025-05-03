from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Reservation, TimeSlot
from .serializers import ReservationSerializer, CreateReservationSerializer
from university_food_system.permissions import (
    IsStudentOrAdmin,
    IsChefOrReceiverOrAdmin,
    IsReceiverOrAdmin,
)
from django.db.models import Q
import pytz
from datetime import datetime

class ReceiverOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsReceiverOrAdmin]

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
    permission_classes = [IsAuthenticated, IsReceiverOrAdmin]

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
            # Create the reservation (capacity updates will be handled by signals)
            reservation = serializer.save(student=request.user)
            
            # The delivery code will be automatically generated in the save method
            # No need to call generate_delivery_code() explicitly
            
            # Get the full reservation data for response
            response_data = ReservationSerializer(reservation).data
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_406_NOT_ACCEPTABLE)


class PendingOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsReceiverOrAdmin]

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

class RetrieveReservationByDeliveryCodeView(APIView):
    permission_classes = [IsAuthenticated, IsReceiverOrAdmin]

    def post(self, request):
        """Retrieve reservation details by delivery code."""
        delivery_code = request.data.get('delivery_code')
        meal_type = request.data.get('meal_type')
        date = request.data.get('date')
        
        # Validate required fields
        missing_fields = []
        if not delivery_code:
            missing_fields.append("delivery_code")
        if not meal_type:
            missing_fields.append("meal_type")
        if not date:
            missing_fields.append("date")
            
        if missing_fields:
            return Response(
                {"error": f"Required fields missing: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate delivery code format (must be 6 digits)
        if not (delivery_code.isdigit() and len(delivery_code) == 6):
            return Response({"error": "Delivery code must be a 6-digit number"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Validate meal_type
        if meal_type not in ['lunch', 'dinner']:
            return Response({"error": "meal_type must be either 'lunch' or 'dinner'"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
            
        
        try:
            # Build query with all required filters
            reservation = Reservation.objects.get(
                delivery_code=delivery_code,
                meal_type=meal_type,
                reserved_date=parsed_date
            )
            data = ReservationSerializer(reservation).data        
            return Response(data, status=status.HTTP_200_OK)
            
        except Reservation.DoesNotExist:
            return Response({"error": "Invalid or unknown delivery code"}, status=status.HTTP_404_NOT_FOUND)

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


class NotPickedUpOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsReceiverOrAdmin]

    def patch(self, request, id):
        """Mark an order as not picked up."""
        try:
            order = Reservation.objects.get(id=id)
        except Reservation.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        if order.status != 'ready_to_pickup':
            return Response({"error": "Order is not ready for pickup"}, status=status.HTTP_400_BAD_REQUEST)

        order.status = 'not_picked_up'
        order.save()
        serializer = ReservationSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CancelReservationView(APIView):
    permission_classes = [IsAuthenticated, IsStudentOrAdmin]

    def delete(self, request, id):
        """Allow a user to cancel their reservation if status is pending_payment."""
        try:
            reservation = Reservation.objects.get(id=id)
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found."}, status=status.HTTP_404_NOT_FOUND)

        if reservation.student != request.user:
            return Response({"error": "You can only cancel your own reservation."}, status=status.HTTP_403_FORBIDDEN)

        if reservation.status != 'pending_payment':
            return Response({"error": "Reservation can only be cancelled if status is pending_payment."}, status=status.HTTP_400_BAD_REQUEST)

        reservation.status = 'cancelled'
        reservation.save(update_fields=["status"])
        return Response({"success": "Reservation cancelled."}, status=status.HTTP_200_OK)