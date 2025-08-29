# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The phone number must be set')
        user = self.model(phone_number=phone_number, **extra_fields)
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

    def get_queryset(self):
        # Exclude soft-deleted users by default
        return super().get_queryset().filter(is_deleted=False)


class User(AbstractUser):
    username = None  # Remove username
    phone_number = models.CharField(max_length=15, unique=True)
    student_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=[
        ('student', 'دانشجو'),
        ('receiver', 'پذیرنده'),
        ('admin', 'مدیر'),
    ])
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)  # Add avatar field
    trust_score = models.IntegerField(default=10, help_text="User's trust score")
    trust_score_updated_at = models.DateTimeField(auto_now_add=True, help_text="When the trust score was last updated")
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'phone_number'

    objects = UserManager()
    # Unfiltered manager to access soft-deleted rows when needed
    all_objects = models.Manager()

    def __str__(self):
        return self.phone_number

    def recover_trust_score_daily(self, recovery_rate=2):
        """
        Recover trust score by recovery_rate points per day for users with negative scores.
        This should be called by a scheduled task (e.g., cron job) daily.
        
        Args:
            recovery_rate: Number of points to recover (default: 2)
            
        Returns:
            bool: True if the score was updated, False otherwise
        """
        if self.trust_score < 0:
            # Increase score by recovery_rate points (but don't go above 0)
            new_score = min(self.trust_score + recovery_rate, 0)
            
            # Only update if score changed
            if new_score != self.trust_score:
                self.trust_score = new_score
                self.trust_score_updated_at = now()
                self.save(update_fields=['trust_score', 'trust_score_updated_at'])
                return True
        return False

    def save(self, *args, **kwargs):
        try:
            this = User.objects.get(id=self.id)
            if this.avatar != self.avatar and this.avatar:
                this.avatar.delete(save=False)
        except User.DoesNotExist:
            pass
        super(User, self).save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete: mark as deleted instead of removing from DB.
        """
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = now()
            self.save(update_fields=['is_deleted', 'deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        """
        Permanently delete the user from DB. Use with caution.
        """
        return super(User, self).delete(using=using, keep_parents=keep_parents)
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

