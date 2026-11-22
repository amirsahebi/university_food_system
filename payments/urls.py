from django.urls import path
from .views import (
    PaymentRequestView, PaymentVerifyView, 
    PaymentHistoryView, PaymentStartView,
    AdminPaymentView, PaymentInquiryView,
    MyWalletView, WalletTopupView,
    WalletPayOrderView, WalletTransactionsListView
)

app_name = 'payments'

urlpatterns = [
    # User-facing payment endpoints
    path("request/", PaymentRequestView.as_view(), name="payment-request"),
    path("start/<str:authority>/", PaymentStartView.as_view(), name="payment_start"),
    path("verify/", PaymentVerifyView.as_view(), name="payment-verify"),
    path("history/", PaymentHistoryView.as_view(), name="payment-history"),
    
    # Wallet endpoints
    path("wallet/", MyWalletView.as_view(), name="my-wallet"),
    path("wallet/topup/", WalletTopupView.as_view(), name="wallet-topup"),
    path("wallet/pay-order/", WalletPayOrderView.as_view(), name="wallet-pay-order"),
    path("wallet/transactions/", WalletTransactionsListView.as_view(), name="wallet-transactions"),

    # Admin endpoints
    path("payments/", AdminPaymentView.as_view(), name="admin-payment-list"),
    path("payments/<int:pk>/", AdminPaymentView.as_view(), name="admin-payment-detail"),
    path("payments/inquire/<str:authority>/", PaymentInquiryView.as_view(), name="admin-payment-inquiry"),
]
