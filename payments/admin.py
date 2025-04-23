from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Payment
from orders.models import Reservation

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'reservation_link',
        'amount',
        'status',
        'created_at',
        'authority',
        'ref_id'
    )
    list_filter = (
        'status',
        'created_at',
        'user',
    )
    search_fields = (
        'id',
        'authority',
        'ref_id',
        'user__phone_number',
        'reservation__delivery_code'
    )
    readonly_fields = (
        'created_at',
        'authority',
        'ref_id'
    )
    list_per_page = 50
    date_hierarchy = 'created_at'
    actions = ['mark_as_paid', 'mark_as_failed']

    def reservation_link(self, obj):
        """Display a clickable link to the related reservation."""
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/orders/reservation/{obj.reservation.id}/change/",
            obj.reservation.id
        )
    reservation_link.short_description = _('Reservation')
    reservation_link.allow_tags = True

    @admin.action(description='Mark selected payments as paid')
    def mark_as_paid(self, request, queryset):
        updated = queryset.update(status='paid')
        self.message_user(request, f'Successfully marked {updated} payments as paid.')

    @admin.action(description='Mark selected payments as failed')
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f'Successfully marked {updated} payments as failed.')

    def get_queryset(self, request):
        """Optimize the queryset to avoid multiple database queries."""
        return super().get_queryset(request).select_related('user', 'reservation')