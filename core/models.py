from django.db import models
from django.core.exceptions import ValidationError


class VoucherType(models.Model):
    code = models.CharField(max_length=50, unique=True, help_text="Unique identifier, e.g. type_1, type_2, type_3, type_4")
    name = models.CharField(max_length=100, help_text="Human readable name")
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.0, 
        help_text="Discount deduction in Tomans"
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['discount_amount']
        verbose_name = "Voucher Type"
        verbose_name_plural = "Voucher Types"

    def clean(self):
        if self.discount_amount < 0:
            raise ValidationError("Discount amount must be non-negative.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.discount_amount:,.0f} تومان)"


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
        vt = VoucherType.objects.filter(is_active=True).first()
        if vt:
            return vt.discount_amount
        return cls.get_voucher_settings().price

    # Keep this method for backward compatibility, but it just returns the regular voucher price
    @classmethod
    def get_extra_voucher_price(cls):
        """Get the current extra voucher price (same as regular voucher price)."""
        return cls.get_voucher_price()

    def __str__(self):
        return f"Voucher - Discount: {self.price}"
