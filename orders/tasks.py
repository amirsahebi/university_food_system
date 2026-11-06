import logging
from celery import shared_task
from users.utils import SMSService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_pickup_notification_task(self, reservation_id):
    """
    Asynchronous Celery task to send SMS pickup notification.
    Decoupled from database transactions to prevent hanging locks and rollbacks.
    """
    from orders.models import Reservation
    try:
        reservation = Reservation.objects.select_related('student').get(id=reservation_id)
        student = reservation.student
        if not student or not student.phone_number:
            logger.warning(f"No student/phone for reservation {reservation_id}, skipping SMS.")
            return "Skipped: no phone number"

        logger.info(f"[SMS Task] Sending ready_to_pickup notification to {student.phone_number} for order {reservation.id}")
        result = SMSService.send_notification(
            phone_number=student.phone_number,
            name=student.first_name,
            delivery_code=reservation.delivery_code
        )
        logger.info(f"[SMS Task] SMS result for order {reservation.id}: {result.get('status')}")
        return result
    except Exception as exc:
        logger.error(f"[SMS Task] Failed to send SMS for order {reservation_id}: {str(exc)}", exc_info=True)
        # Retry with exponential backoff on transient errors
        try:
            self.retry(exc=exc)
        except Exception:
            pass
        return f"Error: {str(exc)}"
