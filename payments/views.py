from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status, generics, filters
from django.shortcuts import redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from .models import Payment
from .serializers import (
    PaymentRequestSerializer, 
    PaymentSerializer, 
    AdminPaymentSerializer,
)
from .utils import request_payment, verify_payment, inquire_payment, ZARINPAL_STARTPAY_URL
from django.conf import settings
from orders.models import Reservation
from core.logging_utils import get_logger
from core.permissions import IsAdminOrReadOnly

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


from django.db import transaction

class PaymentVerifyView(APIView):
    """Verify a payment using ZarinPal REST API with idempotency and retry logic."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        authority = request.query_params.get("Authority")
        status_query = request.query_params.get("Status")

        if not authority or not status_query:
            logger.error("Invalid payment verification request: missing authority or status")
            return Response({"error": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Use select_for_update to lock the payment record and prevent race conditions
                payment = Payment.objects.select_for_update().get(
                    authority=authority, 
                    user=request.user
                )

                logger.info(f"Verifying payment {payment.id} for user {request.user.id}")

                # Check if payment is already processed
                if payment.status == 'paid':
                    logger.info(f"Payment {payment.id} already processed successfully")
                    return self._handle_successful_payment(payment)
                
            if payment.status == 'failed':
                logger.warning(f"Payment {payment.id} previously failed")
                return Response({
                    "error": "Payment verification previously failed",
                    "status": "failed"
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                # Verify payment with ZarinPal (with built-in retry logic)
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
                    
                    logger.info(f"Payment {payment.id} verified successfully with ref_id: {payment.ref_id}")
                    return self._handle_successful_payment(payment)
                else:
                    # Payment verification failed with a non-retryable error
                    error_code = response.get("data", {}).get("code", "Unknown error")
                    error_msg = f"Payment verification failed with code: {error_code}"
                    logger.warning(error_msg)
                    
                    return self._handle_failed_payment(
                        payment, 
                        error_msg,
                        error_code=error_code
                    )

            except Exception as e:
                # Handle ZarinPal API errors and other exceptions
                logger.error(f"Payment verification failed: {str(e)}")
                return self._handle_failed_payment(payment, str(e))

        except Payment.DoesNotExist:
            logger.error(f"Payment record not found for authority: {authority}")
            return Response(
                {"error": "Payment record not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Unexpected error during payment verification: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _handle_successful_payment(self, payment):
        """Handle successful payment verification."""
        return Response({
            "success": True,
            "ref_id": payment.ref_id,
            "reservation_id": payment.reservation.id,
            "status": "paid"
        })
    
    def _handle_failed_payment(self, payment, error_message, error_code=None):
        """Handle failed payment verification."""
        from django.db import transaction
        
        try:
            with transaction.atomic():
                # Update payment status to failed
                payment.status = 'failed'
                payment.save()
                
                # Only cancel the reservation if it's still in pending state
                if payment.reservation.status == 'pending_payment':
                    payment.reservation.status = 'cancelled'
                    payment.reservation.save()
                    logger.info(f"Cancelled reservation {payment.reservation.id} due to payment failure")
            
            response_data = {
                "error": error_message,
                "status": "failed"
            }
            if error_code is not None:
                response_data["code"] = error_code
                
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error handling failed payment {payment.id}: {str(e)}")
            return Response(
                {"error": "Error processing payment failure"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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


class AdminPaymentView(APIView):
    """
    Admin view for managing all payments with advanced filtering and search.
    Only accessible by admin users.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = AdminPaymentSerializer
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    ordering_fields = ['created_at', 'updated_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return filtered queryset of payments."""
        queryset = Payment.objects.select_related('user', 'reservation').order_by('-created_at')
        
        # Apply filters
        params = self.request.query_params
        
        # Filter by user ID
        if 'user_id' in params:
            queryset = queryset.filter(user_id=params['user_id'])
            
        # Filter by status
        if 'status' in params:
            status = params['status'].lower()
            if status == 'failed':
                queryset = queryset.filter(status='failed')
            else:
                queryset = queryset.filter(status=status)
            
        # Filter by amount range
        if 'min_amount' in params:
            queryset = queryset.filter(amount__gte=params['min_amount'])
        if 'max_amount' in params:
            queryset = queryset.filter(amount__lte=params['max_amount'])
            
        # Filter by date range
        if 'start_date' in params:
            queryset = queryset.filter(created_at__date__gte=params['start_date'])
        if 'end_date' in params:
            # Add 1 day to include the entire end_date
            end_date = params['end_date'] + timezone.timedelta(days=1)
            queryset = queryset.filter(created_at__date__lt=end_date)
            
        # Search by authority, ref_id, or error details
        if 'search' in params:
            search = params['search']
            queryset = queryset.filter(
                Q(authority__icontains=search) | 
                Q(ref_id__icontains=search) |
                Q(user__phone_number__icontains=search) |
                Q(failure_details__error_message__icontains=search) |
                Q(failure_details__error_code__icontains=search)
            )
            
        return queryset
    
    def get(self, request):
        """
        List all payments with optional filtering and pagination.
        
        Query Parameters:
        - limit (int): Number of results per page (default: 20, max: 100)
        - offset (int): Number of items to skip (default: 0)
        - status (str): Filter by payment status (optional)
        - user_id (int): Filter by user ID (optional)
        - min_amount (int): Filter by minimum amount (optional)
        - max_amount (int): Filter by maximum amount (optional)
        - start_date (date): Filter by start date (YYYY-MM-DD) (optional)
        - end_date (date): Filter by end date (YYYY-MM-DD) (optional)
        - search (str): Search in authority, ref_id, or user phone number (optional)
        - ordering (str): Field to order by, prefix with - for descending (default: -created_at)
        """
        try:
            # Parse and validate pagination parameters
            limit = min(int(request.query_params.get('limit', 20)), 100)  # Max 100 items per page
            offset = max(0, int(request.query_params.get('offset', 0)))
            
            # Get filtered and ordered queryset
            queryset = self.get_queryset()
            
            # Get total count before pagination
            total_count = queryset.count()
            
            # Apply pagination
            paginated_payments = queryset[offset:offset + limit]
            
            # Serialize the results
            serializer = self.serializer_class(paginated_payments, many=True)
            
            return Response({
                'count': total_count,
                'next': offset + limit < total_count,
                'previous': offset > 0,
                'offset': offset,
                'limit': limit,
                'results': serializer.data
            })
            
        except (ValueError, TypeError) as e:
            return Response(
                {"error": "Invalid parameters. 'limit' and 'offset' must be integers, and dates must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def retrieve(self, request, pk=None):
        """Retrieve a specific payment with detailed information."""
        payment = get_object_or_404(Payment, pk=pk)
        serializer = self.serializer_class(payment)
        return Response(serializer.data)
    
    def delete(self, request, pk=None):
        """
        Delete a payment (soft delete).
        Only payments with status 'pending' can be deleted.
        """
        try:
            payment = Payment.objects.get(pk=pk)
            
            if payment.status != Payment.STATUS_PENDING:
                return Response(
                    {"error": "Only pending payments can be deleted"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            payment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class PaymentInquiryView(APIView):
    """
    Admin API to inquire payment status from ZarinPal.
    This checks the payment status and can automatically reverse failed payments if needed.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request, authority):
        """
        Inquire payment status from ZarinPal and optionally reverse failed payments.
        
        Parameters:
        - authority: The payment authority code from ZarinPal
        - check_reversal (query param, optional): If true, will automatically reverse failed payments
                                                that are actually successful in ZarinPal (default: true)
        
        Returns:
        {
            "success": bool,
            "status": str,  # Payment status from ZarinPal (PAID, VERIFIED, etc.)
            "code": int,    # Response code from ZarinPal
            "message": str, # Response message
            "payment": {    # Existing payment data if found
                "id": int,
                "status": str,
                "amount": int,
                "created_at": "YYYY-MM-DDTHH:MM:SSZ",
                "updated_at": "YYYY-MM-DDTHH:MM:SSZ"
            },
            "reversed": bool  # True if payment was reversed during this request
        }
        """
        from .utils import check_and_reverse_failed_payment
        
        # Get query parameters
        check_reversal = request.query_params.get('check_reversal', 'true').lower() == 'true'
        
        # First try to get the payment from our database
        payment = Payment.objects.filter(authority=authority).first()
        
        # Get the latest status from ZarinPal
        inquiry_result = inquire_payment(authority)
        
        # Check if we should attempt to reverse this payment
        reversed_during_request = False
        if check_reversal and payment and payment.status == 'failed':
            if check_and_reverse_failed_payment(payment):
                reversed_during_request = True
                # Refresh the payment object to get updated status
                payment.refresh_from_db()
        
        # Prepare payment data for response
        payment_data = None
        if payment:
            payment_data = {
                'id': payment.id,
                'status': payment.status,
                'amount': payment.amount,
                'created_at': payment.created_at.isoformat(),
                'updated_at': payment.updated_at.isoformat(),
                'ref_id': payment.ref_id,
            }
            
            # If the payment is not in our database but ZarinPal has it, return that info
            if not payment_data and inquiry_result['success']:
                payment_data = {
                    'status': 'not_in_database',
                    'message': 'Payment not found in our database but exists in ZarinPal',
                }
        
        return Response({
            'success': inquiry_result['success'],
            'status': inquiry_result['status'],
            'code': inquiry_result['code'],
            'message': inquiry_result['message'],
            'payment': payment_data,
            'reversed': reversed_during_request
        })
