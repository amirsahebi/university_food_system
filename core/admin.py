from django.contrib import admin
from .models import Voucher

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ['price']
