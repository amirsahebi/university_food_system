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
from core.logging_utils import get_logger

logger = get_logger(__name__)

class PaymentRequestView(APIView):
    """Request a new payment using ZarinPal REST API."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentRequestSerializer(data=request.data, context={'request': request})
        print(serializer.is_valid())
        print(serializer.errors)
        
        if serializer.is_valid():
            callback_url = serializer.validated_data['callback_url']
            reservation_id = serializer.validated_data['reservation_id']
            
            try:
                reservation = Reservation.objects.get(id=reservation_id)
                logger.info(f"Found reservation {reservation_id} for payment request")
            except Reservation.DoesNotExist:
                logger.error(f"Reservation {reservation_id} not found")
                return Response({
                    "error": "Reservation not found"
                }, status=status.HTTP_404_NOT_FOUND)
            
            # If amount is zero (free reservation), mark as waiting
            if reservation.price <= 0:
                logger.info(f"Free reservation {reservation_id} processed without payment")
                reservation.status = 'waiting'
                reservation.save()
                return Response({
                    "message": "Reservation processed without payment",
                    "status": "waiting"
                    }, status=status.HTTP_200_OK)

            logger.info(f"Requesting payment for reservation {reservation_id} amount {reservation.price}")
            response = request_payment(reservation.price, callback_url, request.user)

            if response.get("data") and response["data"].get("code") == 100:
                authority = response["data"]["authority"]
                logger.info(f"Payment request successful, authority: {authority}")
                payment = Payment.objects.create(
                    user=request.user,
                    amount=reservation.price,
                    authority=authority,
                    status="pending",
                    reservation_id=reservation_id
                )
                logger.info(f"Payment record created for user {request.user.id}, reservation {reservation_id}")
                return Response({
                    "payment": PaymentSerializer(payment).data,
                    "redirect_url": f"{ZARINPAL_STARTPAY_URL}{authority}"
                }, status=status.HTTP_201_CREATED)

            logger.error(f"Payment request failed: {response.get('errors', 'Unknown error')}")
            return Response({"error": response.get("errors", "Payment request failed")}, status=status.HTTP_400_BAD_REQUEST)
        
        logger.error(f"Invalid payment request data: {serializer.errors}")
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
            logger.error("Invalid payment verification request: missing authority or status")
            return Response({"error": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(authority=authority, user=request.user)
            logger.info(f"Verifying payment {payment.id} for user {request.user.id}")

            try:
                # Verify payment with ZarinPal
                response = verify_payment(payment.amount, authority)
                logger.debug(f"Payment verification response: {response}")

                if "data" in response and response["data"]["code"] in [100, 101]:
                    # Update payment status and ref_id
                    payment.ref_id = response["data"]["ref_id"]
                    payment.status = 'paid'
                    payment.save()
                    
                    # Update reservation status to 'waiting'
                    payment.reservation.status = 'waiting'
                    payment.reservation.save()
                    
                    return Response({
                        "success": True,
                        "ref_id": payment.ref_id
                    })
                else:
                    # Payment verification failed
                    payment.status = 'failed'
                    payment.save()
                    
                    # Cancel the reservation
                    payment.reservation.status = 'cancelled'
                    payment.reservation.save()
                    
                    logger.warn(f"Payment verification failed with code: {response['data']['code']}")
                    return Response({
                        "error": "Payment verification failed",
                        "code": response.get("data", {}).get("code", "Unknown error")
                    }, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                # Handle ZarinPal API errors (like 401)
                logger.error(f"Payment verification failed: {str(e)}")
                
                # Update payment status to failed
                payment.status = 'failed'
                payment.save()
                
                # Cancel the reservation
                payment.reservation.status = 'cancelled'
                payment.reservation.save()
                
                return Response({
                    "error": str(e),
                    "status": "failed"
                }, status=status.HTTP_400_BAD_REQUEST)

        except Payment.DoesNotExist:
            logger.error(f"Payment record not found for authority: {authority}")
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
