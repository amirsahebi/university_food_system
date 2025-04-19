from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Reservation
from users.utils import SMSService
import logging

# Set up logger
logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Reservation)
def handle_reservation_status_change(sender, instance, **kwargs):
    """
    Signal to send notification when reservation status changes from 'preparing' to 'ready_to_pickup'
    """
    # First check if this is an existing reservation (not a new one)
    if instance.pk:
        try:
            # Get the old instance to compare status
            old_instance = Reservation.objects.get(pk=instance.pk)
            
            # Check if status is changing from 'preparing' to 'ready_to_pickup'
            if old_instance.status == 'preparing' and instance.status == 'ready_to_pickup':
                # Update the updated_at timestamp
                instance.updated_at = timezone.now()
                
                # Send notification to the student
                send_ready_pickup_notification(instance)
        except Reservation.DoesNotExist:
            pass  # This is a new reservation, no status change

def send_ready_pickup_notification(reservation):
    """
    Sends a notification to the student that their order is ready for pickup.
    
    Uses the SMSService class to send an SMS notification to the student's phone number.
    """
    student = reservation.student
    delivery_code = reservation.delivery_code
    phone_number = student.phone_number
    name = student.first_name
    
    # Log the notification
    logger.info(f"Sending pickup notification to {phone_number} for reservation {reservation.id}")
    
    # Send the SMS using SMSService
    result = SMSService.send_notification(phone_number, name, delivery_code)
    
    # Log the result
    if result["status"] == "success":
        logger.info(f"Successfully sent pickup notification to {phone_number}")
    else:
        logger.error(f"Failed to send pickup notification to {phone_number}: {result['message']}")
        
    # Return the result of the SMS sending operation
    return result