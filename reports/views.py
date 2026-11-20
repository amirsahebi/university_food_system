from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from orders.models import Reservation
from users.models import User
from django.db.models import Count, Q, Sum
from django.utils.timezone import now
from datetime import timedelta


def get_persian_week_range(target_date):
    """
    Returns (start_of_week, end_of_week) for Iranian calendar (Saturday to Friday).
    In Python datetime.date: Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6.
    """
    days_since_saturday = (target_date.weekday() + 2) % 7
    saturday = target_date - timedelta(days=days_since_saturday)
    friday = saturday + timedelta(days=6)
    return saturday, friday


class ReservationLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve logs of reservations. Accepts query param `days` (default 7, or 'all').
        """
        days_param = request.query_params.get('days', '7')
        today = now().date()

        queryset = Reservation.objects.select_related('student', 'food', 'voucher_type', 'extra_voucher_type')\
            .filter(status__in=['waiting', 'preparing', 'ready_to_pickup', 'picked_up', 'not_picked_up'])
        
        if days_param != 'all':
            try:
                days_int = int(days_param)
            except ValueError:
                days_int = 7
            start_date = today - timedelta(days=days_int)
            queryset = queryset.filter(reserved_date__gte=start_date)

        reservations = queryset.order_by('-reserved_date', '-created_at')[:200]

        logs = [
            {
                "id": reservation.id,
                "student": f"{reservation.student.first_name} {reservation.student.last_name}" if reservation.student else "ناشناس",
                "student_number": reservation.student.student_number if reservation.student else "-",
                "food": reservation.food.name if reservation.food else "-",
                "meal_type": reservation.meal_type,
                "price": int(reservation.price or 0),
                "original_price": int(reservation.original_price or 0),
                "has_voucher": reservation.has_voucher,
                "has_extra_voucher": reservation.has_extra_voucher,
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
        Comprehensive dashboard & analytics data:
        - past_7_days: Daily counts for past 7 days
        - upcoming_7_days: Daily forecast for upcoming 7 days
        - weekly_order_count: Total non-canceled orders this Persian week
        - student_count: Total registered students
        - top_food_this_week: Most ordered food this Persian week
        - analytics: Rich metrics for executive reports
        """
        today = now().date()

        # 1. Past 7 days (including today)
        past_start = today - timedelta(days=6)
        past_counts_qs = (
            Reservation.objects
            .filter(
                reserved_date__range=[past_start, today],
                status__in=['waiting', 'preparing', 'ready_to_pickup', 'picked_up']
            )
            .values('reserved_date')
            .annotate(
                order_count=Count('id'),
                picked_up_count=Count('id', filter=Q(status='picked_up'))
            )
            .order_by('reserved_date')
        )
        past_7_days = list(past_counts_qs)

        # 2. Upcoming 7 days (starting tomorrow through today+7)
        upcoming_start = today + timedelta(days=1)
        upcoming_end = today + timedelta(days=7)
        upcoming_counts_qs = (
            Reservation.objects
            .filter(
                reserved_date__range=[upcoming_start, upcoming_end],
                status__in=['waiting', 'preparing', 'ready_to_pickup', 'picked_up']
            )
            .values('reserved_date')
            .annotate(
                order_count=Count('id'),
                lunch_count=Count('id', filter=Q(meal_type='lunch')),
                dinner_count=Count('id', filter=Q(meal_type='dinner'))
            )
            .order_by('reserved_date')
        )
        upcoming_7_days = list(upcoming_counts_qs)

        # 3. This Persian week stats (Saturday to Friday)
        saturday, friday = get_persian_week_range(today)
        weekly_order_count = Reservation.objects.filter(
            reserved_date__range=[saturday, friday],
            status__in=['waiting', 'preparing', 'ready_to_pickup', 'picked_up']
        ).count()

        # 4. Registered students count
        student_count = User.objects.filter(role='student', is_deleted=False).count()

        # 5. Top selling food this week
        top_food_qs = (
            Reservation.objects
            .filter(
                reserved_date__range=[saturday, friday],
                status__in=['waiting', 'preparing', 'ready_to_pickup', 'picked_up'],
                food__isnull=False
            )
            .values('food__name')
            .annotate(order_count=Count('id'))
            .order_by('-order_count')
            .first()
        )
        if top_food_qs:
            top_food_this_week = {
                'name': top_food_qs['food__name'],
                'count': top_food_qs['order_count']
            }
        else:
            top_food_this_week = {
                'name': 'هنوز ثبت نشده',
                'count': 0
            }

        # 6. Comprehensive Analytics
        total_reservations = Reservation.objects.exclude(status='canceled').count()
        picked_up_count = Reservation.objects.filter(status='picked_up').count()
        not_picked_up_count = Reservation.objects.filter(status='not_picked_up').count()
        preparing_count = Reservation.objects.filter(status='preparing').count()
        waiting_count = Reservation.objects.filter(status='waiting').count()
        ready_to_pickup_count = Reservation.objects.filter(status='ready_to_pickup').count()

        fulfillment_rate = (
            round((picked_up_count / total_reservations * 100), 1)
            if total_reservations > 0 else 100.0
        )

        financials = Reservation.objects.exclude(status='canceled').aggregate(
            total_cash=Sum('price'),
            total_gross=Sum('original_price'),
        )
        total_cash = int(financials.get('total_cash') or 0)
        total_gross = int(financials.get('total_gross') or 0)
        total_subsidies = max(0, total_gross - total_cash)

        # Average daily orders (last 30 days)
        last_30_days_start = today - timedelta(days=30)
        orders_last_30 = Reservation.objects.filter(
            reserved_date__range=[last_30_days_start, today]
        ).exclude(status='canceled').count()
        avg_daily_orders = round(orders_last_30 / 30, 1)

        # Meal distribution
        lunch_count = Reservation.objects.filter(meal_type='lunch').exclude(status='canceled').count()
        dinner_count = Reservation.objects.filter(meal_type='dinner').exclude(status='canceled').count()

        # Top 10 popular foods
        top_foods_qs = (
            Reservation.objects
            .filter(food__isnull=False)
            .exclude(status='canceled')
            .values('food__id', 'food__name', 'food__price')
            .annotate(count=Count('id'), total_revenue=Sum('price'))
            .order_by('-count')[:10]
        )
        top_foods = [
            {
                'id': item['food__id'],
                'name': item['food__name'],
                'price': int(item['food__price'] or 0),
                'count': item['count'],
                'total_revenue': int(item['total_revenue'] or 0),
            }
            for item in top_foods_qs
        ]

        # Voucher breakdown
        voucher_counts = {
            'has_voucher': Reservation.objects.filter(has_voucher=True).exclude(status='canceled').count(),
            'has_extra_voucher': Reservation.objects.filter(has_extra_voucher=True).exclude(status='canceled').count(),
            'no_voucher': Reservation.objects.filter(has_voucher=False, has_extra_voucher=False).exclude(status='canceled').count(),
        }

        # Status distribution
        status_distribution = {
            'picked_up': picked_up_count,
            'ready_to_pickup': ready_to_pickup_count,
            'preparing': preparing_count,
            'waiting': waiting_count,
            'not_picked_up': not_picked_up_count,
        }

        analytics_data = {
            'total_reservations': total_reservations,
            'fulfillment_rate': fulfillment_rate,
            'total_gross': total_gross,
            'total_cash': total_cash,
            'total_subsidies': total_subsidies,
            'avg_daily_orders': avg_daily_orders,
            'meal_distribution': {
                'lunch': lunch_count,
                'dinner': dinner_count,
            },
            'status_distribution': status_distribution,
            'voucher_distribution': voucher_counts,
            'top_foods': top_foods,
        }

        return Response({
            "past_7_days": past_7_days,
            "upcoming_7_days": upcoming_7_days,
            "weekly_order_count": weekly_order_count,
            "student_count": student_count,
            "top_food_this_week": top_food_this_week,
            "analytics": analytics_data,
        }, status=status.HTTP_200_OK)
