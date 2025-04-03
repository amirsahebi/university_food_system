from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from .models import User


class UserCreationForm(forms.ModelForm):
    """Form for creating new users with password hashing."""

    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('phone_number', 'first_name', 'last_name', 'role')

    def clean_password2(self):
        """Ensure both password fields match."""
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        """Save the provided password in hashed format."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """Form for updating users in the admin panel."""

    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = ('phone_number', 'password', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'is_superuser')

    def clean_password(self):
        """Return the initial value of the password."""
        return self.initial["password"]
