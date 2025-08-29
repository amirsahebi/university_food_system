"""
Celery tasks for payment processing.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Payment
from .utils import inquire_payment
from core.logging_utils import get_logger
from university_food_system.tasks_with_logging import task_with_logging
import logging

# Get logger with the module's full name
logger = logging.getLogger('payments.tasks')

@shared_task
@task_with_logging
def check_and_reverse_failed_payments():
    """
    Periodic reconciliation of failed and pending payments against ZarinPal.

    Behavior
    - Failed payments: If status in ZarinPal is PAID/VERIFIED and our record is FAILED,
      attempt reversal and mark reservation appropriately. Also stamp failure_details.last_checked.
    - Pending payments: Query ZarinPal and, if PAID/VERIFIED, mark as PAID and update
      reservation. Always stamp failure_details.last_checked.

    Time windows
    - Failed: Only payments with updated_at <= now - 30 minutes are considered (older or equal).
      Payments updated more recently are skipped (not counted as checked/processed).
    - Pending: Only payments with created_at >= now - 30 minutes are considered (newer or equal).

    Returns a summary dict with counts: total_checked, processed_count, reversed_count,
    updated_count, failed_count, skipped_count, and a timestamp.
    """
    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
    
    # Log the current time and threshold for reference (debug only)
    current_time = timezone.now()
    logger.debug(f"[DEBUG] Current time: {current_time}, 30 mins ago: {thirty_minutes_ago}")
    
    # Get failed payments outside the last 30 minutes that haven't been reversed yet
    logger.debug(f"[DEBUG] Querying for failed payments updated <= {thirty_minutes_ago}")
    
    # First, get all failed payments for debugging
    all_failed = Payment.objects.filter(status=Payment.STATUS_FAILED).count()
    logger.debug(f"[DEBUG] Total failed payments in DB: {all_failed}")
    
    # Get payments that match our criteria
    failed_payments = Payment.objects.filter(
        status=Payment.STATUS_FAILED,
        updated_at__lte=thirty_minutes_ago,  # Changed from __gte to __lte to get older payments
        failure_details__reversed=False  # Only process payments we haven't tried to reverse
    ).select_related('reservation')
    
    # Log the raw SQL query for debugging
    logger.debug(f"[DEBUG] SQL Query: {str(failed_payments.query)}")
    
    # Log the query and results for debugging
    count = failed_payments.count()
    logger.debug(f"[DEBUG] Found {count} failed payments to process")
    
    # Log all payments that match the criteria
    for p in failed_payments:
        logger.debug(f"[DEBUG] Matching Payment - ID: {p.id}, Status: {p.status}, Updated: {p.updated_at}, Details: {p.failure_details}")
    
    # If no payments found, log more details about what's in the DB
    if count == 0:
        logger.debug("[DEBUG] No payments matched the criteria. Checking all failed payments:")
        all_payments = Payment.objects.filter(status=Payment.STATUS_FAILED)
        for p in all_payments:
            logger.debug(f"[DEBUG] All Failed Payment - ID: {p.id}, Status: {p.status}, Updated: {p.updated_at}, Details: {p.failure_details}")
            
            # Check why each payment doesn't match the criteria
            if p.updated_at < thirty_minutes_ago:
                logger.debug(f"[DEBUG]   - Payment {p.id} is too old (updated at {p.updated_at})")
            if (p.failure_details or {}).get('reversed', False):
                logger.debug(f"[DEBUG]   - Payment {p.id} is already reversed")
                
    # Log the time range we're querying for
    logger.debug(f"[DEBUG] Query time range: {thirty_minutes_ago} to {current_time}")
    
    # Get pending payments from the last 30 minutes
    pending_payments = Payment.objects.filter(
        status=Payment.STATUS_PENDING,
        created_at__gte=thirty_minutes_ago
    ).select_related('reservation')
    
    logger.info(f"Found {len(failed_payments)} failed and {len(pending_payments)} pending payments to check")
    
    processed_count = 0
    reversed_count = 0
    updated_count = 0
    failed_count = 0
    
    # Process failed payments
    logger.debug(f"Starting to process {len(failed_payments)} failed payments")
    for payment in failed_payments:
        try:
            logger.debug(f"Processing payment {payment.id} with status {payment.status} and failure_details: {payment.failure_details}")
            
            # Skip if we've already tried to reverse this payment
            if payment.failure_details and payment.failure_details.get('reversed', False):
                logger.debug(f"Skipping payment {payment.id} - already reversed")
                continue
                
            # Skip if the payment was updated too recently (less than 30 minutes ago)
            thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
            logger.debug(f"Payment {payment.id} - updated_at: {payment.updated_at} (type: {type(payment.updated_at)}), thirty_minutes_ago: {thirty_minutes_ago} (type: {type(thirty_minutes_ago)})")
            
            # Convert to timezone-naive datetime for comparison if needed
            updated_at_naive = payment.updated_at.replace(tzinfo=None) if payment.updated_at.tzinfo else payment.updated_at
            thirty_minutes_ago_naive = thirty_minutes_ago.replace(tzinfo=None) if thirty_minutes_ago.tzinfo else thirty_minutes_ago
            
            if updated_at_naive > thirty_minutes_ago_naive:
                logger.info(f"Skipping recently failed payment {payment.id} (updated at {payment.updated_at})")
                continue
                
            # Mark this payment as being processed
            processed_count += 1
                
            # Check payment status with ZarinPal
            inquiry_result = inquire_payment(payment.authority)
            
            # If payment is marked as PAID or VERIFIED in ZarinPal but failed in our system, reverse it
            if inquiry_result.get('success') and inquiry_result.get('status') in ['PAID', 'VERIFIED']:
                logger.info(
                    f"Found successful payment for failed payment {payment.id}. "
                    f"Status: {inquiry_result.get('status')}. Reversing..."
                )
                
                # Try to reverse the payment (this will handle both ZarinPal reversal and our DB update)
                from .utils import check_and_reverse_failed_payment
                if check_and_reverse_failed_payment(payment):
                    reversed_count += 1
                    logger.info(f"Successfully processed reversal for payment {payment.id}")
                else:
                    logger.error(f"Failed to reverse payment {payment.id}")
                    
                    # Update failure details if available
                    if hasattr(payment, 'failure_details') and payment.failure_details.get('reversal_error'):
                        error_info = payment.failure_details['reversal_error']
                        logger.error(f"Reversal error details: {error_info}")
            
            # Update failure details to indicate we've checked this payment
            if not payment.failure_details:
                payment.failure_details = {}
            
            # Update last_checked and save the payment
            payment.failure_details['last_checked'] = timezone.now().isoformat()
            payment.save(update_fields=['failure_details'])
            
            # Log that we've checked this payment
            logger.info(f"Checked payment {payment.id} with status {payment.status}")
                    
        except Exception as e:
            logger.error(f"Error processing failed payment {payment.id}: {str(e)}")
            # Update failure details to indicate we've tried to process this
            if not payment.failure_details:
                payment.failure_details = {}
            payment.failure_details['last_error'] = str(e)
            payment.save(update_fields=['failure_details'])
            failed_count += 1
    
    # Process pending payments
    for payment in pending_payments:
        try:
            # Skip if we've checked this payment recently (within last 5 minutes)
            if payment.failure_details and payment.failure_details.get('last_checked'):
                last_checked = timezone.datetime.fromisoformat(payment.failure_details['last_checked'])
                if timezone.now() - last_checked < timedelta(minutes=5):
                    continue
            
            # Check payment status with ZarinPal
            inquiry_result = inquire_payment(payment.authority)
            
            # Update payment status based on ZarinPal's response
            if inquiry_result.get('success'):
                status = inquiry_result.get('status')
                
                if status in ['PAID', 'VERIFIED'] and payment.status != Payment.STATUS_PAID:
                    # Mark as paid if not already
                    payment.status = Payment.STATUS_PAID
                    payment.ref_id = inquiry_result.get('ref_id')
                    payment.save()
                    updated_count += 1
                    processed_count += 1
                    logger.info(f"Updated pending payment {payment.id} to PAID")
                    
                    # Update reservation status if needed
                    if payment.reservation and payment.reservation.status == 'pending_payment':
                        payment.reservation.status = 'waiting'
                        payment.reservation.save()
                        logger.info(f"Updated reservation {payment.reservation.id} to waiting")
                
                # Update last checked time
                if not payment.failure_details:
                    payment.failure_details = {}
                payment.failure_details['last_checked'] = timezone.now().isoformat()
                payment.save(update_fields=['failure_details'])
                
        except Exception as e:
            logger.error(f"Error processing pending payment {payment.id}: {str(e)}")
            if not payment.failure_details:
                payment.failure_details = {}
            payment.failure_details['last_error'] = str(e)
            payment.save(update_fields=['failure_details'])
            failed_count += 1
    
    total_checked = len(failed_payments) + len(pending_payments)
    skipped_count = total_checked - processed_count  # Any payment not processed is considered skipped
    
    return {
        'total_checked': total_checked,
        'processed_count': processed_count,
        'reversed_count': reversed_count,
        'updated_count': updated_count,
        'failed_count': failed_count,
        'skipped_count': skipped_count,
        'timestamp': timezone.now().isoformat()
    }
