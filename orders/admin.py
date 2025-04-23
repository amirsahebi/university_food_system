from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Reservation
from menu.models import TimeSlot

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'student',
        'food',
        'time_slot_link',
        'meal_type',
        'reserved_date',
        'status',
        'delivery_code',
        'created_at',
        'price',
        'has_voucher'
    )
    list_filter = (
        'status',
        'meal_type',
        'reserved_date',
        'created_at',
        'has_voucher',
        'student',
        'food'
    )
    search_fields = (
        'id',
        'student__phone_number',
        'food__name',
        'delivery_code',
        'time_slot__start_time',
        'time_slot__end_time'
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'reservation_number',
        'delivery_code'
    )
    list_per_page = 50
    date_hierarchy = 'created_at'
    actions = ['mark_as_waiting', 'mark_as_preparing', 'mark_as_ready_to_pickup', 'mark_as_picked_up']

    def time_slot_link(self, obj):
        """Display a clickable link to the related time slot."""
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/menu/timeslot/{obj.time_slot.id}/change/",
            f"{obj.time_slot.start_time}-{obj.time_slot.end_time}"
        )
    time_slot_link.short_description = _('Time Slot')
    time_slot_link.allow_tags = True

    @admin.action(description='Mark selected reservations as waiting')
    def mark_as_waiting(self, request, queryset):
        updated = queryset.update(status='waiting')
        self.message_user(request, f'Successfully marked {updated} reservations as waiting.')

    @admin.action(description='Mark selected reservations as preparing')
    def mark_as_preparing(self, request, queryset):
        updated = queryset.update(status='preparing')
        self.message_user(request, f'Successfully marked {updated} reservations as preparing.')

    @admin.action(description='Mark selected reservations as ready to pickup')
    def mark_as_ready_to_pickup(self, request, queryset):
        updated = queryset.update(status='ready_to_pickup')
        self.message_user(request, f'Successfully marked {updated} reservations as ready to pickup.')

    @admin.action(description='Mark selected reservations as picked up')
    def mark_as_picked_up(self, request, queryset):
        updated = queryset.update(status='picked_up')
        self.message_user(request, f'Successfully marked {updated} reservations as picked up.')

    def get_queryset(self, request):
        """Optimize the queryset to avoid multiple database queries."""
        return super().get_queryset(request).select_related(
            'student',
            'food',
            'time_slot'
        )
