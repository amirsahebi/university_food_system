from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, permissions, viewsets, serializers
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import User
from .serializers import (
    UserSerializer, CreateUserSerializer, LoginSerializer,
    PasswordResetRequestSerializer, ResetPasswordSerializer,
    UserProfileUpdateSerializer, StudentSerializer, StudentInputSerializer
)
from django.core.cache import cache
from django.utils.timezone import now, timedelta
from .models import User, OTP
from .serializers import UserSerializer, UserProfileUpdateSerializer
from .utils import recover_trust_scores_daily
from rest_framework.permissions import IsAdminUser
import re
from django.contrib.auth import authenticate
from django.conf import settings
import os
from .utils import SMSService
from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from django.core import signing


class FlexibleTokenRefreshSerializer(TokenRefreshSerializer):
    refresh = serializers.CharField(required=False)
    refresh_token = serializers.CharField(required=False, write_only=True)

    def validate(self, attrs):
        token_val = attrs.get('refresh') or self.initial_data.get('refresh_token') or self.initial_data.get('refresh')
        if not token_val:
            raise serializers.ValidationError({"refresh": ["This field is required."]})
        attrs['refresh'] = token_val
        data = super().validate(attrs)
        data['access_token'] = data['access']
        return data


class StudentListCreateAPIView(APIView):
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        queryset = User.objects.filter(role='student').order_by('-date_joined')
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(student_number__icontains=search) |
                Q(email__icontains=search)
            )
        return queryset
    
    def get(self, request, *args, **kwargs):
        students = self.get_queryset()
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)
    
    def post(self, request, *args, **kwargs):
        serializer = StudentInputSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(role='student')
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StudentRetrieveUpdateDestroyAPIView(APIView):
    permission_classes = [IsAdminUser]
    
    def get_object(self, pk):
        return get_object_or_404(User, pk=pk, role='student')
    
    def get(self, request, pk, *args, **kwargs):
        student = self.get_object(pk)
        serializer = StudentSerializer(student)
        return Response(serializer.data)
    
    def put(self, request, pk, *args, **kwargs):
        student = self.get_object(pk)
        serializer = StudentInputSerializer(student, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk, *args, **kwargs):
        student = self.get_object(pk)
        serializer = StudentInputSerializer(student, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk, *args, **kwargs):
        student = self.get_object(pk)
        student.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrustScoreView(APIView):
    """
    API endpoint that allows users to view their trust score and recovery status.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        response_data = {
            'trust_score': user.trust_score,
            'trust_score_updated_at': user.trust_score_updated_at,
            'can_use_vouchers': user.trust_score >= 0,
            'status': 'good' if user.trust_score >= 0 else 'recovery_in_progress'
        }
        
        if user.trust_score < 0:
            # Calculate estimated days to recover (ceiling division)
            points_to_recover = abs(user.trust_score)
            estimated_days = (points_to_recover + 1) // 2  # +1 for ceiling effect
            
            response_data['recovery_info'] = {
                'points_to_recover': points_to_recover,
                'estimated_days': estimated_days,
                'recovery_rate': '2 points per day',
                'message': 'Your trust score will recover automatically by 2 points each day.'
            }
        
        return Response(response_data, status=status.HTTP_200_OK)


class SendOTPView(APIView):
    """Send an OTP to the user's phone number."""
    def post(self, request):
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Use the utility method to validate phone number
        if not SMSService.validate_phone_number(phone_number):
            return Response({"error": "Invalid phone number format"}, status=status.HTTP_400_BAD_REQUEST)

        # System-wide rate limiting (by IP address)
        ip_address = self.get_client_ip(request)
        system_cache_key = f"system_otp_limit:{ip_address}"
        system_attempts = cache.get(system_cache_key) or 0
        
        if system_attempts >= 5:  # Limit to 5 attempts per IP within the window
            return Response(
                {"error": "Too many requests from your system. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Phone number specific rate limit
        cache_key = f"otp_limit:{phone_number}"
        attempts = cache.get(cache_key)
        if attempts:
            return Response(
                {"error": "Too many requests. Please wait before requesting another OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # **Delete any existing OTP for this phone number**
        OTP.objects.filter(phone_number=phone_number).delete()

        # Generate OTP
        otp_code = OTP.generate_otp()
        OTP.objects.create(phone_number=phone_number, otp=otp_code)

        # Send OTP via SMS using the utility
        sms_result = SMSService.send_otp(phone_number, otp_code)
        
        if sms_result['status'] == 'error':
            return Response(
                {"error": sms_result['message']}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # **Set cache to enforce rate limit (5 min = 300 seconds)**
        cache.set(cache_key, 1, timeout=300)
        
        # Increment the system-wide counter for this IP
        cache.set(system_cache_key, system_attempts + 1, timeout=3600)  # 1 hour timeout for IP-based limiting

        return Response({"message": "OTP sent successfully"})

    def get_client_ip(self, request):
        """Get client IP address from request, accounting for proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class VerifyOTPView(APIView):
    """Verify the OTP sent to the user's phone with brute-force defense."""
    def post(self, request):
        phone_number = request.data.get('phone_number')
        otp_code = request.data.get('code')

        if not phone_number or not otp_code:
            return Response({"error": "Phone number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        # Brute-force throttling: max 5 failed attempts per phone
        cache_key = f"otp_attempts:{phone_number}"
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            OTP.objects.filter(phone_number=phone_number).delete()
            return Response({
                "error": "Too many failed attempts. Please request a new verification code."
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        try:
            otp_entry = OTP.objects.get(phone_number=phone_number, otp=otp_code)
            if otp_entry.is_valid():
                # Reset attempt counter
                cache.delete(cache_key)
                # Delete OTP to prevent replay attacks
                otp_entry.delete()
                
                # Issue signed verification token valid for 10 minutes
                verification_token = signing.dumps(
                    {"phone_number": phone_number, "action": "signup"},
                    salt="signup-verification"
                )
                return Response({
                    "verified": True,
                    "verification_token": verification_token
                }, status=status.HTTP_200_OK)

            return Response({"error": "OTP expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)
        except OTP.DoesNotExist:
            cache.set(cache_key, attempts + 1, timeout=300)
            remaining = 5 - (attempts + 1)
            return Response({
                "error": f"Invalid verification code. {remaining} attempt(s) remaining."
            }, status=status.HTTP_400_BAD_REQUEST)


class SignUpView(APIView):
    """Sign up a new student after cryptographic OTP verification."""
    def post(self, request):
        phone_number = request.data.get('phone_number')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        student_number = request.data.get('student_number')
        password = request.data.get('password')
        verification_token = request.data.get('verification_token')

        if not phone_number or not password or not first_name or not last_name:
            return Response({"error": "All required fields must be provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce valid cryptographic verification token from VerifyOTPView
        if not verification_token:
            return Response({
                "error": "Verification token required. Please verify your phone number via SMS first."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = signing.loads(verification_token, salt="signup-verification", max_age=600)
            if payload.get("phone_number") != phone_number or payload.get("action") != "signup":
                return Response({
                    "error": "Verification token does not match this phone number."
                }, status=status.HTTP_400_BAD_REQUEST)
        except signing.SignatureExpired:
            return Response({
                "error": "Verification has expired. Please verify your phone number again."
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({
                "error": "Invalid verification token. Please verify your phone number via SMS first."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if user already exists
        if User.objects.filter(phone_number=phone_number).exists():
            return Response({"error": "User with this phone number already exists."}, status=status.HTTP_400_BAD_REQUEST)

        if student_number and User.objects.filter(student_number=student_number).exists():
            return Response({"error": "Student number is already registered."}, status=status.HTTP_400_BAD_REQUEST)

        # Create user
        user = User.objects.create_user(
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            password=password,
            student_number=student_number,
            role='student'
        )
        return Response({
            "message": "Student registered successfully",
            "phone_number": user.phone_number
        }, status=status.HTTP_201_CREATED)


class SignInView(APIView):
    """Sign in a user and return JWT tokens."""
    def post(self, request):
        phone_number = request.data.get('phone_number')
        password = request.data.get('password')

        user = authenticate(phone_number=phone_number, password=password)
        print(user)
        if not user:

            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {
                "id": user.id,
                "phone_number": user.phone_number,
                "role": user.role
            }
        })


class SignOutView(APIView):
    """Log out by blacklisting the refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh_token")
        if not refresh_token:
            return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RefreshTokenView(TokenRefreshView):
    """Refresh JWT tokens with backward and forward compatibility."""
    serializer_class = FlexibleTokenRefreshSerializer


class MeView(APIView):
    """Retrieve details of the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user, context={'request': request})
        return Response(serializer.data)


class RequestPasswordResetView(APIView):
    """Send an OTP for password reset with rate limiting."""
    def post(self, request):
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate phone number format
        if not SMSService.validate_phone_number(phone_number):
            return Response({"error": "Invalid phone number format"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        if not User.objects.filter(phone_number=phone_number).exists():
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # **Rate limit: Allow request only once every 5 minutes**
        cache_key = f"reset_password_limit:{phone_number}"
        attempts = cache.get(cache_key)
        if attempts:
            return Response({"error": "Too many requests. Please wait before requesting another OTP."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Generate OTP and send it
        otp_code = OTP.generate_otp()
        OTP.objects.create(phone_number=phone_number, otp=otp_code)

        # Send OTP via SMS using the utility
        sms_result = SMSService.send_otp(phone_number, otp_code)
        
        if sms_result['status'] == 'error':
            return Response(
                {"error": sms_result['message']}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Set cache to enforce rate limit (5 min = 300 seconds)
        cache.set(cache_key, 1, timeout=300)

        return Response({"message": "Password reset OTP sent successfully"})


class ResetPasswordView(APIView):
    """Reset password using OTP with brute-force defense."""
    def post(self, request):
        phone_number = request.data.get('phone_number')
        otp_code = request.data.get('otp')
        new_password = request.data.get('new_password')

        if not phone_number or not otp_code or not new_password:
            return Response({"error": "Phone number, OTP, and new password are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Brute-force throttling on password reset attempts
        cache_key = f"reset_attempts:{phone_number}"
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            OTP.objects.filter(phone_number=phone_number).delete()
            return Response({
                "error": "Too many failed attempts. Please request a new password reset code."
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Verify OTP
        try:
            otp_entry = OTP.objects.get(phone_number=phone_number, otp=otp_code)
            if otp_entry.is_valid():
                cache.delete(cache_key)
                try:
                    user = User.objects.get(phone_number=phone_number)
                    user.set_password(new_password)
                    user.save()

                    # Delete OTP after successful use
                    otp_entry.delete()

                    return Response({"message": "Password reset successfully"})
                except User.DoesNotExist:
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": "OTP expired"}, status=status.HTTP_400_BAD_REQUEST)
        except OTP.DoesNotExist:
            cache.set(cache_key, attempts + 1, timeout=300)
            remaining = 5 - (attempts + 1)
            return Response({
                "error": f"Invalid verification code. {remaining} attempt(s) remaining."
            }, status=status.HTTP_400_BAD_REQUEST)

class UserProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        serializer = UserProfileUpdateSerializer(user, data=request.data, partial=True)
        print(request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profile updated successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('currentPassword')
        new_password = request.data.get('newPassword')

        if not current_password or not new_password:
            print({"error": "Current password and new password are required"})
            return Response({"error": "Current password and new password are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(current_password):
            print({"error": "Current password is incorrect"})
            return Response({"error": "Current password is incorrect"},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)
    

class CheckPhoneNumberView(APIView):
    """Check if a phone number is registered in the system."""
    def post(self, request):
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate phone number format
        if not re.match(r'^(?:\+98|0)?9\d{9}$', phone_number):
            return Response({"error": "Invalid phone number format"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if phone number exists
        exists = User.objects.filter(phone_number=phone_number).exists()

        return Response({"exists": exists}, status=status.HTTP_200_OK)
    
class CheckStudentNumberView(APIView):
    """Check if a student number is registered in the system."""
    def post(self, request):
        student_number = request.data.get('student_number')
        
        if not student_number:
            return Response(
                {"error": "Student number is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        exists = User.objects.filter(student_number=student_number).exists()
        
        return Response({"exists": exists}, status=status.HTTP_200_OK)


class AdminTrustScoreRecoveryView(APIView):
    """
    Admin endpoint to manually trigger trust score recovery.
    This is meant for testing and admin purposes.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request):
        # Expecting student identifier in request
        student_id = request.data.get('student_id') or request.data.get('student_number')
        if not student_id:
            return Response(
                {"error": "'student_id' is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find the student by id
        try:
            student = User.objects.get(id=student_id)
        except User.DoesNotExist:
            return Response(
                {"error": "Student not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Only adjust if trust_score is negative
        if student.trust_score < 0:
            previous_score = student.trust_score
            student.trust_score = 0
            student.trust_score_updated_at = now()
            student.save(update_fields=["trust_score", "trust_score_updated_at"])
            return Response(
                {
                    "message": "Trust score reset to zero",
                    "student_id": student.id,
                    "previous_trust_score": previous_score,
                    "new_trust_score": student.trust_score,
                },
                status=status.HTTP_200_OK,
            )

        # Nothing to change if score is already zero or positive
        return Response(
            {
                "message": "No change needed; trust score is not negative",
                "student_id": student.id,
                "trust_score": student.trust_score,
            },
            status=status.HTTP_200_OK,
        )
