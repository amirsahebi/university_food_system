from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'phone_number', 'student_number', 'first_name', 'last_name', 'role', 'is_active' ,'avatar' ,'avatar_url']

    def get_avatar_url(self, obj):
        if obj.avatar:
            return self.context['request'].build_absolute_uri(obj.avatar.url)
        return None


class CreateUserSerializer(serializers.ModelSerializer):
    """Serializer for creating a new user."""

    class Meta:
        model = User
        fields = ['phone_number', 'password', 'first_name', 'last_name', 'role']
        extra_kwargs = {
            'password': {'write_only': True},  # Ensure password is write-only
        }

    def create(self, validated_data):
        """Create a user using the custom user manager."""
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    phone_number = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        """Validate phone number and password."""
        phone_number = data.get('phone_number')
        password = data.get('password')

        if not phone_number or not password:
            raise serializers.ValidationError("Phone number and password are required.")

        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting a password reset via OTP."""
    phone_number = serializers.CharField(max_length=15)

    def validate_phone_number(self, value):
        """Ensure the phone number exists in the system."""
        if not User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("No user is associated with this phone number.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for resetting a user's password."""
    phone_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        """Ensure all fields are provided."""
        if not data.get('phone_number') or not data.get('otp') or not data.get('new_password'):
            raise serializers.ValidationError("Phone number, OTP, and new password are required.")
        return data
    

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'student_number']