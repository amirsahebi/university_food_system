from django.urls import path
from .views import VoucherPriceView

urlpatterns = [
    path('voucher/price/', VoucherPriceView.as_view(), name='voucher_price'),
]
