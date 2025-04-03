from django.db import models
from food.models import Food


class TemplateMenu(models.Model):
    day = models.CharField(max_length=10, choices=[
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ])
    meal_type = models.CharField(max_length=10, choices=[('lunch', 'Lunch'), ('dinner', 'Dinner')])

    def __str__(self):
        return f"{self.day} - {self.meal_type}"


class TemplateMenuItem(models.Model):
    template_menu = models.ForeignKey(TemplateMenu, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    start_time = models.TimeField()
    end_time = models.TimeField()
    time_slot_count = models.PositiveIntegerField()
    time_slot_capacity = models.PositiveIntegerField()
    daily_capacity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.food.name} ({self.template_menu})"


class DailyMenu(models.Model):
    date = models.DateField()
    meal_type = models.CharField(max_length=10, choices=[('lunch', 'Lunch'), ('dinner', 'Dinner')])

    def __str__(self):
        return f"{self.date} - {self.meal_type}"


class DailyMenuItem(models.Model):
    daily_menu = models.ForeignKey(DailyMenu, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    start_time = models.TimeField()
    end_time = models.TimeField()
    time_slot_count = models.PositiveIntegerField()
    time_slot_capacity = models.PositiveIntegerField()
    daily_capacity = models.PositiveIntegerField()
    is_available = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        """Override save method to update related TimeSlot capacities."""
        if self.pk:  # Check if the object is being updated
            original = DailyMenuItem.objects.get(pk=self.pk)
            if original.time_slot_capacity != self.time_slot_capacity:
                self.time_slots.update(capacity=self.time_slot_capacity)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.food.name} ({self.daily_menu})"


class TimeSlot(models.Model):
    daily_menu_item = models.ForeignKey(DailyMenuItem, on_delete=models.CASCADE, related_name="time_slots")
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField()
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.daily_menu_item.food.name} - {self.start_time} to {self.end_time}"
