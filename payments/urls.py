from django.urls import path
from .views import PaymentRequestView, PaymentVerifyView, PaymentHistoryView, PaymentStartView

urlpatterns = [
    path("request/", PaymentRequestView.as_view(), name="payment_request"),
    path("start/<str:authority>/", PaymentStartView.as_view(), name="payment_start"),
    path("verify/", PaymentVerifyView.as_view(), name="payment_verify"),
    path("history/", PaymentHistoryView.as_view(), name="payment_history"),
]
