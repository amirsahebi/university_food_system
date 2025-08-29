from celery import shared_task
from university_food_system.tasks_with_logging import task_with_logging
from utils.logging_strategy import (
    get_logger, 
    create_audit_log
)
from django.utils import timezone
from datetime import timedelta

logger = get_logger('tasks.background_tasks')


@shared_task
@task_with_logging
def cancel_pending_payment_reservations():
    """
    Background task to cancel reservations that have been in pending_payment status for more than 10 minutes
    """
    from orders.models import Reservation
    
    # Find reservations older than 10 minutes that are still in pending_payment
    expiration_time = timezone.now() - timedelta(minutes=10)
    logger.info(f"Checking for pending payment reservations older than {expiration_time}")
    
    expired_reservations = Reservation.objects.filter(
        status='pending_payment', 
        created_at__lt=expiration_time
    )
    
    total_expired = expired_reservations.count()
    logger.info(f"Found {total_expired} reservations to cancel")
    
    if total_expired == 0:
        logger.info("No reservations to cancel")
        return
    
    # Cancel expired reservations
    for reservation in expired_reservations:
        try:
            logger.info(f"Cancelling reservation {reservation.id} for student {reservation.student_id}")
            reservation.status = 'cancelled'
            reservation.save()
            
            # Audit log for reservation cancellation
            create_audit_log(
                reservation.student, 
                'reservation_payment_expired', 
                {
                    'reservation_id': reservation.id,
                    'original_status': 'pending_payment'
                }
            )
            logger.info(f"Successfully cancelled reservation {reservation.id}")
        except Exception as e:
            logger.error(
                f'Failed to cancel reservation {reservation.id}',
                exc_info=True,
                extra={'reservation_id': reservation.id}
            )
    
    logger.info(f"Successfully cancelled {total_expired} reservations")
    return f"{total_expired} pending payment reservations cancelled."
