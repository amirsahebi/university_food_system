from django.urls import path
from .views import (
    ReceiverOrdersView,
    UpdateOrderStatusView,
    PlaceOrderView,
    PendingOrdersView,
    DeliverOrderView,
    StudentOrdersView,
    RetrieveReservationByDeliveryCodeView,
    PickedUpOrdersView,
    ReadyToPickupOrdersView,
    CancelReservationView
)

urlpatterns = [
    path('receiver/', ReceiverOrdersView.as_view(), name='receiver_orders'),
    path('<int:id>/status/', UpdateOrderStatusView.as_view(), name='update_order_status'),
    path('place/', PlaceOrderView.as_view(), name='place_order'),
    path('pending/', PendingOrdersView.as_view(), name='pending_orders'),
    path('<int:id>/deliver/', DeliverOrderView.as_view(), name='deliver_order'),
    path('student/', StudentOrdersView.as_view(), name='student_orders'),
    path('delivery-code/', RetrieveReservationByDeliveryCodeView.as_view(), name='retrieve_by_delivery_code'),
    path('picked-up/', PickedUpOrdersView.as_view(), name='picked_up_orders'),
    path('ready-to-pickup/', ReadyToPickupOrdersView.as_view(), name='ready_to_pickup_orders'),
    path('<int:id>/cancel/', CancelReservationView.as_view(), name='cancel_order'),
]
