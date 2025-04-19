from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import DailyMenuItem, TimeSlot

@receiver(post_save, sender=DailyMenuItem)
def update_daily_menu_item_availability(sender, instance, **kwargs):
    """Automatically update `is_available` for DailyMenuItem before saving."""
    if instance.daily_capacity == 0 or instance.time_slot_capacity == 0:
        instance.is_available = False
    else:
        instance.is_available = True


@receiver(post_save, sender=DailyMenuItem)
def update_time_slots_availability(sender, instance, **kwargs):
    """Update `is_available` for TimeSlots when a DailyMenuItem is updated."""
    instance.time_slots.update(is_available=instance.is_available)


@receiver(post_save, sender=TimeSlot)
def update_time_slot_availability(sender, instance, **kwargs):
    """Automatically update `is_available` for TimeSlot before saving."""
    instance.is_available = instance.capacity > 0


@receiver(post_save, sender=DailyMenuItem)
def update_time_slot_capacity(sender, instance, **kwargs):
    """Update TimeSlot capacities when DailyMenuItem's time_slot_capacity changes."""
    
    # Step 1: Get the original object before the update
    try:
        original = DailyMenuItem.objects.get(pk=instance.pk)
    except DailyMenuItem.DoesNotExist:
        return  # The object is new (not an update), so we do nothing

    # Step 2: If time_slot_capacity has changed, update all related TimeSlots
    if original.time_slot_capacity != instance.time_slot_capacity:
        instance.time_slots.update(capacity=instance.time_slot_capacity)

