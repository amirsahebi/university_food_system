from django.db import models
from django.core.exceptions import ValidationError


class Voucher(models.Model):
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def clean(self):
        if self.price < 0:
            raise ValidationError("Voucher price must be a non-negative value.")

    def save(self, *args, **kwargs):
        self.clean()  # Call the clean method before saving
        super().save(*args, **kwargs)

    @staticmethod
    def get_voucher_price():
        """Fetch the current voucher price."""
        settings, created = Voucher.objects.get_or_create(id=1)  # Ensure a single row exists
        return settings.price

    def __str__(self):
        return f"Voucher Price: {self.price}"
