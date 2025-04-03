from django.contrib import admin
from .models import Reservation

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'food', 'time_slot', 'reserved_date', 'has_voucher', 'price', 'status')
    list_filter = ('status', 'reserved_date', 'has_voucher')
    search_fields = ('student__phone_number', 'food__name', 'status')
    readonly_fields = ('price', 'qr_code')
    list_editable = ('status',)

    def get_queryset(self, request):
        """Customize queryset to prefetch related fields for better performance."""
        queryset = super().get_queryset(request)
        return queryset.select_related('student', 'food', 'time_slot')
