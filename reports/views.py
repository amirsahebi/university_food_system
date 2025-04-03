from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from orders.models import Reservation
from django.db.models import Count
from django.utils.timezone import now
from datetime import timedelta


class ReservationLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve logs of reservations.
        """
        reservations = Reservation.objects.select_related('student', 'food').all()
        logs = [
            {
                "id": reservation.id,
                "student": f"{reservation.student.first_name} {reservation.student.last_name}",
                "food": reservation.food.name,
                "status": reservation.status,
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
            Reservation.objects.filter(created_at__date__range=[start_date, today])
            .extra(select={'day': "date(created_at)"})
            .values('day')
            .annotate(order_count=Count('id'))
            .order_by('day')
        )

        response_data = [{"day": count['day'], "order_count": count['order_count']} for count in daily_counts]
        return Response(response_data, status=status.HTTP_200_OK)
