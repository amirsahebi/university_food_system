from django.db import models
from django.contrib.auth import get_user_model
from food.models import Food
from core.models import Voucher
from menu.models import TimeSlot
import qrcode
from io import BytesIO
from django.core.files import File
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
from django.conf import settings

User = get_user_model()

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending_payment', 'Pending Payment'),
        ('waiting', 'Waiting'),
        ('preparing', 'Preparing'),
        ('ready_to_pickup', 'Ready to Pickup'),
        ('picked_up', 'Picked Up'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations')
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    meal_type = models.CharField(max_length=10, choices=[('lunch', 'Lunch'), ('dinner', 'Dinner')])
    reserved_date = models.DateField()
    has_voucher = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    qr_code = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    def encrypt_data(self, data):
        """Encrypt data using AES encryption."""
        key = settings.SECRET_KEY[:32]  # Ensure the key is 32 bytes for AES-256
        cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC)
        iv = cipher.iv  # Initialization vector
        encrypted_data = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
        return base64.b64encode(iv + encrypted_data).decode('utf-8')

    def decrypt_data(self, encrypted_data):
        """Decrypt data using AES decryption."""
        key = settings.SECRET_KEY[:32]
        decoded_data = base64.b64decode(encrypted_data)
        iv = decoded_data[:16]
        encrypted_message = decoded_data[16:]
        cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(encrypted_message), AES.block_size).decode('utf-8')

    def generate_qr_code(self):
        """Generate a QR code with encrypted data and save it as a string."""
        qr_data = f"Reservation ID: {self.id}, Student: {self.student.phone_number}, Food: {self.food.name}, Status: {self.status}"
        encrypted_qr_data = self.encrypt_data(qr_data)
        self.qr_code = encrypted_qr_data
        

    def calculate_price(self):
        global_voucher_price = Voucher.get_voucher_price()
        return self.food.price-global_voucher_price if self.has_voucher else self.food.price

    def save(self, *args, **kwargs):
        if not self.price:
            self.price = self.calculate_price()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.phone_number} - {self.food.name} ({self.status})"
