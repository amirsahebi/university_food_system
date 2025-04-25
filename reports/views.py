from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from orders.models import Reservation
from django.db.models import Count, Q
from django.utils.timezone import now
from datetime import timedelta


class ReservationLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve logs of reservations for the last 3 days.
        """
        today = now().date()
        start_date = today - timedelta(days=3)

        reservations = Reservation.objects.select_related('student', 'food')\
            .filter(
                created_at__date__range=[start_date, today],
                status__in=['waiting', 'preparing', 'ready_to_pickup', 'picked_up']
            )\
            .order_by('-created_at')

        logs = [
            {
                "id": reservation.id,
                "student": f"{reservation.student.first_name} {reservation.student.last_name}",
                "food": reservation.food.name,
                "status": reservation.status,
                "reserved_date": reservation.reserved_date,
                "created_at": reservation.created_at,
                "updated_at": reservation.updated_at,
            }
            for reservation in reservations
        ]
        return Response(logs, status=status.HTTP_200_OK)


class DailyOrderCountsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve daily counts of orders for the last 7 days.
        """
        today = now().date()
        start_date = today - timedelta(days=7)

        daily_counts = (
            Reservation.objects
            .filter(
                reserved_date__date__range=[start_date, today],
                status__in=['waiting', 'preparing', 'ready_to_pickup', 'picked_up']
            )
            .extra(select={'date': "date(created_at)"})
            .values('date')
            .annotate(
                order_count=Count('id'),
                picked_up_count=Count('id', filter=Q(status='picked_up'))
            )
            .order_by('date')
        )

        return Response(daily_counts, status=status.HTTP_200_OK)
