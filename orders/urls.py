from django.urls import path
from .views import (
    ChefOrdersView,
    UpdateOrderStatusView,
    PlaceOrderView,
    PendingOrdersView,
    DeliverOrderView,
    StudentOrdersView,
    RetrieveReservationByQRCodeView,
    PickedUpOrdersView,
    ReadyToPickupOrdersView,
)

urlpatterns = [
    path('chef/', ChefOrdersView.as_view(), name='chef_orders'),
    path('<int:id>/status/', UpdateOrderStatusView.as_view(), name='update_order_status'),
    path('place/', PlaceOrderView.as_view(), name='place_order'),
    path('pending/', PendingOrdersView.as_view(), name='pending_orders'),
    path('<int:id>/deliver/', DeliverOrderView.as_view(), name='deliver_order'),
    path('student/', StudentOrdersView.as_view(), name='student_orders'),
    path('qr/', RetrieveReservationByQRCodeView.as_view(), name='retrieve_by_qr_code'),
    path('picked-up/', PickedUpOrdersView.as_view(), name='picked_up_orders'),
    path('ready-to-pickup/', ReadyToPickupOrdersView.as_view(), name='ready_to_pickup_orders'),
]
