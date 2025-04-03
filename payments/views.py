from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import redirect
from django.core.paginator import Paginator
from .models import Payment
from .serializers import PaymentRequestSerializer, PaymentSerializer
from .utils import request_payment, verify_payment, ZARINPAL_STARTPAY_URL
from django.conf import settings
from orders.models import Reservation

class PaymentRequestView(APIView):
    """Request a new payment using ZarinPal REST API."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentRequestSerializer(data=request.data)
        print(request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            callback_url = serializer.validated_data['callback_url']
            reservation_id = serializer.validated_data['reservation_id']

            response = request_payment(amount, callback_url, request.user)
            print(response)

            if response.get("data") and response["data"].get("code") == 100:
                authority = response["data"]["authority"]
                payment = Payment.objects.create(
                    user=request.user,
                    amount=amount,
                    authority=authority,
                    status="pending",
                    reservation_id=reservation_id
                )
                return Response({
                    "payment": PaymentSerializer(payment).data,
                    "redirect_url": f"{ZARINPAL_STARTPAY_URL}{authority}"
                }, status=status.HTTP_201_CREATED)

            return Response({"error": response.get("errors", "Payment request failed")}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentStartView(APIView):
    """Redirect user to ZarinPal payment page."""
    
    def get(self, request, authority):
        """Redirects to ZarinPal payment gateway."""
        return redirect(f"{ZARINPAL_STARTPAY_URL}{authority}")


class PaymentVerifyView(APIView):
    """Verify a payment using ZarinPal REST API."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        authority = request.query_params.get("Authority")
        status_query = request.query_params.get("Status")

        if not authority or not status_query:
            return Response({"error": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST)

        if status_query != "OK":
            return Response({"error": "Payment was not successful"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(authority=authority, user=request.user)

            response = verify_payment(payment.amount, authority)

            if "data" in response and response["data"]["code"] in [100, 101]:
                payment.ref_id = response["data"]["ref_id"]
                payment.status = "paid"
                payment.save()
                
                # Update reservation status to waiting
                try:
                    reservation = Reservation.objects.get(id=payment.reservation_id)
                    reservation.status = "waiting"
                    reservation.save()
                except Reservation.DoesNotExist:
                    return Response({"error": "Reservation not found"}, status=status.HTTP_404_NOT_FOUND)
                
                return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)

            payment.status = "failed"
            payment.save()
            return Response({"error": "Payment verification failed"}, status=status.HTTP_400_BAD_REQUEST)

        except Payment.DoesNotExist:
            return Response({"error": "Payment record not found"}, status=status.HTTP_404_NOT_FOUND)


class PaymentHistoryView(APIView):
    """Retrieve payment history for the authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = request.query_params.get("limit", 20)
        offset = request.query_params.get("offset", 0)
        status_filter = request.query_params.get("status")

        payments = Payment.objects.filter(user=request.user)
        if status_filter:
            payments = payments.filter(status=status_filter)

        paginator = Paginator(payments, limit)
        paginated_payments = paginator.get_page(offset)

        return Response({
            "count": paginator.count,
            "results": PaymentSerializer(paginated_payments, many=True).data
        })
