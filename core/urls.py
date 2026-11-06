from django.urls import path
from .views import VoucherPriceView, VoucherTypeListCreateView, VoucherTypeDetailView

urlpatterns = [
    path('voucher/price/', VoucherPriceView.as_view(), name='voucher_price'),
    path('voucher-types/', VoucherTypeListCreateView.as_view(), name='voucher_type_list_create'),
    path('voucher-types/<int:pk>/', VoucherTypeDetailView.as_view(), name='voucher_type_detail'),
]
