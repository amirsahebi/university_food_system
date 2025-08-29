from django.db import models


class FoodCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Food Category"
        verbose_name_plural = "Food Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Food(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='foods/', blank=True, null=True)
    category = models.ForeignKey(
        FoodCategory, 
        on_delete=models.SET_NULL, 
        related_name='foods', 
        null=True, 
        blank=True
    )
    supports_extra_voucher = models.BooleanField(
        default=False,
        help_text='Whether this food item supports extra vouchers'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
