from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, OTP
from .forms import UserCreationForm, UserChangeForm


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin to handle phone_number instead of username."""

    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    list_display = ('phone_number', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')

    # Customize the fieldsets to use phone_number
    fieldsets = (
        (None, {'fields': ('phone_number', 'password', 'role', 'student_number')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    # Customize the add_fieldsets for creating a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )

    search_fields = ('phone_number', 'first_name', 'last_name')
    ordering = ('phone_number',)


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('id', 'phone_number', 'otp', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('phone_number', 'otp')
    ordering = ('-created_at',)
