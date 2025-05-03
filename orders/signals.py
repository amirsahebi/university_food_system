from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from .models import Reservation
from menu.models import DailyMenuItem
from users.utils import SMSService
import logging

# Set up logger
logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Reservation)
def handle_reservation_status_change(sender, instance, **kwargs):
    """
    Signal to handle reservation status changes:
    - Send notification when reservation status changes from 'preparing' to 'ready_to_pickup'
    - Update capacity when a new reservation is created
    - Restore capacity when status changes to 'cancelled'
    """
    try:
        with transaction.atomic():
            # Handle new reservation creation
            if not instance.pk:
                # Update capacity
                instance.time_slot.capacity -= 1
                instance.time_slot.save()
                
                # Update daily menu item capacity
                daily_menu_item = instance.time_slot.daily_menu_item
                daily_menu_item.daily_capacity -= 1
                
                # If capacity reaches zero, mark as unavailable
                if daily_menu_item.daily_capacity <= 0:
                    daily_menu_item.is_available = False
                daily_menu_item.save()
            
            # Get the old instance if it exists
            old_instance = None
            if instance.pk:
                old_instance = Reservation.objects.get(pk=instance.pk)
                
                # Handle cancelled status change
                if old_instance.status == 'pending_payment' and instance.status == 'cancelled':
                    # Restore capacity
                    instance.time_slot.capacity += 1
                    instance.time_slot.save()
                    
                    # Restore daily menu item capacity
                    daily_menu_item = instance.time_slot.daily_menu_item
                    daily_menu_item.daily_capacity += 1
                    
                    # If capacity was zero, make it available again
                    if daily_menu_item.daily_capacity > 0:
                        daily_menu_item.is_available = True
                    daily_menu_item.save()
                    
                # Check if status is changing from 'preparing' to 'ready_to_pickup'
                elif old_instance.status == 'preparing' and instance.status == 'ready_to_pickup':
                    # Update the updated_at timestamp
                    instance.updated_at = timezone.now()
                    # Send notification to the student
                    send_ready_pickup_notification(instance)
                    
    except Reservation.DoesNotExist:
        pass  # This is a new reservation, no status change
    except Exception as e:
        logger.error(f"Error handling reservation status change: {str(e)}")
        raise  # Re-raise the exception to trigger transaction rollback

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