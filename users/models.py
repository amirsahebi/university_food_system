# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The phone number must be set')
        user = self.model(phone_number=phone_number, **extra_fields)
        print("HELOOOOOOOOOOO")
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        extra_fields.setdefault('role', 'admin')  # Default role for superuser
        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractUser):
    username = None  # Remove username
    phone_number = models.CharField(max_length=15, unique=True)
    student_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=[
        ('student', 'دانشجو'),
        ('chef', 'آشپز'),
        ('receiver', 'پذیرنده'),
        ('admin', 'مدیر'),
    ])
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)  # Add avatar field
    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'phone_number'

    objects = UserManager()

    def __str__(self):
        return self.phone_number

    def save(self, *args, **kwargs):
        try:
            this = User.objects.get(id=self.id)
            if this.avatar != self.avatar and this.avatar:
                this.avatar.delete(save=False)
        except User.DoesNotExist:
            pass
        super(User, self).save(*args, **kwargs)
import random
from django.utils.timezone import now, timedelta

class OTP(models.Model):
    phone_number = models.CharField(max_length=15)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return self.created_at >= now() - timedelta(minutes=5)  # OTP is valid for 5 minutes

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))

