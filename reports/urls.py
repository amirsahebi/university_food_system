from django.urls import path
from .views import ReservationLogsView, DailyOrderCountsView

urlpatterns = [
    path('orders/logs/', ReservationLogsView.as_view(), name='reservation_logs'),
    path('orders/daily-counts/', DailyOrderCountsView.as_view(), name='daily_order_counts'),
]
