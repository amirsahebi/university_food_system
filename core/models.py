from django.db import models
from django.core.exceptions import ValidationError


class Voucher(models.Model):
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.0, 
        help_text="Voucher discount amount"
    )

    def clean(self):
        if self.price < 0:
            raise ValidationError("Voucher price must be a non-negative value.")

    def save(self, *args, **kwargs):
        self.clean()  # Call the clean method before saving
        super().save(*args, **kwargs)

    @classmethod
    def get_voucher_settings(cls):
        """Get or create voucher settings."""
        return cls.objects.get_or_create(id=1)[0]

    @classmethod
    def get_voucher_price(cls):
        """Get the current voucher price."""
        return cls.get_voucher_settings().price

    # Keep this method for backward compatibility, but it just returns the regular voucher price
    @classmethod
    def get_extra_voucher_price(cls):
        """Get the current extra voucher price (same as regular voucher price)."""
        return cls.get_voucher_price()

    def __str__(self):
        return f"Voucher - Discount: {self.price}"
